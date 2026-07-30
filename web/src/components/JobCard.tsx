import Link from "next/link";
import { JobSummary, formatLocation } from "@/lib/types";
import Badge, { workplaceVariant } from "./Badge";

interface JobCardProps {
  job: JobSummary;
  compact?: boolean;
  /** Model-internal similarity score, shown on recommendation cards. */
  score?: number;
  /** Attribute agreement with the job the visitor is currently viewing. */
  match?: {
    family: boolean;
    seniority: boolean;
    workplace: boolean;
  };
}

export default function JobCard({ job, compact = false, score, match }: JobCardProps) {
  return (
    <Link href={`/jobs/${job.id}`} className="block">
      <div className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition-all bg-white h-full">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 leading-snug">{job.title}</h3>
            <p className="text-sm text-gray-600 mt-0.5">{job.company}</p>
          </div>
          {score !== undefined && (
            <span
              className="shrink-0 font-mono text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5"
              title="This model's own similarity score. Not comparable across models."
            >
              {score.toFixed(3)}
            </span>
          )}
        </div>

        <div className="mt-2 flex items-center gap-1.5 text-sm text-gray-500">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span className="truncate">{formatLocation(job)}</span>
        </div>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Badge
            variant={match && !match.family ? "default" : "blue"}
            title={match ? (match.family ? "Same job family as the job you're viewing" : "Different job family") : undefined}
          >
            {match && !match.family && "≠ "}
            {job.category}
          </Badge>
          <Badge
            variant={match && !match.seniority ? "default" : "purple"}
            title={match ? (match.seniority ? "Within one seniority level" : "More than one level apart") : undefined}
          >
            {match && !match.seniority && "≠ "}
            {job.experience}
          </Badge>
          <Badge
            variant={match && !match.workplace ? "default" : workplaceVariant(job.workplace)}
            title={match ? (match.workplace ? "Same workplace type" : "Different workplace type") : undefined}
          >
            {match && !match.workplace && "≠ "}
            {job.workplace}
          </Badge>
          {!compact && job.jobType !== "Full-time" && (
            <Badge variant="green">{job.jobType}</Badge>
          )}
        </div>
      </div>
    </Link>
  );
}
