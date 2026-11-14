"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { rehearsalApi, type CoachHint, type RehearsalSession, type RehearsalSetup, type TraceEvent, type WorkerAction } from "./api";

export type RehearsalStatus = "idle" | "starting" | "dalal" | "yourTurn" | "coaching" | "debriefing" | "done" | "error";

export interface RehearsalState {
  id: string | null;
  status: RehearsalStatus;
  session: RehearsalSession | null;
  /** hints that arrived over SSE for the turn being coached, before the session is reloaded */
  liveHints: CoachHint[];
  maxTurns: number;
  minTurns: number;
  error: string | null;
}

const INITIAL: RehearsalState = { id: null, status: "idle", session: null, liveHints: [], maxTurns: 10, minTurns: 6, error: null };

function statusOf(s: RehearsalSession): RehearsalStatus {
  if (s.status === "done") return "done";
  const last = s.turns[s.turns.length - 1];
  if (!last) return "dalal";
  return !last.worker_reply && last.action === "none" && !last.hints.length ? "yourTurn" : "coaching";
}

/**
 * One rehearsal: creates the session, follows its trace over SSE (the same stream format as an analysis), and
 * reloads the session whenever a step finishes. Coach hints are shown as each one arrives.
 */
export function useRehearsal() {
  const [state, setState] = useState<RehearsalState>(INITIAL);
  const source = useRef<EventSource | null>(null);

  const close = () => {
    source.current?.close();
    source.current = null;
  };

  const reload = useCallback(async (id: string) => {
    try {
      const session = await rehearsalApi.get(id);
      setState((s) => (s.id === id ? { ...s, session, liveHints: [], status: statusOf(session) } : s));
    } catch (e) {
      setState((s) => ({ ...s, status: "error", error: (e as Error).message }));
    }
  }, []);

  const follow = useCallback(
    (id: string) => {
      close();
      const es = new EventSource(rehearsalApi.eventsUrl(id), { withCredentials: true });
      source.current = es;
      es.addEventListener("trace", (msg) => {
        const ev = JSON.parse((msg as MessageEvent).data) as TraceEvent;
        if (ev.type === "rehearsal_started") {
          setState((s) => ({ ...s, maxTurns: Number(ev.data.max_turns) || s.maxTurns, minTurns: Number(ev.data.min_turns) || s.minTurns }));
        } else if (ev.type === "worker_turn") {
          setState((s) => ({ ...s, status: "coaching", liveHints: [] }));
        } else if (ev.type === "coach_hint") {
          const hint = ev.data.hint as CoachHint;
          setState((s) => ({ ...s, liveHints: [...s.liveHints.filter((h) => h.member !== hint.member), hint] }));
        } else if (ev.type === "dalal_line" || ev.type === "turn_done" || ev.type === "record_ready") {
          void reload(id);
        } else if (ev.type === "debrief") {
          setState((s) => ({ ...s, status: "debriefing" }));
        } else if (ev.type === "error") {
          setState((s) => ({ ...s, error: ev.message }));
          void reload(id);
        }
      });
      es.addEventListener("end", () => {
        close();
        void reload(id);
      });
      es.onerror = () => {
        // EventSource reconnects by itself with Last-Event-ID; only a closed stream with no session is an error
        if (es.readyState === EventSource.CLOSED) void reload(id);
      };
    },
    [reload],
  );

  const start = useCallback(
    async (setup: RehearsalSetup) => {
      close();
      setState({ ...INITIAL, status: "starting" });
      try {
        const { id } = await rehearsalApi.create(setup);
        setState((s) => ({ ...s, id, status: "dalal" }));
        follow(id);
      } catch (e) {
        setState((s) => ({ ...s, status: "error", error: (e as Error).message }));
      }
    },
    [follow],
  );

  const reply = useCallback(
    async (text: string, action: WorkerAction = "none") => {
      const id = state.id;
      if (!id) return;
      setState((s) => ({ ...s, status: "coaching", error: null, liveHints: [] }));
      try {
        await rehearsalApi.turn(id, text, action);
      } catch (e) {
        setState((s) => ({ ...s, error: (e as Error).message }));
        void reload(id);
      }
    },
    [state.id, reload],
  );

  const finish = useCallback(async () => {
    const id = state.id;
    if (!id) return;
    setState((s) => ({ ...s, status: "debriefing" }));
    try {
      await rehearsalApi.finish(id);
    } catch (e) {
      setState((s) => ({ ...s, error: (e as Error).message }));
    }
  }, [state.id]);

  const setSession = useCallback((session: RehearsalSession) => setState((s) => ({ ...s, session })), []);

  const reset = useCallback(() => {
    close();
    setState(INITIAL);
  }, []);

  useEffect(() => close, []);

  return { ...state, start, reply, finish, reset, setSession };
}
