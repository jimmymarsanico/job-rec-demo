import { Meta } from "@/lib/types";

/** Metrics worth showing on stage, in the order they tell the story. */
const SHOWN: { key: string; label: string; hint: string; higherIsBetter: boolean }[] = [
  {
    key: "Same job family",
    label: "Same job family",
    hint: "Share of recommendations in the same job family as the source job",
    higherIsBetter: true,
  },
  {
    key: "Same workplace type",
    label: "Workplace match",
    hint: "Share of recommendations with the same remote / hybrid / on-site type",
    higherIsBetter: true,
  },
  {
    key: "Seniority within 1 level",
    label: "Seniority within 1",
    hint: "Share of recommendations within one seniority level of the source job",
    higherIsBetter: true,
  },
  {
    key: "Relevance (desc-space cosine)",
    label: "Relevance",
    hint: "Mean cosine similarity in description TF-IDF space — the shared yardstick neither model ranks by",
    higherIsBetter: true,
  },
  {
    key: "Catalog coverage",
    label: "Catalog coverage",
    hint: "Share of the catalog that appears in at least one recommendation list",
    higherIsBetter: true,
  },
  {
    key: "Intra-list diversity",
    label: "List diversity",
    hint: "1 − mean pairwise similarity within each list of three",
    higherIsBetter: true,
  },
];

/** Direction of "better" for every metric the notebook exports. */
const HIGHER_IS_BETTER: Record<string, boolean> = {
  "Relevance (desc-space cosine)": true,
  "Intra-list diversity": true,
  "Same job family": true,
  "Seniority within 1 level": true,
  "Same country": true,
  "Same workplace type": true,
  "Identical title (echo)": false,
  "Same company": false,
  "Catalog coverage": true,
};

function countEnhancedWins(meta: Meta): { wins: number; total: number } {
  const keys = Object.keys(meta.metrics.baseline).filter((k) => k in HIGHER_IS_BETTER);
  const wins = keys.filter((k) => {
    const a = meta.metrics.baseline[k];
    const b = meta.metrics.enhanced[k];
    return HIGHER_IS_BETTER[k] ? b > a : b < a;
  }).length;
  return { wins, total: keys.length };
}

function fmt(key: string, value: number): string {
  return key === "Relevance (desc-space cosine)" || key === "Intra-list diversity"
    ? value.toFixed(3)
    : `${Math.round(value * 100)}%`;
}

export default function ModelScorecard({ meta }: { meta: Meta }) {
  const { baseline, enhanced } = meta.metrics;
  const { wins, total } = countEnhancedWins(meta);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
      <div className="px-4 py-3 border-b border-gray-100 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="font-bold text-gray-900">Offline scorecard</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Measured over all {meta.jobCount.toLocaleString()} jobs in the notebook. Enhanced wins{" "}
            {wins} of {total} metrics.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500" /> A · Baseline
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> B · Enhanced
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-y md:divide-y-0 divide-x divide-gray-100">
        {SHOWN.map(({ key, label, hint, higherIsBetter }) => {
          const a = baseline[key];
          const b = enhanced[key];
          if (a === undefined || b === undefined) return null;
          const enhancedWins = higherIsBetter ? b > a : b < a;
          const pct = (v: number) => Math.max(2, Math.min(100, v * 100));
          return (
            <div key={key} className="p-3" title={hint}>
              <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide leading-tight h-7">
                {label}
              </div>
              <div className="mt-1 space-y-1.5">
                <div>
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>A</span>
                    <span className="font-mono">{fmt(key, a)}</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded mt-0.5">
                    <div className="h-1.5 bg-blue-500 rounded" style={{ width: `${pct(a)}%` }} />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>B</span>
                    <span className={`font-mono ${enhancedWins ? "font-bold text-emerald-700" : ""}`}>
                      {fmt(key, b)}
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded mt-0.5">
                    <div className="h-1.5 bg-emerald-500 rounded" style={{ width: `${pct(b)}%` }} />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-100 text-xs text-gray-500">
        {meta.companyCount} companies · {meta.feedSize.toLocaleString()} postings scraped from
        Greenhouse, Lever and Ashby boards · sampled to {meta.jobCount.toLocaleString()} ·{" "}
        {Math.round(meta.zeroOverlapShare * 100)}% of jobs get a completely different top-3 from the
        two models · feed built {meta.generatedAt}
      </div>
    </div>
  );
}
