"use client";

import { CopilotChat, useAgent, useComponent } from "@copilotkit/react-core/v2";
import {
  TripSummaryCard,
  tripSummaryPropsSchema,
} from "./components/TripSummaryCard";
import styles from "./page.module.css";

type Activity = {
  time: string;
  title: string;
  description: string;
  location: string;
};

type DayPlan = {
  day: number;
  summary: string;
  activities: Activity[];
};

export default function Page() {
  const { agent } = useAgent({ agentId: "itinerary_agent" });

  useComponent({
    name: "show_trip_summary",
    description:
      "Call this tool every time you create or modify an itinerary, to show the user a trip summary card.",
    parameters: tripSummaryPropsSchema,
    render: TripSummaryCard,
  });

  const itinerary = (agent.state.itinerary as DayPlan[] | undefined) ?? [];
  const hasItinerary = itinerary.length > 0;
  const city = (agent.state.city as string | undefined) ?? "";
  const numDays = (agent.state.num_days as number | undefined) ?? 0;

  const updateItinerary = (mutate: (draft: DayPlan[]) => void) => { 
    const prev = (agent.state.itinerary as DayPlan[] | undefined) ?? [];
    const next = structuredClone(prev);
    mutate(next); agent.setState({ itinerary: next });
  };

  const removeActivity = (dayIdx: number, actIdx: number) =>
  updateItinerary((draft) => {
    draft[dayIdx].activities.splice(actIdx, 1);
  });

  return (
    <div className={styles.root}>
      <div className={styles.panel}>
        <h1 className={styles.heading}>
          {hasItinerary ? `${numDays}-Day Itinerary: ${city}` : "Trip Planner"}
        </h1>

        {itinerary.map((d, dayIdx) => (
          <div key={d.day} className={styles.day}>
            <h2 className={styles.dayHeading}>
              Día {d.day} <span className={styles.daySummary}>— {d.summary}</span>
            </h2>
            {d.activities?.map((a, actIdx) => (
              <div key={actIdx} className={styles.activity}>
                <div className={styles.activityHeader}>
                  <span className={styles.time}>{a.time}</span>
                  <span className={styles.activityTitle}>{a.title}</span>
                  <span className={styles.location}>📍 {a.location}</span>
                  <button
                    onClick={() => removeActivity(dayIdx, actIdx)}
                    className={styles.removeBtn}
                    title={`Quitar ${a.title}`}
                  >
                    ✕
                  </button>
                </div>
                <p className={styles.description}>{a.description}</p>
              </div>
            ))}
          </div>
        ))}     
      </div>
      <div className={styles.chat}>
        <CopilotChat
          agentId="itinerary_agent"
          labels={{ chatInputPlaceholder: "¿A dónde quieres viajar?" }}
          welcomeScreen={({ input }) => (
            <div className={styles.welcome}>
              <p className={styles.welcomeTitle}>¿A dónde te gustaría ir?</p>
              {input}
            </div>
          )}
        />
      </div>
    </div>
  );
}