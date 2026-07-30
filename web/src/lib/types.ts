export type Workplace = "Remote" | "Hybrid" | "On-site";

export interface Job {
  id: string;
  title: string;
  company: string;
  city: string;
  state: string;
  country: string;
  remote: boolean;
  workplace: Workplace;
  description: string;
  category: string;
  jobType: string;
  experience: string;
  education: string;
  department: string;
  team: string;
  url: string;
  date: string;
  source: string;
}

/** A job without its (large) HTML description — used for list views. */
export type JobSummary = Omit<Job, "description">;

export interface Recommendation {
  id: string;
  score: number;
}

export type RecommendationMap = Record<string, Recommendation[]>;

export interface Meta {
  generatedAt: string;
  jobCount: number;
  companyCount: number;
  feedSize: number;
  topN: number;
  weights: Record<string, number>;
  metrics: {
    baseline: Record<string, number>;
    enhanced: Record<string, number>;
  };
  workplaceMix: Record<string, number>;
  meanOverlap: number;
  zeroOverlapShare: number;
}

/** Drop the HTML description so a job can be passed to list/card components. */
export function toSummary(job: Job): JobSummary {
  const { description: _description, ...summary } = job;
  return summary;
}

/** Seniority ordered low to high, matching SENIORITY_RANK in the notebook. */
export const SENIORITY_ORDER = [
  "Internship",
  "Entry level",
  "Mid level",
  "Senior",
  "Staff / Principal",
  "Director",
  "Executive",
] as const;

export function seniorityRank(level: string): number {
  const i = SENIORITY_ORDER.indexOf(level as (typeof SENIORITY_ORDER)[number]);
  return i === -1 ? 2 : i;
}

/**
 * Human-readable location. `city` is the placeholder "Unknown" for postings that only
 * name a country and "Remote" for remote roles with no anchor office, so fall through
 * to the most specific real value available.
 */
export function formatLocation(job: JobSummary | Job): string {
  const country = job.country === "CA" ? "Canada" : "United States";
  const parts: string[] = [];
  if (job.city && job.city !== "Unknown" && job.city !== "Remote") parts.push(job.city);
  if (job.state && job.state !== "Unknown") parts.push(job.state);
  if (parts.length === 0) return country;
  return `${parts.join(", ")}, ${job.country}`;
}
