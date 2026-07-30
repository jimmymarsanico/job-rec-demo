import { Job, JobSummary, Meta, RecommendationMap } from "./types";
import fs from "fs";
import path from "path";

function readJsonFile<T>(filename: string): T {
  const filePath = path.join(process.cwd(), "public", "data", filename);
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as T;
}

let _jobs: Job[] | null = null;
let _jobIndex: Map<string, Job> | null = null;
let _summaries: JobSummary[] | null = null;
let _baselineRecs: RecommendationMap | null = null;
let _weightedRecs: RecommendationMap | null = null;
let _meta: Meta | null = null;

export function getJobs(): Job[] {
  if (!_jobs) {
    _jobs = readJsonFile<Job[]>("jobs.json");
    _jobIndex = new Map(_jobs.map((j) => [j.id, j]));
  }
  return _jobs;
}

/**
 * Jobs with the HTML description stripped out. The full jobs.json is ~8 MB because it
 * carries every posting's markup, and serializing that into the browse page's payload
 * would make the first load unusable. List views only need the metadata.
 */
export function getJobSummaries(): JobSummary[] {
  if (!_summaries) {
    _summaries = getJobs().map(({ description: _drop, ...rest }) => rest);
  }
  return _summaries;
}

export function getBaselineRecs(): RecommendationMap {
  if (!_baselineRecs) {
    _baselineRecs = readJsonFile<RecommendationMap>("recs_baseline.json");
  }
  return _baselineRecs;
}

export function getWeightedRecs(): RecommendationMap {
  if (!_weightedRecs) {
    _weightedRecs = readJsonFile<RecommendationMap>("recs_weighted.json");
  }
  return _weightedRecs;
}

export function getMeta(): Meta {
  if (!_meta) {
    _meta = readJsonFile<Meta>("meta.json");
  }
  return _meta;
}

export function getJobById(id: string): Job | undefined {
  getJobs();
  return _jobIndex!.get(id);
}

export function getJobSummariesByIds(ids: string[]): JobSummary[] {
  const wanted = new Set(ids);
  return getJobSummaries().filter((j) => wanted.has(j.id));
}
