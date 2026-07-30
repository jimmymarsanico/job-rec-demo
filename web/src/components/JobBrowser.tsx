"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { JobSummary, formatLocation } from "@/lib/types";
import Badge, { workplaceVariant } from "./Badge";

interface JobBrowserProps {
  jobs: JobSummary[];
}

const PAGE_SIZE = 20;
const WORKPLACES = ["Remote", "Hybrid", "On-site"];

export default function JobBrowser({ jobs }: JobBrowserProps) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [workplace, setWorkplace] = useState("all");
  const [experience, setExperience] = useState("all");
  const [country, setCountry] = useState("all");
  const [page, setPage] = useState(0);

  const categories = useMemo(
    () => [...new Set(jobs.map((j) => j.category))].sort(),
    [jobs]
  );
  const experiences = useMemo(
    () => [...new Set(jobs.map((j) => j.experience))].sort(),
    [jobs]
  );

  const filtered = useMemo(() => {
    let result = jobs;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q) ||
          j.city.toLowerCase().includes(q)
      );
    }
    if (category !== "all") result = result.filter((j) => j.category === category);
    if (workplace !== "all") result = result.filter((j) => j.workplace === workplace);
    if (experience !== "all") result = result.filter((j) => j.experience === experience);
    if (country !== "all") result = result.filter((j) => j.country === country);
    return result;
  }, [jobs, search, category, workplace, experience, country]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const safePage = Math.min(page, Math.max(0, totalPages - 1));
  const paginated = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  const onFilter = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setPage(0);
  };

  const selectClass =
    "px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none";

  return (
    <div>
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-col lg:flex-row gap-3">
          <div className="flex-1 relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search by title, company, or city..."
              value={search}
              onChange={(e) => onFilter(setSearch)(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
            />
          </div>

          <select
            value={category}
            onChange={(e) => onFilter(setCategory)(e.target.value)}
            className={selectClass}
          >
            <option value="all">All job families</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <select
            value={workplace}
            onChange={(e) => onFilter(setWorkplace)(e.target.value)}
            className={selectClass}
          >
            <option value="all">Remote / hybrid / on-site</option>
            {WORKPLACES.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>

          <select
            value={experience}
            onChange={(e) => onFilter(setExperience)(e.target.value)}
            className={selectClass}
          >
            <option value="all">All levels</option>
            {experiences.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>

          <select
            value={country}
            onChange={(e) => onFilter(setCountry)(e.target.value)}
            className={selectClass}
          >
            <option value="all">US &amp; Canada</option>
            <option value="US">United States</option>
            <option value="CA">Canada</option>
          </select>
        </div>

        <div className="mt-3 text-sm text-gray-500">
          Showing {paginated.length} of {filtered.length.toLocaleString()} jobs
          {search && ` matching "${search}"`}
        </div>
      </div>

      <div className="space-y-2">
        {paginated.map((job) => (
          <Link key={job.id} href={`/jobs/${job.id}`} className="block">
            <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition-all">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-gray-900">{job.title}</h3>
                  <p className="text-sm text-gray-600 mt-0.5">{job.company}</p>
                  <div className="flex items-center gap-1.5 mt-1.5 text-sm text-gray-500">
                    <svg
                      className="w-4 h-4 shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                    </svg>
                    <span>{formatLocation(job)}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 shrink-0 justify-end max-w-[55%]">
                  <Badge variant="blue">{job.category}</Badge>
                  <Badge variant="purple">{job.experience}</Badge>
                  <Badge variant={workplaceVariant(job.workplace)}>{job.workplace}</Badge>
                </div>
              </div>
            </div>
          </Link>
        ))}

        {filtered.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-10 text-center text-gray-500">
            No jobs match those filters.
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(0, safePage - 1))}
            disabled={safePage === 0}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-sm text-gray-600">
            Page {safePage + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))}
            disabled={safePage >= totalPages - 1}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
