"""
Standalone version of job_recommendations.ipynb: builds both recommendation models from the
XML feed and writes the JSON the web app consumes. Same logic, no Jupyter required.

    python generate_data.py                     # writes output/*.json
    python generate_data.py --copy-to-web       # also copies into ../web/public/data/
    python generate_data.py --refresh-feed      # re-scrape the ATS boards first

The notebook is the artifact to read — it explains each step and shows the evaluation.
This script exists so the app's data can be regenerated in one command.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

XML_PATH = "data/tech_jobs_feed.xml"
GZ_PATH = XML_PATH + ".gz"
FEED_URL = (
    "https://raw.githubusercontent.com/jimmymarsanico/job-rec-demo/"
    "main/notebook/data/tech_jobs_feed.xml.gz"
)
OUTPUT_DIR = "output"
WEB_DATA_DIR = os.path.join("..", "web", "public", "data")
SAMPLE_SIZE = 1000
TOP_N = 3
SEED = 42

WEIGHTS = {
    "description": 0.32,
    "title": 0.20,
    "job_family": 0.16,
    "seniority": 0.12,
    "location": 0.10,
    "workplace": 0.06,
    "employment_type": 0.04,
}

FAMILY_GROUP = {
    "Software Engineering": "eng", "Backend Engineering": "eng", "Frontend Engineering": "eng",
    "Full-Stack Engineering": "eng", "Mobile Engineering": "eng",
    "Infrastructure & DevOps": "eng", "QA & Test Engineering": "eng",
    "Security Engineering": "eng", "Engineering Management": "eng",
    "Machine Learning Engineering": "ai-data", "AI / ML Research": "ai-data",
    "Data Science": "ai-data", "Data Engineering": "ai-data", "Analytics & BI": "ai-data",
    "Product Management": "product", "Technical Program Management": "product",
    "Product Design": "design",
    "Solutions Engineering": "field", "Developer Relations": "field",
}

SENIORITY_RANK = {
    "Internship": 0, "Entry level": 1, "Mid level": 2, "Senior": 3,
    "Staff / Principal": 4, "Director": 5, "Executive": 6,
}

WORKPLACE_SIM = {
    ("Remote", "Remote"): 1.0, ("Hybrid", "Hybrid"): 1.0, ("On-site", "On-site"): 1.0,
    ("Remote", "Hybrid"): 0.35, ("Hybrid", "Remote"): 0.35,
    ("Hybrid", "On-site"): 0.35, ("On-site", "Hybrid"): 0.35,
    ("Remote", "On-site"): 0.0, ("On-site", "Remote"): 0.0,
}

DOMAIN_STOPWORDS = {
    "experience", "years", "year", "work", "working", "team", "teams", "role", "company",
    "candidate", "candidates", "job", "position", "opportunity", "ability", "strong",
    "excellent", "required", "preferred", "plus", "help", "including", "etc", "new",
    "world", "mission", "people", "www", "https", "http", "com",
    "salary", "compensation", "bonus", "equity", "benefits", "insurance", "dental", "vision",
    "pto", "401k", "offer", "range", "pay", "hiring", "recruiter", "interview", "resume",
    "apply", "application", "employer", "employment", "equal", "disability", "veteran",
    "gender", "orientation", "religion", "race", "sexual", "identity", "protected",
    "applicants", "accommodation", "accommodations", "reasonable", "status", "regard",
}
STOPWORDS = sorted(TfidfVectorizer(stop_words="english").get_stop_words() | DOMAIN_STOPWORDS)

FIELDS = {
    "id": "referencenumber", "title": "title", "company": "company",
    "city": "city", "state": "state", "country": "country",
    "workplace": "workplace", "job_type": "jobtype", "category": "category",
    "experience": "experience", "education": "education",
    "department": "department", "team": "team",
    "url": "url", "date": "date", "source": "feedsource",
    "description": "description",
}

BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "div", "td", "blockquote"]


def ensure_feed(refresh=False):
    if refresh:
        print("Re-scraping ATS boards...")
        subprocess.run([sys.executable, "fetch_feed.py", "--out", XML_PATH, "--gzip"], check=True)
        return
    if os.path.exists(XML_PATH):
        print(f"Using cached feed {XML_PATH} ({os.path.getsize(XML_PATH) / 1e6:.1f} MB)")
        return
    if not os.path.exists(GZ_PATH):
        print(f"Downloading {FEED_URL} ...")
        r = requests.get(FEED_URL, timeout=300)
        r.raise_for_status()
        os.makedirs("data", exist_ok=True)
        with open(GZ_PATH, "wb") as f:
            f.write(r.content)
    with gzip.open(GZ_PATH, "rb") as fi, open(XML_PATH, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    print(f"Wrote {XML_PATH} ({os.path.getsize(XML_PATH) / 1e6:.1f} MB)")


def parse_feed(xml_path):
    jobs = []
    for _, elem in etree.iterparse(xml_path, events=("end",), tag="job", recover=True):
        job = {k: (elem.findtext(tag) or "").strip() for k, tag in FIELDS.items()}
        job["remote"] = (elem.findtext("remote") or "").strip().lower() == "true"
        if job["id"] and job["title"] and job["description"]:
            jobs.append(job)
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    return jobs


def stratified_sample(df, n=SAMPLE_SIZE, seed=SEED):
    """Sample n jobs keeping the feed's job-family x workplace mix."""
    df = df.drop_duplicates(subset=["title", "company"]).copy()
    df["_cell"] = df["category"] + " | " + df["workplace"]
    counts = df["_cell"].value_counts()
    alloc = (counts / counts.sum() * n).apply(lambda x: max(int(round(x)), 2)).clip(upper=counts)

    while alloc.sum() > n:
        for cell in alloc.sort_values(ascending=False).index:
            if alloc[cell] > 2:
                alloc[cell] -= 1
                if alloc.sum() == n:
                    break
    while alloc.sum() < n:
        for cell in alloc.sort_values(ascending=False).index:
            if alloc[cell] < counts[cell]:
                alloc[cell] += 1
                if alloc.sum() == n:
                    break

    parts = [df[df["_cell"] == c].sample(n=k, random_state=seed) for c, k in alloc.items() if k > 0]
    out = pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    return out.drop(columns="_cell")


def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"\S+@\S+\.\S+", " ", text)
    text = re.sub(r"&\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def html_blocks(raw_html):
    if not raw_html:
        return []
    soup = BeautifulSoup(raw_html, "html.parser")
    out = []
    for el in soup.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS):
            continue
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if t:
            out.append(t)
    if not out:
        t = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        if t:
            out.append(t)
    return out


def block_key(block):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", block.lower())).strip()


def strip_boilerplate(df, global_share=0.25, company_share=0.50, min_postings=3):
    """
    Drop paragraphs that repeat across a company's postings (the "About Us" block) or
    across the whole corpus (EEO footers), plus the employer's own name. Without this,
    description similarity mostly measures whether two jobs share an employer.
    """
    blocks = df["description"].apply(html_blocks)
    sizes = df["company"].value_counts()
    global_counts, company_counts = Counter(), defaultdict(Counter)
    for company, bs in zip(df["company"], blocks):
        keys = {block_key(b) for b in bs}
        global_counts.update(keys)
        company_counts[company].update(keys)

    global_drop = {k for k, c in global_counts.items() if c >= global_share * len(df)}
    company_drop = {
        (company, k)
        for company, counts in company_counts.items()
        if sizes[company] >= min_postings
        for k, c in counts.items()
        if c >= company_share * sizes[company]
    }

    out = []
    for company, bs in zip(df["company"], blocks):
        kept = [
            b for b in bs
            if len(block_key(b)) >= 25
            and block_key(b) not in global_drop
            and (company, block_key(b)) not in company_drop
        ]
        text = " ".join(kept)
        # Longest first, fixed order: set iteration depends on string hashing, which
        # varies per process and would make the pipeline non-reproducible.
        for token in sorted({company, company.split()[0]}, key=len, reverse=True):
            if len(token) > 2:
                text = re.sub(re.escape(token), " ", text, flags=re.I)
        out.append(re.sub(r"\s+", " ", text).strip())
    return out, len(global_drop), len(company_drop)


def preprocess_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#\s]", " ", text.lower())).strip()


def get_top_n_recs(sim_matrix, frame, n=TOP_N, max_per_company=None):
    # max_per_company applies a post-ranking diversity cap: walk the ranking in score
    # order and skip a candidate once that employer already fills its quota.
    # Scores are rounded before sorting and ties broken by job id, so the ranking does
    # not shift between runs when BLAS sums float32 products in a different order.
    ids = frame["id"].to_numpy()
    companies = frame["company"].to_numpy()
    recs = {}
    for i in range(len(frame)):
        scores = np.round(sim_matrix[i], 6)
        scores[i] = -1.0  # never recommend the job itself
        order = np.lexsort((ids, -scores))
        if max_per_company is None:
            chosen = order[:n]
        else:
            used, chosen = Counter(), []
            for j in order:
                if used[companies[j]] >= max_per_company:
                    continue
                chosen.append(j)
                used[companies[j]] += 1
                if len(chosen) == n:
                    break
        recs[ids[i]] = [{"id": ids[j], "score": round(float(scores[j]), 4)} for j in chosen]
    return recs


def evaluate(recs, df, desc_sim):
    """All relevance measured in description TF-IDF space — one yardstick for both models."""
    idx = {job_id: i for i, job_id in enumerate(df["id"])}
    fam = df["category"].to_dict()
    rank = df["experience"].map(SENIORITY_RANK).fillna(2).to_dict()
    country = df["country"].to_dict()
    workplace = df["workplace"].to_dict()
    company = df["company"].to_dict()
    title = df["title"].to_dict()

    rel, ild, f_hit, s_hit, g_hit, w_hit, echo, same_co = ([] for _ in range(8))
    covered = set()
    for job_id, rlist in recs.items():
        i = idx[job_id]
        js = [idx[r["id"]] for r in rlist]
        covered.update(r["id"] for r in rlist)
        rel.extend(desc_sim[i, j] for j in js)
        pairs = [desc_sim[a, b] for k, a in enumerate(js) for b in js[k + 1:]]
        if pairs:
            ild.append(1.0 - float(np.mean(pairs)))
        for j in js:
            f_hit.append(fam[i] == fam[j])
            s_hit.append(abs(rank[i] - rank[j]) <= 1)
            g_hit.append(country[i] == country[j])
            w_hit.append(workplace[i] == workplace[j])
            echo.append(title[i].strip().lower() == title[j].strip().lower())
            same_co.append(company[i] == company[j])

    return {
        "Relevance (desc-space cosine)": float(np.mean(rel)),
        "Intra-list diversity": float(np.mean(ild)),
        "Same job family": float(np.mean(f_hit)),
        "Seniority within 1 level": float(np.mean(s_hit)),
        "Same country": float(np.mean(g_hit)),
        "Same workplace type": float(np.mean(w_hit)),
        "Identical title (echo)": float(np.mean(echo)),
        "Same company": float(np.mean(same_co)),
        "Catalog coverage": len(covered) / len(df),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--copy-to-web", action="store_true", help=f"copy JSON into {WEB_DATA_DIR}")
    ap.add_argument("--refresh-feed", action="store_true", help="re-scrape the ATS boards first")
    args = ap.parse_args()

    os.makedirs("data", exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    np.random.seed(SEED)

    ensure_feed(args.refresh_feed)

    df_all = pd.DataFrame(parse_feed(XML_PATH))
    print(f"Feed: {len(df_all):,} jobs, {df_all['company'].nunique()} companies")

    df = stratified_sample(df_all)
    print(f"Sample: {len(df)} jobs, {df['company'].nunique()} companies, "
          f"{df['category'].nunique()} families")
    print(f"  workplace: {df['workplace'].value_counts().to_dict()}")

    df["description_clean"] = df["description"].apply(clean_html)
    core, n_global, n_company = strip_boilerplate(df)
    df["description_core"] = core
    removed = 1 - df["description_core"].str.len().sum() / df["description_clean"].str.len().sum()
    print(f"Boilerplate: {n_global} global + {n_company} company blocks, "
          f"{removed:.1%} of text removed")

    df["title_clean"] = df["title"].apply(preprocess_text)
    df["desc_processed"] = df["description_core"].apply(preprocess_text)

    # --- Model A: title only -------------------------------------------------------
    title_tfidf = TfidfVectorizer(
        ngram_range=(1, 2), max_features=5000, stop_words=STOPWORDS, sublinear_tf=True
    ).fit_transform(df["title_clean"])
    # Rounded at source so BLAS thread scheduling cannot reorder tied candidates.
    title_sim = np.round(cosine_similarity(title_tfidf), 5).astype(np.float32)
    baseline_recs = get_top_n_recs(title_sim, df)
    print(f"\nBaseline: {len(baseline_recs)} rec lists (title TF-IDF {title_tfidf.shape})")

    # --- Model B: seven weighted features ------------------------------------------
    desc_tfidf = TfidfVectorizer(
        ngram_range=(1, 2), max_features=20000, max_df=0.80, min_df=3,
        stop_words=STOPWORDS, sublinear_tf=True, dtype=np.float32,
    ).fit_transform(df["desc_processed"])
    desc_sim = np.round(cosine_similarity(desc_tfidf), 5).astype(np.float32)

    fam = df["category"].to_numpy()
    grp = df["category"].map(FAMILY_GROUP).fillna("other").to_numpy()
    family_sim = np.where(fam[:, None] == fam[None, :], 1.0,
                          np.where(grp[:, None] == grp[None, :], 0.5, 0.0)).astype(np.float32)

    rank = df["experience"].map(SENIORITY_RANK).fillna(2).to_numpy(dtype=np.float32)
    seniority_sim = (1.0 - np.abs(rank[:, None] - rank[None, :]) / 6.0).astype(np.float32)

    city, state, country = df["city"].to_numpy(), df["state"].to_numpy(), df["country"].to_numpy()
    real_city = ~np.isin(city, ["Unknown", "Remote", ""])
    real_state = state != "Unknown"
    location_sim = np.where(
        (city[:, None] == city[None, :]) & real_city[:, None] & real_city[None, :], 1.0,
        np.where((state[:, None] == state[None, :]) & real_state[:, None] & real_state[None, :], 0.6,
                 np.where(country[:, None] == country[None, :], 0.25, 0.0))
    ).astype(np.float32)

    codes = {w: i for i, w in enumerate(["Remote", "Hybrid", "On-site"])}
    lut = np.zeros((3, 3), dtype=np.float32)
    for (a, b), v in WORKPLACE_SIM.items():
        lut[codes[a], codes[b]] = v
    wp_idx = np.array([codes.get(w, 2) for w in df["workplace"].to_numpy()])
    workplace_sim = lut[wp_idx[:, None], wp_idx[None, :]]

    jt = df["job_type"].to_numpy()
    jobtype_sim = (jt[:, None] == jt[None, :]).astype(np.float32)

    weighted_sim = (
        WEIGHTS["description"] * desc_sim
        + WEIGHTS["title"] * title_sim
        + WEIGHTS["job_family"] * family_sim
        + WEIGHTS["seniority"] * seniority_sim
        + WEIGHTS["location"] * location_sim
        + WEIGHTS["workplace"] * workplace_sim
        + WEIGHTS["employment_type"] * jobtype_sim
    ).astype(np.float32)

    weighted_recs = get_top_n_recs(weighted_sim, df, max_per_company=1)
    print(f"Enhanced: {len(weighted_recs)} rec lists (desc TF-IDF {desc_tfidf.shape}), "
          f"capped at 1 per employer")

    # --- Evaluate -------------------------------------------------------------------
    base_m = evaluate(baseline_recs, df, desc_sim)
    wtd_m = evaluate(weighted_recs, df, desc_sim)
    print("\n{:<32} {:>10} {:>10}".format("metric", "baseline", "enhanced"))
    for k in base_m:
        print(f"  {k:<30} {base_m[k]:>10.4f} {wtd_m[k]:>10.4f}")

    overlaps = [
        len({r["id"] for r in baseline_recs[j]} & {r["id"] for r in weighted_recs[j]})
        for j in baseline_recs
    ]

    # --- Export ---------------------------------------------------------------------
    jobs_export = [{
        "id": r["id"], "title": r["title"], "company": r["company"],
        "city": r["city"], "state": r["state"], "country": r["country"],
        "remote": bool(r["remote"]), "workplace": r["workplace"],
        "description": r["description"], "category": r["category"],
        "jobType": r["job_type"], "experience": r["experience"],
        "education": r["education"], "department": r["department"], "team": r["team"],
        "url": r["url"], "date": r["date"], "source": r["source"],
    } for _, r in df.iterrows()]

    meta = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "jobCount": len(jobs_export),
        "companyCount": int(df["company"].nunique()),
        "feedSize": int(len(df_all)),
        "topN": TOP_N,
        "weights": WEIGHTS,
        "metrics": {
            "baseline": {k: round(v, 4) for k, v in base_m.items()},
            "enhanced": {k: round(v, 4) for k, v in wtd_m.items()},
        },
        "workplaceMix": df["workplace"].value_counts().to_dict(),
        "meanOverlap": round(float(np.mean(overlaps)), 3),
        "zeroOverlapShare": round(float(np.mean([o == 0 for o in overlaps])), 4),
    }

    payloads = {
        "jobs.json": jobs_export,
        "recs_baseline.json": baseline_recs,
        "recs_weighted.json": weighted_recs,
        "meta.json": meta,
    }
    print()
    for name, payload in payloads.items():
        p = os.path.join(OUTPUT_DIR, name)
        with open(p, "w") as f:
            json.dump(payload, f, separators=(",", ":"))
        print(f"  {p:<30} {os.path.getsize(p) / 1024:>8.0f} KB")

    ids = {j["id"] for j in jobs_export}
    for label, recs in (("baseline", baseline_recs), ("enhanced", weighted_recs)):
        assert set(recs) == ids, f"{label}: rec keys do not match job ids"
        assert all(len(v) == TOP_N for v in recs.values()), f"{label}: wrong rec count"
        assert all(r["id"] in ids for v in recs.values() for r in v), f"{label}: dangling rec id"
        assert all(k not in {r["id"] for r in v} for k, v in recs.items()), f"{label}: self-rec"
    print("\nValidation passed.")

    if args.copy_to_web:
        os.makedirs(WEB_DATA_DIR, exist_ok=True)
        for name in payloads:
            shutil.copy(os.path.join(OUTPUT_DIR, name), os.path.join(WEB_DATA_DIR, name))
        print(f"Copied {len(payloads)} files into {WEB_DATA_DIR}")


if __name__ == "__main__":
    main()
