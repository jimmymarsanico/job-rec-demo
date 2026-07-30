"use client";

import { useState } from "react";

const PROSE_CLASSES =
  "prose prose-sm max-w-none text-gray-700 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2 [&_p]:mb-3 [&_a]:text-blue-600 [&_a]:underline";

/**
 * Collapsed by default. These postings run to 6,000 characters, and when the point of
 * the page is the model comparison below it, nobody should have to scroll past a full
 * job ad to reach it.
 */
export default function JobDescription({ html }: { html: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">Job Description</h2>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          {expanded ? "Collapse" : "Show full description"}
        </button>
      </div>

      <div className="relative">
        <div
          className={expanded ? PROSE_CLASSES : `${PROSE_CLASSES} max-h-56 overflow-hidden`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        {!expanded && (
          <button
            onClick={() => setExpanded(true)}
            aria-label="Show full description"
            className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-white via-white/90 to-transparent flex items-end justify-center pb-1 text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Show full description
          </button>
        )}
      </div>
    </div>
  );
}
