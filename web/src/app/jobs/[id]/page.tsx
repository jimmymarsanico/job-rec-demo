import { notFound } from "next/navigation";
import Link from "next/link";
import {
  getJobs,
  getJobById,
  getJobSummariesByIds,
  getBaselineRecs,
  getWeightedRecs,
} from "@/lib/data";
import { JobSummary, formatLocation, toSummary } from "@/lib/types";
import Badge, { workplaceVariant } from "@/components/Badge";
import RecommendationPanel from "@/components/RecommendationPanel";
import AnalyzeButton from "@/components/AnalyzeButton";
import JobDescription from "@/components/JobDescription";

const SOURCE_LABEL: Record<string, string> = {
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
};

export async function generateStaticParams() {
  return getJobs().map((job) => ({ id: job.id }));
}

interface JobPageProps {
  params: Promise<{ id: string }>;
}

export default async function JobPage({ params }: JobPageProps) {
  const { id } = await params;
  const job = getJobById(id);
  if (!job) return notFound();

  const baseRecs = getBaselineRecs()[id] || [];
  const wtdRecs = getWeightedRecs()[id] || [];

  // Only the handful of jobs referenced by the two recommendation lists.
  const recJobs = getJobSummariesByIds([
    ...baseRecs.map((r) => r.id),
    ...wtdRecs.map((r) => r.id),
  ]);
  const recMap = new Map(recJobs.map((j) => [j.id, j]));

  const baseRecIds = new Set(baseRecs.map((r) => r.id));
  const wtdRecIds = new Set(wtdRecs.map((r) => r.id));
  const overlap = [...baseRecIds].filter((rid) => wtdRecIds.has(rid)).length;

  const sourceSummary = toSummary(job);

  const judgePayload = (recs: typeof baseRecs) =>
    recs
      .map((r) => recMap.get(r.id))
      .filter((j): j is JobSummary => Boolean(j))
      .map((j) => ({
        title: j.title,
        company: j.company,
        city: j.city,
        country: j.country,
        category: j.category,
        jobType: j.jobType,
        experience: j.experience,
        workplace: j.workplace,
      }));

  return (
    <div>
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 mb-6"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to all jobs
      </Link>

      {/* Job header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
            <p className="text-lg text-gray-600 mt-1">{job.company}</p>
            <div className="flex items-center gap-2 mt-2 text-gray-500">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>{formatLocation(job)}</span>
              {job.department && (
                <span className="text-sm text-gray-400">
                  · {job.department}
                  {job.team && job.team !== job.department ? ` / ${job.team}` : ""}
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <Badge variant="blue">{job.category}</Badge>
              <Badge variant="purple">{job.experience}</Badge>
              <Badge variant={workplaceVariant(job.workplace)}>{job.workplace}</Badge>
              <Badge variant="green">{job.jobType}</Badge>
              {job.education !== "Not Specified" && (
                <Badge variant="orange">{job.education}</Badge>
              )}
            </div>
          </div>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium text-sm shrink-0"
          >
            Apply on {SOURCE_LABEL[job.source] ?? "the job board"}
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>

        <div className="mt-6 pt-6 border-t border-gray-100">
          <JobDescription html={job.description} />
        </div>
      </div>

      {/* Recommendations */}
      <div className="mb-4">
        <h2 className="text-xl font-bold text-gray-900">Similar jobs: two models, same input</h2>
        <p className="text-gray-600 mt-1 text-sm">
          The two models share <strong>{overlap} of {baseRecs.length}</strong> picks for this job.
          A yellow bar marks a pick only that model made; <span className="font-mono">≠</span> marks
          an attribute that disagrees with the job above.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <RecommendationPanel
          label="A"
          title="Baseline"
          description="TF-IDF cosine similarity on the job title alone. Nothing else."
          sourceJob={sourceSummary}
          recommendations={baseRecs}
          jobs={recJobs}
          accent="blue"
          otherRecIds={wtdRecIds}
        />
        <RecommendationPanel
          label="B"
          title="Enhanced"
          description="Seven weighted features — description 32%, title 20%, job family 16%, seniority 12%, location 10%, workplace 6%, employment type 4% — then capped at one role per employer."
          sourceJob={sourceSummary}
          recommendations={wtdRecs}
          jobs={recJobs}
          accent="emerald"
          otherRecIds={baseRecIds}
        />
      </div>

      <AnalyzeButton
        sourceJob={{
          title: job.title,
          company: job.company,
          city: job.city,
          country: job.country,
          category: job.category,
          jobType: job.jobType,
          experience: job.experience,
          workplace: job.workplace,
        }}
        baselineRecs={judgePayload(baseRecs)}
        enhancedRecs={judgePayload(wtdRecs)}
      />

      <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
        <div className="font-semibold text-gray-800 mb-2">Reading this comparison</div>
        <ul className="space-y-1.5">
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-4 bg-yellow-400 rounded shrink-0 mt-0.5" />
            Picked by only one of the two models — these are where the models actually disagree.
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-4 bg-gray-200 rounded shrink-0 mt-0.5" />
            Picked by both models.
          </li>
          <li>
            The <strong>Agreement</strong> row counts how many of each model&apos;s three picks share
            this job&apos;s family, sit within one seniority level, and share its workplace type —
            plus how many distinct employers it surfaced.
          </li>
          <li>
            Similarity scores are each model&apos;s own and are computed on different scales, so a
            0.7 from A and a 0.7 from B do not mean the same thing.{" "}
            <span className="text-gray-500">
              The notebook compares them on one shared yardstick instead.
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
