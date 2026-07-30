# Job Recommendation Demo

Two content-based "similar jobs" recommenders compared head to head over **1,000 tech postings
from 112 US and Canadian companies**, with a real mix of remote, hybrid and on-site roles.

| | Model | What it sees |
|---|---|---|
| **A** | Baseline | Job **title** only — TF-IDF cosine similarity |
| **B** | Enhanced | Description 32%, title 20%, job family 16%, seniority 12%, location 10%, workplace type 6%, employment type 4% — then capped at one role per employer |

Model B wins **8 of 9** offline metrics. The headline result is that the win comes from the
structured fields (job family, seniority, workplace type), not from the description text —
and that removing per-company boilerplate mattered more than adding features at all.

```
notebook/    data ingestion, both models, evaluation, JSON export
web/         Next.js app — browse jobs, compare both models side by side
docs/plans/  original Feb 2026 build plan (historical)
```

## The data

There is no off-the-shelf feed that fits. The large aggregate feeds (e.g. Workable's 177K-job
board feed, still live at 825 MB) are dominated by non-tech roles outside North America, and
none of them carry a trustworthy remote / hybrid / on-site signal.

So `notebook/fetch_feed.py` builds one from the public ATS job boards of **124 named tech
companies** — Greenhouse, Lever and Ashby. Ashby and Lever expose `workplaceType` directly, so
the workplace field is reported rather than guessed; for Greenhouse it is derived from the
location string and an explicit in-office cadence in the posting text.

The script normalizes three payload shapes into one record, keeps only tech roles resolvable to
a US or Canadian location, and writes a single Indeed-style XML feed:

```
13,700 raw postings  ->  2,793 tech US/CA jobs  ->  1,000 sampled for the demo
```

| | |
|---|---|
| Job families | 19 — backend, frontend, full-stack, mobile, ML engineering, AI research, data science, data engineering, analytics, infra/DevOps, security, QA, product management, product design, engineering management, TPM, DevRel, solutions engineering |
| Workplace mix | 49% on-site · 26% remote · 25% hybrid |
| Geography | 87% US · 13% Canada |
| Companies | Databricks, Stripe, Anthropic, Figma, Datadog, Reddit, Roblox, Coinbase, Notion, Cursor, Cohere, Ramp, Vanta, Zoox, Replit, ElevenLabs, Pinterest, Airbnb, and ~95 more |

The gzipped feed (3.3 MB) is committed, so the notebook runs from a cold start — including on
Colab — without hitting 120+ endpoints.

## Running it

```bash
cd notebook
pip install -r requirements.txt

# Option 1: open the notebook (already has all outputs saved)
jupyter lab job_recommendations.ipynb

# Option 2: run the same pipeline as a script
python generate_data.py --copy-to-web

# Rebuild the feed from live job boards (~2 min)
python fetch_feed.py --gzip
```

The notebook and `generate_data.py` produce byte-identical output — similarity matrices are
rounded at source and ties break on job id, so BLAS thread scheduling can't reorder results
between runs.

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

### Optional: the blind LLM judge

The job detail page has a **Run blind LLM judge** button. It sends both recommendation lists to
an LLM *without* saying which model produced which, in randomised order, and asks which set is
more useful — then maps the verdict back. Set `OPENAI_API_KEY` in the Vercel project settings
(or `web/.env.local`) to enable it. Without a key the button returns a clear error and
everything else works.

## Findings

1. **Boilerplate removal mattered more than feature engineering.** Before stripping per-company
   text blocks, Model B looked spectacular — relevance 0.56 vs 0.16, and 76% of its
   recommendations at the same employer as the source job. Both numbers were the same artifact:
   every Stripe posting shares a paragraph of Stripe copy, so description TF-IDF was largely
   measuring *"do these two jobs share an employer"*. Dropping 43% of the text as boilerplate
   cut the apparent win by about 90%; what remained was real.

2. **The structured fields carry the win.**

   | | A · Baseline | B · Enhanced |
   |---|---|---|
   | Same job family | 76% | **96%** |
   | Seniority within one level | 85% | **93%** |
   | Same workplace type | 40% | **76%** |
   | Remote ↔ On-site mismatches | 20.8% | **5.8%** |
   | Relevance (shared yardstick) | 0.125 | **0.160** |
   | Catalog coverage | 73% | **87%** |

3. **Workplace type is a hard constraint dressed as a soft feature.** A candidate reading a
   remote posting cannot take an on-site role in another city, so that slot is wasted. The
   baseline burns one in five slots this way.

4. **You cannot compare the two models' own scores.** They are computed on different scales, so
   "mean recommendation score" is meaningless across models. Every relevance metric here is
   measured on one shared yardstick — description TF-IDF space, which neither model ranks by.

Limitations, and what would come next with real interaction data, are in section 13 of the
notebook.
