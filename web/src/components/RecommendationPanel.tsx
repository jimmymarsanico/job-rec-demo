import { JobSummary, Recommendation, seniorityRank } from "@/lib/types";
import JobCard from "./JobCard";

interface RecommendationPanelProps {
  label: string;
  title: string;
  description: string;
  sourceJob: JobSummary;
  recommendations: Recommendation[];
  jobs: JobSummary[];
  accent: "blue" | "emerald";
  otherRecIds: Set<string>;
}

const ACCENT = {
  blue: { border: "border-blue-500", chip: "bg-blue-600", text: "text-blue-700" },
  emerald: { border: "border-emerald-500", chip: "bg-emerald-600", text: "text-emerald-700" },
};

export default function RecommendationPanel({
  label,
  title,
  description,
  sourceJob,
  recommendations,
  jobs,
  accent,
  otherRecIds,
}: RecommendationPanelProps) {
  const jobMap = new Map(jobs.map((j) => [j.id, j]));
  const a = ACCENT[accent];
  const srcRank = seniorityRank(sourceJob.experience);

  const resolved = recommendations
    .map((rec) => ({ rec, job: jobMap.get(rec.id) }))
    .filter((r): r is { rec: Recommendation; job: JobSummary } => Boolean(r.job));

  // Per-job scorecard: how well this model's picks agree with the job being viewed.
  const matches = resolved.map(({ job }) => ({
    family: job.category === sourceJob.category,
    seniority: Math.abs(seniorityRank(job.experience) - srcRank) <= 1,
    workplace: job.workplace === sourceJob.workplace,
  }));
  const tally = {
    family: matches.filter((m) => m.family).length,
    seniority: matches.filter((m) => m.seniority).length,
    workplace: matches.filter((m) => m.workplace).length,
    companies: new Set(resolved.map(({ job }) => job.company)).size,
  };
  const n = resolved.length || 1;

  return (
    <div className={`border-t-4 ${a.border} rounded-lg bg-white shadow-sm flex flex-col`}>
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className={`${a.chip} text-white text-xs font-bold rounded px-1.5 py-0.5`}>
            {label}
          </span>
          <h3 className="font-bold text-lg text-gray-900">{title}</h3>
        </div>
        <p className="text-sm text-gray-500 mt-1.5">{description}</p>
      </div>

      <div className="p-4 space-y-3 flex-1">
        {resolved.map(({ rec, job }, i) => {
          const isShared = otherRecIds.has(rec.id);
          return (
            <div key={rec.id} className="relative pl-3">
              <div
                className={`absolute left-0 top-0 bottom-0 w-1.5 rounded ${
                  isShared ? "bg-gray-200" : "bg-yellow-400"
                }`}
                title={isShared ? "Both models picked this" : "Only this model picked this"}
              />
              <JobCard job={job} compact score={rec.score} match={matches[i]} />
            </div>
          );
        })}
      </div>

      <div className="px-4 py-3 border-t border-gray-100 bg-gray-50 rounded-b-lg">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Agreement with this job
        </div>
        <div className="grid grid-cols-4 gap-2 text-center">
          {[
            ["Family", tally.family, n],
            ["Seniority", tally.seniority, n],
            ["Workplace", tally.workplace, n],
            ["Employers", tally.companies, n],
          ].map(([labelText, value, total]) => (
            <div key={labelText as string}>
              <div className={`text-lg font-bold ${a.text}`}>
                {value as number}/{total as number}
              </div>
              <div className="text-[11px] text-gray-500 leading-tight">{labelText}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
