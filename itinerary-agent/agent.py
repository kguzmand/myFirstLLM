import json
from typing import Annotated, List, Literal, Optional, Sequence

from copilotkit import CopilotKitState
from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "gemini-3.1-flash-lite"
llm = ChatGoogleGenerativeAI(model=MODEL)

CLASSIFY_SYSTEM_PROMPT = (
    "Eres un clasificador de asistente de viajes.\n"
    "Ciudad actual: {city}\n"
    "Días actuales: {num_days}\n"
    "Existe itinerario: {has_itinerary}\n\n"
    "Conversación hasta ahora:\n{history}\n\n"
    "Clasifica la última intención del usuario."
)

CLASSIFY_HUMAN_PROMPT = (
    'Clasifica esta solicitud: "{request}"'
)

PLAN_SYSTEM_PROMPT = (
    "Crea un itinerario de viaje de {num_days} días para {city}. "
    "Incluye 3-4 actividades reales y conocidas por día con horarios realistas."
)

PLAN_HUMAN_PROMPT = "Genera el itinerario ahora."

RESPOND_TASK_NEW_PLAN = (
    "Acabas de generar un itinerario de {num_days} días para {city}. "
    "Dile al usuario que está listo en una frase amistosa. "
    "Menciona que puede eliminar actividades con los botones ✕ o pedir cambios."
)
RESPOND_TASK_MODIFY = (
    'Acabas de aplicar este cambio: "{modification}". '
    "Confirma lo que cambiaste en una frase amistosa."
)
RESPOND_TASK_DEFAULT = "Responde la pregunta del usuario de forma útil y concisa."

RESPOND_SYSTEM_PROMPT = (
    "Eres un asistente amable de planificación de viajes.\n"
    "Ciudad actual: {city}\n"
    "Días actuales: {num_days}\n"
    "Existe itinerario: {has_itinerary}\n\n"
    "Tarea: {task}\n\n"
    "Cuando acabes de crear o modificar un itinerario, llama a la herramienta "
    "`show_trip_summary` con `city`, `num_days`, el total de actividades "
    "(sumando todas las que hay en todos los días) y un `highlight` corto y "
    "evocador. Llámala UNA sola vez por respuesta."
)

RESPOND_NO_HUMAN_REPLY = "¿Cómo puedo ayudarte a planear tu viaje?"

MODIFY_SYSTEM_PROMPT = (
    "Aquí está el itinerario actual de {num_days} días para {city} en JSON:\n"
    "{itinerary}\n\n"
    "Aplica la modificación solicitada y devuelve el itinerario completo "
    "actualizado, conservando todos los días y actividades sin cambios."
)

MODIFY_HUMAN_PROMPT = "Modificación: {modification}"

ASK_REPLY = (
    "¡Me encantaría ayudarte a planear tu viaje! ¿Podrías decirme {missing}?"
)

ASK_DEFAULT_MISSING = "algunos detalles más"

class Activity(BaseModel):
    time: str = Field(description="Formato HH:MM 24h")
    title: str
    description: str
    location: str

class DayPlan(BaseModel):
    day: int
    summary: str
    activities: List[Activity]

class ItineraryState(CopilotKitState):
    messages: Annotated[Sequence[BaseMessage], add_messages]

    city: Optional[str]
    num_days: Optional[int]

    itinerary: List[DayPlan]

    intent: Optional[
        Literal["new_plan", "modify", "missing_info", "chat"]
    ]

    missing: Optional[str]
    modification: Optional[str]

def route_after_classify(state: ItineraryState) -> str:
    intent = state.get("intent")

    if intent == "new_plan":
        return "plan"

    if intent == "modify":
        return "modify"

    if intent == "missing_info":
        return "ask"

    return "respond"

def respond_node(state: ItineraryState) -> dict:
    # Si el último mensaje es un ToolMessage, el agente ya invocó la tool
    # del frontend en este turno. No generes otra respuesta: cerraría el
    # ciclo con otra tool call y el grafo entraría en bucle.
    if state["messages"] and isinstance(state["messages"][-1], ToolMessage):
        return {}

    intent = state.get("intent")
    if intent == "new_plan":
        task = RESPOND_TASK_NEW_PLAN.format(
            num_days=state["num_days"], city=state["city"])
    elif intent == "modify":
        task = RESPOND_TASK_MODIFY.format(
            modification=state.get("modification"))
    else:
        task = RESPOND_TASK_DEFAULT

    humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not humans:
        return {"messages": [AIMessage(content=RESPOND_NO_HUMAN_REPLY)]}

    # Leemos las herramientas que el frontend ha registrado y se las
    # bindeamos al modelo para que pueda llamarlas.
    frontend_tools = state.get("copilotkit", {}).get("actions", [])
    llm_with_tools = llm.bind_tools(frontend_tools) if frontend_tools else llm

    reply = llm_with_tools.invoke([
        SystemMessage(content=RESPOND_SYSTEM_PROMPT.format(
            city=state.get("city") or "not set",
            num_days=state.get("num_days") or "not set",
            has_itinerary=bool(state.get("itinerary")),
            task=task,
        )),
        HumanMessage(content=humans[-1].content),
    ])
    # Enviamos toda la salida
    return {"messages": [reply]}

class ItineraryPlan(BaseModel):
    days: List[DayPlan]


class Intent(BaseModel):
    intent: Literal["new_plan", "modify", "missing_info", "chat"] = Field(
        description=(
            "new_plan: el usuario quiere un itinerario nuevo y tanto la ciudad "
            "como los días están claros. "
            "modify: el usuario quiere cambiar el itinerario existente. "
            "missing_info: el usuario quiere un plan pero falta la ciudad o los días. "
            "chat: pregunta general o conversación."
        )
    )
    city: Optional[str] = Field(None, description="Ciudad de destino si se menciona")
    num_days: Optional[int] = Field(None, description="Número de días si se menciona")
    missing: Optional[str] = Field(
        None,
        description="Qué falta, p. ej. 'la ciudad de destino'. Solo para missing_info.",
    )
    modification: Optional[str] = Field(
        None, description="Modificación exacta solicitada. Solo para modify."
    )

def classify_node(state: ItineraryState) -> dict:
    humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]

    if not humans:
        return {
            "intent": "chat",
            "missing": None,
            "modification": None
        }
    
    # Si el último mensaje es un ToolMessage, este run viene del resultado
    # de un frontend tool, no de un mensaje nuevo del usuario. Devolvemos
    # un intent neutro para que el enrutador termine el flujo sin volver
    # a planear o modificar.
    if isinstance(state["messages"][-1], ToolMessage):
        return {"intent": "chat"}

    history_summary = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in state["messages"]
        if hasattr(m, "content") and m.content
    )

    result: Intent = classifier.invoke([
        SystemMessage(content=CLASSIFY_SYSTEM_PROMPT.format(
            city=state.get("city") or "not set",
            num_days=state.get("num_days") or "not set",
            has_itinerary=bool(state.get("itinerary")),
            history=history_summary,
        )),
        HumanMessage(content=CLASSIFY_HUMAN_PROMPT.format(
            request=humans[-1].content
        )),
    ])

    return {
        "city": result.city or state.get("city"),
        "num_days": result.num_days or state.get("num_days"),
        "intent": result.intent,
        "missing": result.missing,
        "modification": result.modification,
    }

def plan_node(state: ItineraryState) -> dict:
    result: ItineraryPlan = planner.invoke([
        SystemMessage(
            content=PLAN_SYSTEM_PROMPT.format(
                num_days=state["num_days"],
                city=state["city"],
            )
        ),
        HumanMessage(content=PLAN_HUMAN_PROMPT),
    ])

    return {
        "itinerary": [
            d.model_dump() for d in result.days
        ]
    }

# Variante del LLM para clasificar la intención
classifier = llm.with_structured_output(Intent)

# Variante del LLM para generar itinerarios estructurados
planner = llm.with_structured_output(ItineraryPlan)

def modify_node(state: ItineraryState) -> dict:
    # El estado puede llegar como dicts (desde el frontend) o como objetos Pydantic
    # (desde el propio grafo). Normalizamos siempre a DayPlan para validar.
    raw = state.get("itinerary") or []
    current = [DayPlan.model_validate(d) for d in raw]

    itinerary_json = (
        json.dumps([d.model_dump() for d in current], indent=2)
        if current else "none"
    )

    result: ItineraryPlan = planner.invoke([
        SystemMessage(content=MODIFY_SYSTEM_PROMPT.format(
            num_days=state.get("num_days"),
            city=state.get("city"),
            itinerary=itinerary_json,
        )),
        HumanMessage(content=MODIFY_HUMAN_PROMPT.format(
            modification=state.get("modification")
        )),
    ])

    return {
        "itinerary": [
            d.model_dump() for d in result.days
        ]
    }

def ask_node(state: ItineraryState) -> dict:
    return {
        "messages": [
            AIMessage(
                content=ASK_REPLY.format(
                    missing=state.get("missing") or ASK_DEFAULT_MISSING
                )
            )
        ]
    }

builder = StateGraph(ItineraryState)

builder.add_node("classify", classify_node)
builder.add_node("plan", plan_node)
builder.add_node("modify", modify_node)
builder.add_node("ask", ask_node)
builder.add_node("respond", respond_node)

builder.add_edge(START, "classify")

builder.add_conditional_edges(
    "classify",
    route_after_classify,
    ["plan", "modify", "ask", "respond"],
)

builder.add_edge("plan", "respond")
builder.add_edge("modify", "respond")
builder.add_edge("ask", END)
builder.add_edge("respond", END)

graph = builder.compile(checkpointer=InMemorySaver())

if __name__ == "__main__":
    for thread, msg in [
        ("t1", "Planea un viaje de 3 dias a Roma"),         # new_plan
        ("t2", "Quiero un viaje"),                          # missing_info
        ("t3", "¿Cuál es la mejor época para ir a Japón?"), # chat
    ]:
        cfg = {"configurable": {"thread_id": thread}}
        r = graph.invoke({"messages": [HumanMessage(content=msg)]}, config=cfg)
        print(thread, "→", r["intent"], "|", r["messages"][-1].content)