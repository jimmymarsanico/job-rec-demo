"use client";

import { useState } from "react";

interface JudgeJob {
  title: string;
  company: string;
  city: string;
  country: string;
  category: string;
  jobType: string;
  experience: string;
  workplace: string;
}

interface AnalyzeButtonProps {
  sourceJob: JudgeJob;
  baselineRecs: JudgeJob[];
  enhancedRecs: JudgeJob[];
}

interface Verdict {
  winner: "baseline" | "enhanced" | "tie";
  reasoning: string;
  shownFirst: "baseline" | "enhanced";
}

const WINNER_STYLE: Record<Verdict["winner"], { label: string; className: string }> = {
  enhanced: {
    label: "Judge picked B · Enhanced",
    className: "bg-emerald-600 text-white",
  },
  baseline: {
    label: "Judge picked A · Baseline",
    className: "bg-blue-600 text-white",
  },
  tie: { label: "Judge called it a tie", className: "bg-gray-600 text-white" },
};

const SPARK_PATH =
  "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z";

export default function AnalyzeButton({
  sourceJob,
  baselineRecs,
  enhancedRecs,
}: AnalyzeButtonProps) {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    setVerdict(null);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sourceJob, baselineRecs, enhancedRecs }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
      setVerdict(data as Verdict);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-8">
      {!verdict && !loading && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleAnalyze}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium text-sm"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={SPARK_PATH} />
            </svg>
            Run blind LLM judge
          </button>
          <span className="text-xs text-gray-500 max-w-md">
            Sends both lists to an LLM without saying which model produced which, in randomised
            order, and asks it to pick the more useful set.
          </span>
        </div>
      )}

      {loading && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-purple-700">Judging both lists blind...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={handleAnalyze}
            className="mt-2 text-sm text-red-600 underline hover:text-red-800"
          >
            Try again
          </button>
        </div>
      )}

      {verdict && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-5">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-purple-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={SPARK_PATH} />
              </svg>
              <h3 className="font-bold text-purple-900">Blind LLM judge</h3>
            </div>
            <span
              className={`text-xs font-bold rounded-full px-3 py-1 ${WINNER_STYLE[verdict.winner].className}`}
            >
              {WINNER_STYLE[verdict.winner].label}
            </span>
            <span className="text-xs text-purple-500">
              ({verdict.shownFirst === "enhanced" ? "Enhanced" : "Baseline"} was shown as List 1
              this run)
            </span>
          </div>
          <div className="text-sm text-purple-900 leading-relaxed whitespace-pre-wrap">
            {verdict.reasoning}
          </div>
          <button
            onClick={handleAnalyze}
            className="mt-3 text-xs text-purple-600 underline hover:text-purple-800"
          >
            Re-run (order is randomised again)
          </button>
        </div>
      )}
    </div>
  );
}
