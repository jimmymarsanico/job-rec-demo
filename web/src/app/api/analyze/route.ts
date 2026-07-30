import { NextRequest, NextResponse } from "next/server";

interface JobSummary {
  title: string;
  company: string;
  city: string;
  country: string;
  category: string;
  jobType: string;
  experience: string;
  workplace: string;
}

interface AnalyzeRequest {
  sourceJob: JobSummary;
  baselineRecs: JobSummary[];
  enhancedRecs: JobSummary[];
}

function render(recs: JobSummary[]): string {
  return recs
    .map(
      (r, i) =>
        `${i + 1}. ${r.title} — ${r.company} (${r.city}, ${r.country}) ` +
        `[${r.category}; ${r.experience}; ${r.workplace}; ${r.jobType}]`
    )
    .join("\n");
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      {
        error:
          "OPENAI_API_KEY is not configured. Add it in the Vercel project settings (or web/.env.local) to enable the blind LLM judge.",
      },
      { status: 500 }
    );
  }

  const body: AnalyzeRequest = await request.json();
  const { sourceJob, baselineRecs, enhancedRecs } = body;

  if (!sourceJob || !baselineRecs?.length || !enhancedRecs?.length) {
    return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
  }

  // Blind A/B: the judge is never told which list came from which model, and which list
  // appears first is randomised per request. Labelling one of them "Enhanced" in the
  // prompt would do the judging for us and the verdict would prove nothing.
  const enhancedFirst = Math.random() < 0.5;
  const listOne = enhancedFirst ? enhancedRecs : baselineRecs;
  const listTwo = enhancedFirst ? baselineRecs : enhancedRecs;

  const prompt = `You are evaluating two candidate "similar jobs" lists for a job board. A candidate is currently viewing the job below. Two different recommender systems each produced three suggestions. You are told nothing about how either system works.

## The job being viewed
- Title: ${sourceJob.title}
- Company: ${sourceJob.company}
- Location: ${sourceJob.city}, ${sourceJob.country}
- Job family: ${sourceJob.category}
- Seniority: ${sourceJob.experience}
- Workplace: ${sourceJob.workplace}
- Employment type: ${sourceJob.jobType}

## List 1
${render(listOne)}

## List 2
${render(listTwo)}

Judge which list is more useful to this specific candidate. Weigh:
- role relevance — would someone interested in the viewed job plausibly want these?
- seniority fit — an intern should not be shown Director roles, and vice versa
- workplace compatibility — a remote candidate cannot take an on-site role in another city
- usefulness of the set as a whole — three near-identical titles add little, and neither do three roles at one employer

Respond with JSON only, in this shape:
{"winner": "List 1" | "List 2" | "tie", "reasoning": "3-4 sentences citing specific job titles from the lists and explaining the decisive differences. Refer to the lists only as List 1 and List 2."}`;

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.2,
        max_tokens: 500,
        response_format: { type: "json_object" },
      }),
    });

    if (!response.ok) {
      // Surface the upstream reason. A bare "429" is ambiguous between a rate limit and
      // an exhausted quota, and that difference decides whether waiting helps.
      let detail = "";
      let code = "";
      try {
        const err = await response.json();
        detail = err?.error?.message ?? "";
        code = err?.error?.code ?? err?.error?.type ?? "";
      } catch {
        detail = await response.text().catch(() => "");
      }

      const friendly =
        code === "insufficient_quota"
          ? "The OpenAI account has no remaining quota — add credit or use a different key."
          : response.status === 401
            ? "OPENAI_API_KEY was rejected. Check the key in the Vercel project settings."
            : response.status === 429
              ? "OpenAI rate limit or quota reached. If this persists, check billing rather than retrying."
              : `OpenAI returned ${response.status}.`;

      return NextResponse.json(
        { error: detail ? `${friendly} (${detail})` : friendly },
        { status: 502 }
      );
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    if (!content) {
      return NextResponse.json({ error: "Empty response from the judge." }, { status: 502 });
    }

    let parsed: { winner?: string; reasoning?: string };
    try {
      parsed = JSON.parse(content);
    } catch {
      return NextResponse.json({ error: "Judge returned malformed JSON." }, { status: 502 });
    }

    // Map the blind label back to the model that actually produced that list.
    let winner: "baseline" | "enhanced" | "tie" = "tie";
    if (parsed.winner === "List 1") winner = enhancedFirst ? "enhanced" : "baseline";
    else if (parsed.winner === "List 2") winner = enhancedFirst ? "baseline" : "enhanced";

    return NextResponse.json({
      winner,
      reasoning: parsed.reasoning ?? "No reasoning returned.",
      // Which model happened to be shown first, so the UI can show the blinding was real.
      shownFirst: enhancedFirst ? "enhanced" : "baseline",
    });
  } catch {
    return NextResponse.json({ error: "Failed to reach the OpenAI API." }, { status: 502 });
  }
}
