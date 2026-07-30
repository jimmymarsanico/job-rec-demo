import { getJobSummaries, getMeta } from "@/lib/data";
import JobBrowser from "@/components/JobBrowser";
import ModelScorecard from "@/components/ModelScorecard";

export default function Home() {
  const jobs = getJobSummaries();
  const meta = getMeta();

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">
          {jobs.length.toLocaleString()} tech jobs, two recommenders
        </h2>
        <p className="text-gray-600 mt-1">
          Software, data, ML, product and design roles at {meta.companyCount} US and Canadian
          companies, with a real mix of remote, hybrid and on-site. Open any job to see a title-only
          baseline and a seven-feature model recommend side by side.
        </p>
      </div>

      <ModelScorecard meta={meta} />

      <JobBrowser jobs={jobs} />
    </div>
  );
}
