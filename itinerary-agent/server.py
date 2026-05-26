from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from agent import graph

app = FastAPI()

# Permite que Next.js (puerto 3000) llame al backend en dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = LangGraphAgent(
    name="itinerary_agent",
    description="Plans and modifies travel itineraries through conversation",
    graph=graph,
)

# Monta el endpoint AG-UI en /agent
add_langgraph_fastapi_endpoint(
    app,
    agent,
    path="/agent",
)