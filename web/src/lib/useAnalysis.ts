"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type AnalysisResult, type TraceEvent } from "./api";

export type StepId = "read" | "redact" | "match" | "verify";
export const STEP_ORDER: StepId[] = ["read", "redact", "match", "verify"];

export interface OcrCheck {
  field: "salary";
  currency: string;
  value: string;
  confidence: number;
}

export type JobStatus = "idle" | "starting" | "running" | "waiting" | "done" | "error";

export interface AnalysisState {
  jobId: string | null;
  name: string | null;
  status: JobStatus;
  stepsDone: StepId[];
  events: TraceEvent[];
  ocrCheck: OcrCheck | null;
  confirmed: boolean;
  result: AnalysisResult | null;
  error: string | null;
}

const INITIAL: AnalysisState = {
  jobId: null,
  name: null,
  status: "idle",
  stepsDone: [],
  events: [],
  ocrCheck: null,
  confirmed: false,
  result: null,
  error: null,
};

/**
 * Runs one analysis job: starts it, follows the agent trace over SSE, surfaces the
 * human salary check, and loads the final result. Pass `jobId` to attach to an
 * existing job (e.g. the Counsel page opened from a link).
 */
export function useAnalysis(existingJobId?: string) {
  const [state, setState] = useState<AnalysisState>(INITIAL);
  const source = useRef<EventSource | null>(null);

  const close = () => {
    source.current?.close();
    source.current = null;
  };

  const loadResult = useCallback(async (jobId: string) => {
    try {
      const result = await api.result(jobId);
      setState((s) => ({ ...s, status: "done", result, stepsDone: STEP_ORDER }));
    } catch (e) {
      setState((s) => ({ ...s, status: "error", error: (e as Error).message }));
    }
  }, []);

  const follow = useCallback(
    (jobId: string) => {
      close();
      const es = new EventSource(api.eventsUrl(jobId), { withCredentials: true });
      source.current = es;
      es.addEventListener("trace", (msg) => {
        const ev = JSON.parse((msg as MessageEvent).data) as TraceEvent;
        setState((s) => {
          const next = { ...s, events: [...s.events, ev] };
          if (ev.type === "step") next.stepsDone = Array.from(new Set([...s.stepsDone, ev.data.step as StepId]));
          if (ev.type === "ocr_check") {
            next.ocrCheck = ev.data as unknown as OcrCheck;
            next.status = "waiting";
          }
          if (ev.type === "agent_start" && s.status === "waiting" && ev.agent === "Wage Calculator") next.status = "running";
          if (ev.type === "error") {
            next.status = "error";
            next.error = ev.message;
          }
          return next;
        });
      });
      es.addEventListener("end", (msg) => {
        close();
        const end = JSON.parse((msg as MessageEvent).data) as { status: string; error: string | null };
        if (end.status === "done") void loadResult(jobId);
        else setState((s) => ({ ...s, status: "error", error: end.error ?? "Analysis failed" }));
      });
      es.onerror = () => {
        // The stream closes normally after "end"; otherwise fall back to checking the job.
        if (!source.current) return;
        close();
        api
          .status(jobId)
          .then((st) => {
            if (st.status === "done") void loadResult(jobId);
            else if (st.status === "error") setState((s) => ({ ...s, status: "error", error: st.error ?? "Analysis failed" }));
            else setTimeout(() => follow(jobId), 1500);
          })
          .catch(() => setState((s) => ({ ...s, status: "error", error: "offline" })));
      };
    },
    [loadResult],
  );

  const start = useCallback(
    async (input: { file: File; destination?: string | null; policy?: File | null } | { sampleId: string }) => {
      close();
      setState({ ...INITIAL, status: "starting", name: "file" in input ? input.file.name : input.sampleId });
      try {
        const job = "file" in input ? await api.analyzeFile(input.file, input.destination, input.policy) : await api.analyzeSample(input.sampleId);
        setState((s) => ({ ...s, jobId: job.job_id, name: job.name, status: "running" }));
        follow(job.job_id);
        return job.job_id;
      } catch (e) {
        const msg = (e as Error).message;
        setState((s) => ({ ...s, status: "error", error: msg.includes("Failed to fetch") ? "offline" : msg }));
        return null;
      }
    },
    [follow],
  );

  const confirm = useCallback(
    async (value: string) => {
      if (!state.jobId) return;
      await api.confirm(state.jobId, value);
      setState((s) => ({ ...s, confirmed: true, status: s.status === "waiting" ? "running" : s.status }));
    },
    [state.jobId],
  );

  const reset = useCallback(() => {
    close();
    setState(INITIAL);
  }, []);

  useEffect(() => {
    if (!existingJobId) return;
    let cancelled = false;
    api
      .status(existingJobId)
      .then((st) => {
        if (cancelled) return;
        setState((s) => ({ ...s, jobId: existingJobId, status: st.status === "done" ? "running" : (st.status as JobStatus) }));
        if (st.status === "done") void loadResult(existingJobId);
        else follow(existingJobId);
      })
      .catch((e) => !cancelled && setState((s) => ({ ...s, status: "error", error: (e as Error).message })));
    return () => {
      cancelled = true;
      close();
    };
  }, [existingJobId, follow, loadResult]);

  useEffect(() => close, []);

  return { ...state, start, confirm, reset };
}
