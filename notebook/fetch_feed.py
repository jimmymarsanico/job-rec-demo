"""
Build a tech-jobs XML feed from public ATS job boards (Greenhouse, Lever, Ashby).

Why not a single off-the-shelf XML feed? The large aggregate feeds (e.g. Workable's
177K-job board feed) are dominated by non-tech roles and non-North-American postings,
and none of them carry a trustworthy remote / hybrid / on-site signal. The public ATS
board APIs do: Ashby and Lever both expose an explicit `workplaceType`, and their
boards belong to named US/Canada tech companies.

This script fetches every board in BOARDS, normalizes the three payload shapes into one
record type, keeps only tech roles located in the US or Canada, and writes a single
Indeed-style XML job feed. The notebook then treats that XML as its raw input, so the
modelling pipeline reads one cached file instead of 120+ HTTP endpoints.

Usage:
    python fetch_feed.py                              # fetch live -> data/tech_jobs_feed.xml
    python fetch_feed.py --cache-dir raw_boards       # reuse/populate raw JSON cache
    python fetch_feed.py --out data/feed.xml --gzip   # also write feed.xml.gz
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from lxml import etree

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

BOARD_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}",
}

# (ats, board token, display company name). Every board here was verified live.
BOARDS = [
    # --- Greenhouse ---
    ("greenhouse", "databricks", "Databricks"),
    ("greenhouse", "anthropic", "Anthropic"),
    ("greenhouse", "roblox", "Roblox"),
    ("greenhouse", "stripe", "Stripe"),
    ("greenhouse", "affirm", "Affirm"),
    ("greenhouse", "reddit", "Reddit"),
    ("greenhouse", "okta", "Okta"),
    ("greenhouse", "pinterest", "Pinterest"),
    ("greenhouse", "brex", "Brex"),
    ("greenhouse", "datadog", "Datadog"),
    ("greenhouse", "scaleai", "Scale AI"),
    ("greenhouse", "verkada", "Verkada"),
    ("greenhouse", "twilio", "Twilio"),
    ("greenhouse", "lyft", "Lyft"),
    ("greenhouse", "gitlab", "GitLab"),
    ("greenhouse", "samsara", "Samsara"),
    ("greenhouse", "instacart", "Instacart"),
    ("greenhouse", "tenstorrent", "Tenstorrent"),
    ("greenhouse", "coinbase", "Coinbase"),
    ("greenhouse", "airbnb", "Airbnb"),
    ("greenhouse", "mongodb", "MongoDB"),
    ("greenhouse", "robinhood", "Robinhood"),
    ("greenhouse", "nuro", "Nuro"),
    ("greenhouse", "figma", "Figma"),
    ("greenhouse", "epicgames", "Epic Games"),
    ("greenhouse", "riotgames", "Riot Games"),
    ("greenhouse", "asana", "Asana"),
    ("greenhouse", "faire", "Faire"),
    ("greenhouse", "elastic", "Elastic"),
    ("greenhouse", "chime", "Chime"),
    ("greenhouse", "temporaltechnologies", "Temporal Technologies"),
    ("greenhouse", "vercel", "Vercel"),
    ("greenhouse", "dialpad", "Dialpad"),
    ("greenhouse", "gusto", "Gusto"),
    ("greenhouse", "tailscale", "Tailscale"),
    ("greenhouse", "discord", "Discord"),
    ("greenhouse", "duolingo", "Duolingo"),
    ("greenhouse", "mercury", "Mercury"),
    ("greenhouse", "remotecom", "Remote"),
    ("greenhouse", "twitch", "Twitch"),
    ("greenhouse", "amplitude", "Amplitude"),
    ("greenhouse", "gemini", "Gemini"),
    ("greenhouse", "fastly", "Fastly"),
    ("greenhouse", "peloton", "Peloton"),
    ("greenhouse", "airtable", "Airtable"),
    ("greenhouse", "betterment", "Betterment"),
    ("greenhouse", "scopely", "Scopely"),
    ("greenhouse", "later", "Later"),
    ("greenhouse", "sofi", "SoFi"),
    ("greenhouse", "dropbox", "Dropbox"),
    ("greenhouse", "marqeta", "Marqeta"),
    ("greenhouse", "webflow", "Webflow"),
    ("greenhouse", "mixpanel", "Mixpanel"),
    ("greenhouse", "carta", "Carta"),
    ("greenhouse", "cockroachlabs", "Cockroach Labs"),
    ("greenhouse", "planetscale", "PlanetScale"),
    ("greenhouse", "flexport", "Flexport"),
    ("greenhouse", "cloudflare", "Cloudflare"),
    ("greenhouse", "modernhealth", "Modern Health"),
    ("greenhouse", "lithic", "Lithic"),
    ("greenhouse", "hootsuite", "Hootsuite"),
    ("greenhouse", "netlify", "Netlify"),
    ("greenhouse", "lattice", "Lattice"),
    ("greenhouse", "squarespace", "Squarespace"),
    # --- Lever ---
    ("lever", "zoox", "Zoox"),
    ("lever", "ro", "Ro"),
    ("lever", "logrocket", "LogRocket"),
    ("lever", "gopuff", "Gopuff"),
    # --- Ashby ---
    ("ashby", "harvey", "Harvey"),
    ("ashby", "crusoe", "Crusoe"),
    ("ashby", "replit", "Replit"),
    ("ashby", "sierra", "Sierra"),
    ("ashby", "cursor", "Cursor"),
    ("ashby", "decagon", "Decagon"),
    ("ashby", "cohere", "Cohere"),
    ("ashby", "base-power", "Base Power"),
    ("ashby", "ramp", "Ramp"),
    ("ashby", "baseten", "Baseten"),
    ("ashby", "temporal", "Temporal"),
    ("ashby", "hinge-health", "Hinge Health"),
    ("ashby", "vanta", "Vanta"),
    ("ashby", "zip", "Zip"),
    ("ashby", "writer", "Writer"),
    ("ashby", "notion", "Notion"),
    ("ashby", "ashby", "Ashby"),
    ("ashby", "gamma", "Gamma"),
    ("ashby", "rain", "Rain"),
    ("ashby", "suno", "Suno"),
    ("ashby", "workos", "WorkOS"),
    ("ashby", "nooks", "Nooks"),
    ("ashby", "cognition", "Cognition"),
    ("ashby", "rogo", "Rogo"),
    ("ashby", "orb", "Orb"),
    ("ashby", "poolside", "Poolside"),
    ("ashby", "modal", "Modal"),
    ("ashby", "doss", "Doss"),
    ("ashby", "persona", "Persona"),
    ("ashby", "sardine", "Sardine"),
    ("ashby", "rilla", "Rilla"),
    ("ashby", "speak", "Speak"),
    ("ashby", "middesk", "Middesk"),
    ("ashby", "watershed", "Watershed"),
    ("ashby", "openevidence", "OpenEvidence"),
    ("ashby", "elevenlabs", "ElevenLabs"),
    ("ashby", "pika", "Pika"),
    ("ashby", "browserbase", "Browserbase"),
    ("ashby", "resend", "Resend"),
    ("ashby", "reka", "Reka AI"),
    ("ashby", "warp", "Warp"),
    ("ashby", "knock", "Knock"),
    ("ashby", "axiom", "Axiom"),
    ("ashby", "found", "Found"),
    ("ashby", "neon", "Neon"),
    ("ashby", "abridge", "Abridge"),
    ("ashby", "lovable", "Lovable"),
    ("ashby", "attio", "Attio"),
    ("ashby", "pylon", "Pylon"),
    ("ashby", "plain", "Plain"),
    ("ashby", "levelpath", "Levelpath"),
    ("ashby", "lago", "Lago"),
    ("ashby", "inngest", "Inngest"),
    ("ashby", "oneschema", "OneSchema"),
    ("ashby", "tenderly", "Tenderly"),
    ("ashby", "quicknode", "QuickNode"),
]

# --------------------------------------------------------------------------------------
# Location parsing
# --------------------------------------------------------------------------------------

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC", "washington dc": "DC",
    "washington d c": "DC",
}
US_ABBR = set(US_STATES.values())

CA_PROVINCES = {
    "ontario": "ON", "quebec": "QC", "québec": "QC", "british columbia": "BC",
    "alberta": "AB", "manitoba": "MB", "saskatchewan": "SK", "nova scotia": "NS",
    "new brunswick": "NB", "newfoundland and labrador": "NL", "newfoundland": "NL",
    "prince edward island": "PE",
}
CA_ABBR = set(CA_PROVINCES.values())

# Bare city names that appear without a state/province. Values: (canonical city, region, country)
CITY_MAP = {
    "san francisco": ("San Francisco", "CA", "US"),
    "sf": ("San Francisco", "CA", "US"),
    "san francisco bay area": ("San Francisco", "CA", "US"),
    "sf bay area": ("San Francisco", "CA", "US"),
    "bay area": ("San Francisco", "CA", "US"),
    "south san francisco": ("South San Francisco", "CA", "US"),
    "new york": ("New York", "NY", "US"),
    "new york city": ("New York", "NY", "US"),
    "nyc": ("New York", "NY", "US"),
    "manhattan": ("New York", "NY", "US"),
    "brooklyn": ("Brooklyn", "NY", "US"),
    "seattle": ("Seattle", "WA", "US"),
    "bellevue": ("Bellevue", "WA", "US"),
    "kirkland": ("Kirkland", "WA", "US"),
    "redmond": ("Redmond", "WA", "US"),
    "austin": ("Austin", "TX", "US"),
    "dallas": ("Dallas", "TX", "US"),
    "houston": ("Houston", "TX", "US"),
    "san antonio": ("San Antonio", "TX", "US"),
    "boston": ("Boston", "MA", "US"),
    "cambridge": ("Cambridge", "MA", "US"),
    "somerville": ("Somerville", "MA", "US"),
    "chicago": ("Chicago", "IL", "US"),
    "los angeles": ("Los Angeles", "CA", "US"),
    "la": ("Los Angeles", "CA", "US"),
    "santa monica": ("Santa Monica", "CA", "US"),
    "culver city": ("Culver City", "CA", "US"),
    "el segundo": ("El Segundo", "CA", "US"),
    "pasadena": ("Pasadena", "CA", "US"),
    "irvine": ("Irvine", "CA", "US"),
    "san diego": ("San Diego", "CA", "US"),
    "san jose": ("San Jose", "CA", "US"),
    "sunnyvale": ("Sunnyvale", "CA", "US"),
    "santa clara": ("Santa Clara", "CA", "US"),
    "mountain view": ("Mountain View", "CA", "US"),
    "palo alto": ("Palo Alto", "CA", "US"),
    "menlo park": ("Menlo Park", "CA", "US"),
    "redwood city": ("Redwood City", "CA", "US"),
    "foster city": ("Foster City", "CA", "US"),
    "san mateo": ("San Mateo", "CA", "US"),
    "burlingame": ("Burlingame", "CA", "US"),
    "emeryville": ("Emeryville", "CA", "US"),
    "oakland": ("Oakland", "CA", "US"),
    "berkeley": ("Berkeley", "CA", "US"),
    "fremont": ("Fremont", "CA", "US"),
    "pleasanton": ("Pleasanton", "CA", "US"),
    "denver": ("Denver", "CO", "US"),
    "boulder": ("Boulder", "CO", "US"),
    "arvada": ("Arvada", "CO", "US"),
    "colorado springs": ("Colorado Springs", "CO", "US"),
    "atlanta": ("Atlanta", "GA", "US"),
    "miami": ("Miami", "FL", "US"),
    "tampa": ("Tampa", "FL", "US"),
    "orlando": ("Orlando", "FL", "US"),
    "portland": ("Portland", "OR", "US"),
    "phoenix": ("Phoenix", "AZ", "US"),
    "tempe": ("Tempe", "AZ", "US"),
    "salt lake city": ("Salt Lake City", "UT", "US"),
    "lehi": ("Lehi", "UT", "US"),
    "minneapolis": ("Minneapolis", "MN", "US"),
    "detroit": ("Detroit", "MI", "US"),
    "ann arbor": ("Ann Arbor", "MI", "US"),
    "pittsburgh": ("Pittsburgh", "PA", "US"),
    "philadelphia": ("Philadelphia", "PA", "US"),
    "nashville": ("Nashville", "TN", "US"),
    "charlotte": ("Charlotte", "NC", "US"),
    "raleigh": ("Raleigh", "NC", "US"),
    "durham": ("Durham", "NC", "US"),
    "cary": ("Cary", "NC", "US"),
    "washington": ("Washington", "DC", "US"),
    "washington dc": ("Washington", "DC", "US"),
    "arlington": ("Arlington", "VA", "US"),
    "reston": ("Reston", "VA", "US"),
    "mclean": ("McLean", "VA", "US"),
    "baltimore": ("Baltimore", "MD", "US"),
    "las vegas": ("Las Vegas", "NV", "US"),
    "reno": ("Reno", "NV", "US"),
    "columbus": ("Columbus", "OH", "US"),
    "cleveland": ("Cleveland", "OH", "US"),
    "indianapolis": ("Indianapolis", "IN", "US"),
    "kansas city": ("Kansas City", "MO", "US"),
    "st louis": ("St. Louis", "MO", "US"),
    "madison": ("Madison", "WI", "US"),
    "milwaukee": ("Milwaukee", "WI", "US"),
    "new orleans": ("New Orleans", "LA", "US"),
    "toronto": ("Toronto", "ON", "CA"),
    "vancouver": ("Vancouver", "BC", "CA"),
    "montreal": ("Montreal", "QC", "CA"),
    "montréal": ("Montreal", "QC", "CA"),
    "ottawa": ("Ottawa", "ON", "CA"),
    "waterloo": ("Waterloo", "ON", "CA"),
    "kitchener": ("Kitchener", "ON", "CA"),
    "calgary": ("Calgary", "AB", "CA"),
    "edmonton": ("Edmonton", "AB", "CA"),
    "winnipeg": ("Winnipeg", "MB", "CA"),
    "halifax": ("Halifax", "NS", "CA"),
    "victoria": ("Victoria", "BC", "CA"),
    "mississauga": ("Mississauga", "ON", "CA"),
    "burnaby": ("Burnaby", "BC", "CA"),
    "quebec city": ("Quebec City", "QC", "CA"),
}

US_WORDS = {"us", "usa", "u s", "u s a", "united states", "united states of america", "america"}
CA_WORDS = {"canada", "ca canada"}
NA_WORDS = {"north america", "us canada", "us or canada", "united states or canada", "namer"}

# Any of these means the segment is NOT US/Canada; used to reject rather than guess.
FOREIGN = {
    "united kingdom", "uk", "u k", "england", "london", "manchester", "edinburgh", "scotland",
    "ireland", "dublin", "cork", "germany", "berlin", "munich", "hamburg", "france", "paris",
    "spain", "barcelona", "madrid", "netherlands", "amsterdam", "utrecht", "belgium", "brussels",
    "sweden", "stockholm", "norway", "oslo", "denmark", "copenhagen", "finland", "helsinki",
    "poland", "warsaw", "krakow", "kraków", "portugal", "lisbon", "porto", "italy", "rome",
    "milan", "switzerland", "zurich", "geneva", "austria", "vienna", "czech republic", "prague",
    "romania", "bucharest", "hungary", "budapest", "greece", "athens", "turkey", "istanbul",
    "israel", "tel aviv", "jerusalem", "india", "bengaluru", "bangalore", "mumbai", "delhi",
    "new delhi", "gurugram", "gurgaon", "hyderabad", "pune", "chennai", "noida", "japan",
    "tokyo", "osaka", "china", "beijing", "shanghai", "shenzhen", "hong kong", "singapore",
    "south korea", "korea", "seoul", "taiwan", "taipei", "australia", "sydney", "melbourne",
    "brisbane", "perth", "new zealand", "auckland", "wellington", "brazil", "sao paulo",
    "são paulo", "rio de janeiro", "mexico", "mexico city", "ciudad de mexico", "guadalajara",
    "argentina", "buenos aires", "chile", "santiago", "colombia", "bogota", "bogotá",
    "peru", "lima", "costa rica", "uruguay", "montevideo", "south africa", "cape town",
    "johannesburg", "nigeria", "lagos", "kenya", "nairobi", "egypt", "cairo", "uae",
    "dubai", "abu dhabi", "saudi arabia", "riyadh", "qatar", "doha", "philippines", "manila",
    "indonesia", "jakarta", "malaysia", "kuala lumpur", "thailand", "bangkok", "vietnam",
    "hanoi", "ho chi minh city", "pakistan", "karachi", "lahore", "bangladesh", "dhaka",
    "ukraine", "kyiv", "serbia", "belgrade", "croatia", "zagreb", "bulgaria", "sofia",
    "lithuania", "vilnius", "latvia", "riga", "estonia", "tallinn", "emea", "apac", "latam",
    "australian capital territory", "new south wales", "victoria australia", "ontario canada uk",
}

_REMOTE_RE = re.compile(r"\b(?:fully\s+)?remote\b|\bdistributed\b|\bwork\s+from\s+home\b|\bwfh\b|\banywhere\b", re.I)
_HYBRID_LOC_RE = re.compile(r"\bhybrid\b", re.I)
_ONSITE_LOC_RE = re.compile(r"\bin[-\s]?office\b|\bon[-\s]?site\b|\bonsite\b|\bhq\b|\boffice\b", re.I)

_SPLIT_RE = re.compile(r"\s*(?:;|•|\||/|\bor\b|\band\b|\+)\s*", re.I)
_PARENS_RE = re.compile(r"\(([^)]*)\)")
_NOISE_RE = re.compile(
    r"\b(?:hq|headquarters|office|onsite|on-site|in-office|hybrid|remote|remote-friendly|friendly|"
    r"preferred|based|only|metro area|metro|area|region|greater|multiple locations|various|"
    r"flexible|blank|n/?a|opportunity|optional|eligible|either|open to|anywhere in|anywhere|"
    r"distributed|work from home|wfh|locations?|position|role)\b",
    re.I,
)
# Feeds prefix some locations with a country code: "US - San Francisco", "IN - Bangalore".
_COUNTRY_PREFIX_RE = re.compile(r"^\s*(us|usa|ca|can|uk|gb|in|es|de|fr|jp|sg|au|br|mx|ie|nl|il)\s*[-–:]\s*", re.I)


def _norm(s: str) -> str:
    """Lowercase, strip accents and punctuation noise for dictionary lookups."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").replace("-", " ").replace("_", " ")
    s = re.sub(r"[^a-z0-9,\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _as_region(tok: str):
    """Return (region_abbrev, country) if tok names a US state or Canadian province."""
    if not tok:
        return None
    if tok in US_STATES:
        return (US_STATES[tok], "US")
    if tok in CA_PROVINCES:
        return (CA_PROVINCES[tok], "CA")
    flat = tok.replace(" ", "").upper()
    if len(flat) == 2 and flat in US_ABBR:
        return (flat, "US")
    if len(flat) == 2 and flat in CA_ABBR:
        return (flat, "CA")
    return None


def _as_city(tok: str):
    """
    Look tok up in CITY_MAP, tolerating extra words around the city name
    ("us san francisco", "nyc privy", "betterment hq new york city").
    """
    if not tok:
        return None
    hit = CITY_MAP.get(tok)
    if hit:
        return hit
    words = tok.split()
    if len(words) < 2 or len(words) > 6:
        return None
    # Longest contiguous window first, so "new york city" beats "new york".
    for size in range(min(3, len(words)), 0, -1):
        for start in range(0, len(words) - size + 1):
            hit = CITY_MAP.get(" ".join(words[start:start + size]))
            if hit:
                return hit
    return None


def _resolve_segment(seg: str):
    """Resolve one location segment to (city, region, country) or None if not US/Canada."""
    prefix_country = None
    m = _COUNTRY_PREFIX_RE.match(seg)
    if m:
        code = m.group(1).lower()
        if code in ("us", "usa"):
            prefix_country = "US"
        elif code in ("ca", "can"):
            prefix_country = "CA"
        seg = _COUNTRY_PREFIX_RE.sub("", seg, count=1)

    raw = _NOISE_RE.sub(" ", seg)
    raw = re.sub(r"\s+", " ", raw).strip(" ,-")
    n = _norm(raw)
    if not n:
        return ("Unknown", "Unknown", prefix_country) if prefix_country else None

    parts = [p.strip() for p in n.split(",") if p.strip()]
    if not parts:
        return None

    # Reject explicitly foreign segments before trying to match anything.
    if n in FOREIGN or any(p in FOREIGN for p in parts):
        return None

    # Country-only / region-only mentions.
    if all(p in US_WORDS for p in parts):
        return ("Unknown", "Unknown", "US")
    if len(parts) == 1 and parts[0] in CA_WORDS:
        return ("Unknown", "Unknown", "CA")
    if len(parts) == 1 and parts[0] in NA_WORDS:
        return ("Unknown", "Unknown", "US")

    # Drop a trailing country token so "City, ST, USA" behaves like "City, ST".
    country = prefix_country
    while parts and (parts[-1] in US_WORDS or parts[-1] in CA_WORDS or parts[-1] in NA_WORDS):
        last = parts.pop()
        country = "CA" if last in CA_WORDS else "US"

    if not parts:
        return ("Unknown", "Unknown", country or "US")

    city_tok = parts[0]
    known = _as_city(city_tok)

    # A bare region token in first position ("ON, AB, BC", "California") is a region, not a city.
    if not known:
        first_region = _as_region(city_tok)
        if first_region:
            return ("Unknown", first_region[0], first_region[1])

    region = rcountry = None
    if len(parts) > 1:
        # If the second token is itself a known city, this is a multi-city string —
        # ignore it rather than mistaking "San Francisco, New York, NY" for SF in NY.
        second_is_city = _as_city(parts[1]) is not None
        second_region = _as_region(parts[1])
        if second_region and not (second_is_city and known):
            region, rcountry = second_region

    if known:
        city, kregion, kcountry = known
        # Trust an explicit region only when it names a different country than the
        # dictionary entry (e.g. "Vancouver, WA" is Washington, not British Columbia).
        if region and rcountry != kcountry:
            return (city, region, rcountry)
        return (city, kregion, kcountry)

    if region:
        display = re.split(r"[,•|]", raw)[0].strip().title()
        return (display or "Unknown", region, rcountry)

    # A state name alone ("California", "Texas", "Ontario").
    if city_tok in US_STATES:
        return ("Unknown", US_STATES[city_tok], "US")
    if city_tok in CA_PROVINCES:
        return ("Unknown", CA_PROVINCES[city_tok], "CA")
    ct = city_tok.replace(" ", "").upper()
    if len(ct) == 2 and ct in US_ABBR:
        return ("Unknown", ct, "US")
    if len(ct) == 2 and ct in CA_ABBR:
        return ("Unknown", ct, "CA")

    # Unknown city with an explicit US/CA country from a trailing token.
    if country:
        return (raw.split(",")[0].strip().title(), "Unknown", country)

    return None


def parse_location(text: str):
    """
    Parse a raw ATS location string.

    Returns (city, region, country, workplace_hint, n_segments) or None when the string
    contains no resolvable US/Canada location. workplace_hint is 'Remote', 'Hybrid',
    'On-site' or None.
    """
    if not text:
        return None
    text = text.strip()
    if not text or _norm(text) in {"n a", "na", "blank", ""}:
        return None

    hint = None
    if _REMOTE_RE.search(text):
        hint = "Remote"
    elif _HYBRID_LOC_RE.search(text):
        hint = "Hybrid"
    elif _ONSITE_LOC_RE.search(text):
        hint = "On-site"

    # Parenthetical content often holds the real region: "Remote (US)", "Remote (Canada)".
    extra = _PARENS_RE.findall(text)
    base = _PARENS_RE.sub(" ", text)
    segments = [s for s in _SPLIT_RE.split(base) if s.strip()]
    for e in extra:
        segments.extend(s for s in _SPLIT_RE.split(e) if s.strip())

    resolved = []
    for seg in segments:
        r = _resolve_segment(seg)
        if r:
            resolved.append(r)

    if not resolved:
        return None

    # Prefer a segment that names an actual city.
    best = next((r for r in resolved if r[0] != "Unknown"), resolved[0])
    return (best[0], best[1], best[2], hint, len(segments))


# --------------------------------------------------------------------------------------
# Role classification
# --------------------------------------------------------------------------------------

# Ordered: first match wins, so the most specific patterns come first.
FAMILY_RULES = [
    ("Engineering Management", r"\b(?:engineering|software|technical)\s+(?:manager|director)\b|"
                              r"\b(?:director|head|vp|vice president)\s+of\s+(?:engineering|software|platform|infrastructure|data|security|ai|ml)\b|"
                              r"\bmanager,?\s+(?:software|engineering|backend|frontend|platform|infrastructure|data|security|site reliability|mobile|ml|machine learning)\b|"
                              r"\bengineering\s+lead(?:er)?\b|\bcto\b"),
    ("Technical Program Management", r"\btechnical\s+program\s+manager\b|\btpm\b|\bprogram\s+manager,?\s+(?:engineering|technical|ai|ml|platform)\b|"
                                    r"\btechnical\s+project\s+manager\b"),
    ("Product Management", r"\bproduct\s+manager\b|\bproduct\s+management\b|\bgroup\s+product\s+manager\b|\bprincipal\s+product\b|"
                           r"\bdirector,?\s+product\b|\bhead\s+of\s+product\b|\bproduct\s+lead\b|\bproduct\s+owner\b|\bpm,\s"),
    ("Product Design", r"\bproduct\s+design(?:er)?\b|\bux\s+design(?:er)?\b|\bui\s+design(?:er)?\b|\bux/ui\b|\bui/ux\b|"
                       r"\bdesign(?:er)?,?\s+(?:product|platform|systems?|growth|brand)\b|\bux\s+research(?:er)?\b|"
                       r"\bdesign\s+(?:manager|lead|director|systems)\b|\bhead\s+of\s+design\b|\bvisual\s+design(?:er)?\b|"
                       r"\binteraction\s+design(?:er)?\b|\bux\s+writer?\b|\bcontent\s+design(?:er)?\b|\bgraphic\s+design(?:er)?\b|"
                       r"\bmotion\s+design(?:er)?\b|\bbrand\s+design(?:er)?\b|\bdesign\s+engineer\b"),
    ("AI / ML Research", r"\bresearch\s+scientist\b|\bresearch\s+engineer\b|\bmember\s+of\s+technical\s+staff\b|"
                         r"\b(?:ai|ml|machine learning|deep learning)\s+research\b|\bresearch,?\s+(?:ai|ml|alignment|interpretability)\b|"
                         r"\bapplied\s+scientist\b|\bresearch\s+intern\b|\bpost[-\s]?doc"),
    ("Machine Learning Engineering", r"\b(?:machine\s+learning|ml|ai|deep\s+learning|nlp|computer\s+vision|cv)\s+engineer\b|"
                                     r"\bengineer,?\s+(?:machine\s+learning|ml|ai|inference|training|model)\b|"
                                     r"\bmlops\b|\bml\s+infrastructure\b|\bml\s+platform\b|\bai\s+engineer\b|"
                                     r"\bperception\s+engineer\b|\brobotics\s+engineer\b|\bautonomy\b|\bmodel\s+(?:training|serving)\b"),
    ("Data Science", r"\bdata\s+scientist\b|\bdata\s+science\b|\bquantitative\s+(?:analyst|research)\b|\bstatistician\b|"
                     r"\bdecision\s+scientist\b|\beconomist\b"),
    ("Data Engineering", r"\bdata\s+engineer\b|\banalytics\s+engineer\b|\bdata\s+platform\s+engineer\b|"
                         r"\bdata\s+infrastructure\b|\betl\b|\bdata\s+architect\b|\bdatabase\s+engineer\b"),
    ("Analytics & BI", r"\bdata\s+analyst\b|\bbusiness\s+intelligence\b|\b\bbi\s+(?:analyst|developer|engineer)\b|"
                       r"\banalytics\s+(?:manager|lead|analyst)\b|\bproduct\s+analyst\b|\bbusiness\s+analyst\b|"
                       r"\bmarketing\s+analyst\b|\bgrowth\s+analyst\b|\bfinancial\s+analyst,?\s+(?:data|tech)"),
    ("Security Engineering", r"\bsecurity\s+engineer\b|\bsecurity\s+(?:analyst|architect|researcher)\b|\bappsec\b|"
                             r"\bapplication\s+security\b|\binformation\s+security\b|\binfosec\b|\bcloud\s+security\b|"
                             r"\bproduct\s+security\b|\bdetection\s+(?:and\s+response|engineer)\b|\bincident\s+response\b|"
                             r"\bthreat\s+(?:detection|intelligence)\b|\bpenetration\s+test|\bred\s+team\b|\bciso\b|"
                             r"\bsecurity,\s|\bengineer,?\s+security\b|\btrust\s+(?:and|&)\s+safety\s+engineer\b"),
    ("Infrastructure & DevOps", r"\bsite\s+reliability\b|\bsre\b|\bdevops\b|\bplatform\s+engineer\b|\binfrastructure\s+engineer\b|"
                                r"\bcloud\s+engineer\b|\bsystems?\s+engineer\b|\bnetwork\s+engineer\b|\bdeveloper\s+(?:platform|productivity|experience)\s+engineer\b|"
                                r"\bengineer,?\s+(?:infrastructure|platform|cloud|networking|compute|storage|observability|developer)\b|"
                                r"\bkubernetes\b|\bobservability\b|\bproduction\s+engineer\b|\bdata\s?cent(?:er|re)\b"),
    ("QA & Test Engineering", r"\bqa\s+engineer\b|\bquality\s+(?:assurance|engineer)\b|\btest\s+engineer\b|"
                              r"\bsdet\b|\bautomation\s+engineer\b|\bengineer,?\s+(?:test|quality)\b|\btest\s+automation\b"),
    ("Mobile Engineering", r"\b(?:ios|android|mobile|react\s+native|flutter|swift|kotlin)\s+(?:engineer|developer)\b|"
                           r"\bengineer,?\s+(?:ios|android|mobile)\b|\bmobile\s+(?:platform|infrastructure)\b"),
    ("Frontend Engineering", r"\bfront[-\s]?end\s+(?:engineer|developer)\b|\bengineer,?\s+front[-\s]?end\b|"
                             r"\bweb\s+(?:engineer|developer)\b|\bui\s+engineer\b|\bclient\s+engineer\b|"
                             r"\b(?:react|typescript|javascript)\s+(?:engineer|developer)\b"),
    ("Full-Stack Engineering", r"\bfull[-\s]?stack\b|\bproduct\s+engineer\b|\bapplication\s+(?:engineer|developer)\b|"
                               r"\bgeneralist\s+(?:software\s+)?engineer\b|\bforward\s+deployed\s+engineer\b"),
    ("Developer Relations", r"\bdeveloper\s+(?:advocate|relations|evangelist)\b|\bdevrel\b|\bcommunity\s+engineer\b|"
                            r"\btechnical\s+(?:writer|content|curriculum)\b|\bdocumentation\s+engineer\b"),
    ("Solutions Engineering", r"\bsolutions?\s+(?:engineer|architect|consultant)\b|\bsales\s+engineer\b|\bgtm\s+engineer\b|"
                              r"\bimplementation\s+engineer\b|\bsupport\s+engineer\b|\bpartner\s+engineer\b|"
                              r"\bcustomer\s+engineer\b|\bprofessional\s+services\s+engineer\b|\bdeployment\s+(?:engineer|strategist)\b|"
                              r"\bfield\s+engineer\b|\btechnical\s+account\s+manager\b"),
    ("Backend Engineering", r"\bback[-\s]?end\s+(?:engineer|developer)\b|\bengineer,?\s+back[-\s]?end\b|"
                            r"\bapi\s+engineer\b|\bserver\s+engineer\b|\bdistributed\s+systems\b|\bcompiler\s+engineer\b|"
                            r"\b(?:go|golang|java|python|rust|ruby|scala|elixir|c\+\+)\s+(?:engineer|developer)\b"),
    # Generic software engineering last: anything still unlabelled that is clearly SWE.
    ("Software Engineering", r"\bsoftware\s+engineer(?:ing)?\b|\bsoftware\s+develop(?:er|ment)\b|\bswe\b|"
                             r"\bengineer\b|\bdeveloper\b|\bprogrammer\b|\barchitect\b"),
]
FAMILY_RULES = [(name, re.compile(pat, re.I)) for name, pat in FAMILY_RULES]

# Titles that must never enter the dataset even if a family regex would match them.
EXCLUDE_TITLE = re.compile(
    r"\baccount\s+executive\b|\baccount\s+manager\b|\bsales\s+(?:development|representative|manager|director|lead)\b|"
    r"\bsdr\b|\bbdr\b|\bbusiness\s+development\b|\brecruit(?:er|ing)\b|\btalent\s+(?:acquisition|partner|sourcer)\b|"
    r"\bsourcer\b|\bpeople\s+(?:partner|operations|business)\b|\bhr\b|\bpayroll\b|\bbenefits\b|"
    r"\bcontroller\b|\baccountant\b|\baccounting\b|\bbookkeep|\btax\b|\btreasury\b|\baudit\b|"
    r"\battorney\b|\bcounsel\b|\bparalegal\b|\blegal\b|\bcompliance\s+(?:officer|analyst|manager)\b|"
    r"\bcustomer\s+success\b|\bcustomer\s+support\s+(?:agent|representative|specialist)\b|"
    r"\boffice\s+(?:manager|coordinator)\b|\bexecutive\s+assistant\b|\breceptionist\b|\bfacilities\b|"
    r"\bevent\s+(?:manager|coordinator)\b|\bsocial\s+media\b|\bcopywriter\b|\bpublic\s+relations\b|"
    r"\bdemand\s+gen|\blifecycle\s+marketing\b|\bmarketing\s+(?:manager|director|lead|associate|coordinator|specialist)\b|"
    r"\bbrand\s+(?:manager|marketing)\b|\bproduct\s+marketing\b|\bchief\s+of\s+staff\b|"
    r"\bwarehouse\b|\bdriver\b|\btechnician,?\s+(?:field|install)|\binstaller\b|\bassembler\b|"
    r"\bnurse\b|\bphysician\b|\btherapist\b|\bclinician\b|\bpharmac|\bmedical\s+assistant\b|"
    r"\bteacher\b|\btutor\b|\bcoach,\s|\bbarista\b|\bsecurity\s+guard\b|\bjanitor\b|"
    r"\bmanufacturing\s+(?:associate|operator|test|quality|technician)\b|\bproduction\s+(?:associate|operator)\b|"
    r"\bmechanical\s+engineer\b|\belectrical\s+engineer\b|\bcivil\s+engineer\b|\bindustrial\s+engineer\b|"
    r"\binspector\b|\bproducer\b|\bvideographer\b|\bphotographer\b|\billustrator\b|"
    r"\bmanufacturing\s+engineer\b|\bprocess\s+engineer\b|\bthermal\s+engineer\b|\bhardware\s+engineer\b|"
    r"\bpcb\b|\brf\s+engineer\b|\bstructural\s+engineer\b|\bfield\s+service\b|\bsupply\s+chain\b|"
    r"\bexpression\s+of\s+interest\b|\bgeneral\s+application\b|\btalent\s+(?:pool|network|community)\b|"
    r"\bfuture\s+(?:opportunities|openings)\b|\bspeculative\b|\bdon'?t\s+see\s+(?:a|the)\s+role\b",
    re.I,
)

# Hardware, silicon and facilities engineering: real engineering, but not the software /
# data / product / design families this demo is about. Applied only when the title is not
# explicitly a software role, so "Software Engineer, Trust & Safety" survives.
HARDWARE_TITLE = re.compile(
    r"\beh\s?&?\s?s\b|\benvironmental\b|\bindustrial\s+hygien|\bfire\s+protection\b|"
    r"^\s*compliance\s+engineer|^\s*safety\s+engineer|^\s*validation\s+engineer|"
    r"\bfield\s+(?:applications?|reliability|service)\s+engineer\b|"
    r"\bhardware\b|\bsilicon\b|\bsoc\b|\brtl\b|\bchiplet\b|\bphysical\s+design\b|\bpcie\b|"
    r"\bemulation\b|\basic\b|\bvlsi\b|\btapeout\b|\bcharacterization\s+engineer\b|"
    r"\bsignal\s+integrity\b|\banalog\s+design\b|\bpackaging\s+engineer\b",
    re.I,
)
_IS_SOFTWARE = re.compile(r"\bsoftware\s+(?:engineer|develop)|\bfirmware\b", re.I)

SENIORITY_RULES = [
    ("Internship", r"\bintern(?:ship)?\b|\bco[-\s]?op\b|\bapprentice\b|\bsummer\s+20\d\d\b|\bphd\s+intern"),
    ("Executive", r"\bvp\b|\bvice\s+president\b|\bchief\b|\bc[te]o\b|\bciso\b|\bcto\b|\bhead\s+of\b|\bgeneral\s+manager\b"),
    ("Director", r"\bdirector\b|\bsenior\s+manager\b|\bgroup\s+(?:product\s+)?manager\b"),
    ("Staff / Principal", r"\bstaff\b|\bprincipal\b|\bdistinguished\b|\bfellow\b|\barchitect\b|\bsenior\s+staff\b|\bl[67]\b"),
    ("Senior", r"\bsenior\b|\bsr\.?\b|\blead\b|\biii\b|\bmanager\b|\bexperienced\b"),
    ("Entry level", r"\bnew\s+grad(?:uate)?\b|\bjunior\b|\bjr\.?\b|\bentry[-\s]level\b|\bassociate\b|\bearly\s+career\b|"
                    r"\bgraduate\s+(?:program|engineer)\b|\buniversity\s+grad|\b\bi\b(?!i)"),
]
SENIORITY_RULES = [(name, re.compile(pat, re.I)) for name, pat in SENIORITY_RULES]

EDU_RULES = [
    ("Doctorate", r"\bph\.?\s?d\b|\bdoctorate\b|\bdoctoral\b"),
    ("Master's Degree", r"\bmaster'?s?\b|\bm\.?s\.?\b\s+(?:in|degree)|\bmba\b|\bm\.?sc\b"),
    ("Bachelor's Degree", r"\bbachelor'?s?\b|\bb\.?s\.?\b\s+(?:in|degree)|\bb\.?a\.?\b\s+(?:in|degree)|"
                          r"\bundergraduate\s+degree\b|\bdegree\s+in\s+computer\s+science\b|\bbs/ms\b"),
]
EDU_RULES = [(name, re.compile(pat, re.I)) for name, pat in EDU_RULES]

HYBRID_CADENCE = re.compile(
    r"""(
     \d\+?\s*(?:\(\w+\)\s*)?days?\s+(?:per\s+week\s+|a\s+week\s+|each\s+week\s+|/\s*week\s+)?(?:in|at|from|onsite|on-site|in-office)\b
    |\bin\s+(?:the\s+)?office\s+\d\+?\s*days?
    |\bhybrid\s+(?:work\s+)?(?:model|schedule|policy|arrangement|role|position|environment)\b
    |\bhybrid\s*[-:]\s*\d
    |\bthis\s+(?:is\s+a\s+)?hybrid\s+(?:role|position)
    |\bhybrid\s+in\b
    |\bonsite\s+\d\+?\s*days?
    )""",
    re.I | re.X,
)
FULLY_REMOTE_TEXT = re.compile(
    r"\bfully\s+remote\b|\bremote[-\s]first\b|\b100%\s+remote\b|\ball[-\s]remote\b|\bwork\s+from\s+anywhere\b", re.I
)


def classify_family(title: str, department: str = "", team: str = ""):
    """Map a job title (with department/team as a tie-breaker) to a tech job family."""
    t = f" {title} "
    if EXCLUDE_TITLE.search(t):
        return None
    if HARDWARE_TITLE.search(title) and not _IS_SOFTWARE.search(t):
        return None
    for name, rx in FAMILY_RULES:
        if rx.search(t):
            return name
    # Fall back to the department for titles the title rules miss.
    ctx = f" {department} {team} "
    for name, rx in FAMILY_RULES:
        if rx.search(ctx):
            return name
    return None


def classify_seniority(title: str) -> str:
    t = f" {title} "
    for name, rx in SENIORITY_RULES:
        if rx.search(t):
            return name
    return "Mid level"


def classify_education(text: str) -> str:
    """
    Report the *lowest* degree the posting mentions, since that is the real bar:
    "BS/MS or PhD in a related field" is a Bachelor's requirement, not a doctorate.
    """
    for name, rx in reversed(EDU_RULES):
        if rx.search(text):
            return name
    return "Not Specified"


def classify_jobtype(title: str, raw_type: str) -> str:
    rt = (raw_type or "").strip().lower()
    mapping = {
        "fulltime": "Full-time", "full-time": "Full-time", "full time": "Full-time",
        "parttime": "Part-time", "part-time": "Part-time", "part time": "Part-time",
        "intern": "Internship", "internship": "Internship",
        "contract": "Contract", "contractor": "Contract", "temporary": "Contract",
    }
    if rt in mapping:
        return mapping[rt]
    if re.search(r"\bintern(?:ship)?\b|\bco[-\s]?op\b", title, re.I):
        return "Internship"
    if re.search(r"\bcontract(?:or)?\b|\btemporary\b", title, re.I):
        return "Contract"
    if re.search(r"\bpart[-\s]?time\b", title, re.I):
        return "Part-time"
    return "Full-time"


_STRIP_TAGS_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|video|audio|form)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.I | re.S,
)
_VOID_TAGS_RE = re.compile(r"<\s*(img|source|track|input|iframe)\b[^>]*/?>", re.I)


def sanitize_description(raw_html: str) -> str:
    """
    Drop embedded/external content from the stored HTML. The web app renders these
    descriptions with dangerouslySetInnerHTML, so a stray iframe or a hotlinked image
    would either break the layout or pull in a third-party request mid-demo.
    """
    html_out = _STRIP_TAGS_RE.sub(" ", raw_html)
    html_out = _VOID_TAGS_RE.sub(" ", html_out)
    html_out = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", html_out, flags=re.I)
    return re.sub(r"[ \t]+\n", "\n", html_out).strip()


def is_english(text: str) -> bool:
    """Reject postings written in a non-Latin script (the feeds carry some JA/KO/ZH copy)."""
    sample = text[:1500]
    if not sample:
        return False
    letters = [c for c in sample if c.isalpha()]
    if not letters:
        return False
    ascii_letters = sum(1 for c in letters if c.isascii())
    return ascii_letters / len(letters) > 0.85


# --------------------------------------------------------------------------------------
# Fetch + normalize
# --------------------------------------------------------------------------------------


def fetch_board(ats: str, token: str, cache_dir: str | None = None) -> list:
    """Return the raw posting list for one board, using cache_dir when available."""
    path = os.path.join(cache_dir, f"{ats}__{token}.json") if cache_dir else None
    if path and os.path.exists(path) and os.path.getsize(path) > 100:
        with open(path) as f:
            payload = json.load(f)
    else:
        r = requests.get(BOARD_URLS[ats].format(token=token), headers=UA, timeout=120)
        r.raise_for_status()
        payload = r.json()
        if path:
            os.makedirs(cache_dir, exist_ok=True)
            with open(path, "w") as f:
                json.dump(payload, f)
    if isinstance(payload, list):
        return payload
    return payload.get("jobs") or []


def normalize(ats: str, token: str, company: str, raw: dict):
    """Convert one raw ATS posting into the canonical feed record, or None to drop it."""
    if ats == "greenhouse":
        title = (raw.get("title") or "").strip()
        loc_raw = ((raw.get("location") or {}).get("name") or "").strip()
        desc = html.unescape(raw.get("content") or "")
        depts = [d.get("name", "") for d in (raw.get("departments") or [])]
        dept = re.sub(r"^\d+\s+", "", depts[0]) if depts else ""
        team = ""
        url = raw.get("absolute_url") or ""
        job_id = str(raw.get("id") or "")
        date = (raw.get("first_published") or raw.get("updated_at") or "")[:10]
        raw_type = ""
        explicit_workplace = None
        company = raw.get("company_name") or company
        # Greenhouse offices sometimes carry a cleaner location than the location string.
        office_names = [o.get("name") or "" for o in (raw.get("offices") or [])]
        loc_candidates = [loc_raw] + office_names

    elif ats == "lever":
        title = (raw.get("text") or "").strip()
        cats = raw.get("categories") or {}
        loc_raw = (cats.get("location") or "").strip()
        desc = (raw.get("descriptionBody") or raw.get("description") or "")
        extra = raw.get("additional") or ""
        lists = raw.get("lists") or []
        list_html = "".join(
            f"<h3>{l.get('text','')}</h3><ul>{l.get('content','')}</ul>" for l in lists
        )
        desc = f"{desc}{list_html}{extra}"
        dept = cats.get("department") or ""
        team = cats.get("team") or ""
        url = raw.get("hostedUrl") or ""
        job_id = str(raw.get("id") or "")
        created = raw.get("createdAt")
        date = (
            datetime.fromtimestamp(int(created) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if created else ""
        )
        raw_type = cats.get("commitment") or ""
        wt = (raw.get("workplaceType") or "").lower()
        explicit_workplace = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}.get(wt)
        all_locs = cats.get("allLocations") or []
        loc_candidates = [loc_raw] + [str(x) for x in all_locs]
        if raw.get("country") in ("US", "CA"):
            loc_candidates.append("United States" if raw["country"] == "US" else "Canada")

    else:  # ashby
        title = (raw.get("title") or "").strip()
        loc_raw = (raw.get("location") or "").strip()
        desc = raw.get("descriptionHtml") or ""
        dept = raw.get("department") or ""
        team = raw.get("team") or ""
        url = raw.get("jobUrl") or ""
        job_id = str(raw.get("id") or "")
        date = (raw.get("publishedAt") or "")[:10]
        raw_type = raw.get("employmentType") or ""
        wt = (raw.get("workplaceType") or "").lower()
        explicit_workplace = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}.get(wt)
        addr = ((raw.get("address") or {}).get("postalAddress") or {})
        loc_candidates = [loc_raw]
        locality, region, country = (
            addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry"),
        )
        if locality or region or country:
            loc_candidates.append(", ".join(x for x in (locality, region, country) if x))
        for sec in raw.get("secondaryLocations") or []:
            if sec.get("location"):
                loc_candidates.append(sec["location"])
        if raw.get("isListed") is False:
            return None

    if not title or not desc or not job_id:
        return None
    desc = sanitize_description(desc)
    if len(re.sub(r"<[^>]+>", " ", desc).strip()) < 400:
        return None
    if not is_english(re.sub(r"<[^>]+>", " ", desc)) or not is_english(title):
        return None

    family = classify_family(title, dept, team)
    if not family:
        return None

    parsed = None
    hint = None
    for cand in loc_candidates:
        p = parse_location(cand)
        if p:
            if hint is None and p[3]:
                hint = p[3]
            if parsed is None or (parsed[0] == "Unknown" and p[0] != "Unknown"):
                parsed = p
            if parsed and parsed[0] != "Unknown":
                break
    if not parsed:
        return None
    city, region, country, loc_hint, _ = parsed
    hint = hint or loc_hint

    plain = re.sub(r"<[^>]+>", " ", desc)
    plain = re.sub(r"\s+", " ", plain)

    # Workplace precedence: explicit ATS field > location keyword > description evidence.
    workplace = explicit_workplace
    if not workplace:
        if hint == "Remote" or FULLY_REMOTE_TEXT.search(plain[:4000]):
            workplace = "Remote"
        elif hint == "Hybrid" or HYBRID_CADENCE.search(plain):
            workplace = "Hybrid"
        else:
            workplace = "On-site"
    elif workplace == "On-site" and hint == "Remote":
        workplace = "Remote"

    if workplace == "Remote" and city == "Unknown":
        city = "Remote"

    return {
        "id": f"{ats[:2]}-{token}-{job_id}"[:64],
        "title": title,
        "company": company.strip(),
        "city": city or "Unknown",
        "state": region or "Unknown",
        "country": country,
        "remote": workplace == "Remote",
        "workplace": workplace,
        "description": desc,
        "education": classify_education(plain),
        "job_type": classify_jobtype(title, raw_type),
        "category": family,
        "experience": classify_seniority(title),
        "department": dept.strip(),
        "team": team.strip(),
        "url": url,
        "date": date,
        "source": ats,
    }


def collect(cache_dir=None, workers=12, max_per_company=45):
    """Fetch and normalize every board. Returns (records, stats)."""
    stats = Counter()
    errors = []

    def one(board):
        ats, token, company = board
        try:
            raw_jobs = fetch_board(ats, token, cache_dir)
        except Exception as e:  # a dead board should not sink the whole run
            errors.append(f"{ats}/{token}: {e}")
            return []
        out = []
        for raw in raw_jobs:
            try:
                rec = normalize(ats, token, company, raw)
            except Exception:
                rec = None
            if rec:
                out.append(rec)
        stats[f"raw:{ats}"] += len(raw_jobs)
        stats[f"kept:{ats}"] += len(out)
        return out

    records = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for batch in ex.map(one, BOARDS):
            records.extend(batch)

    # Drop repostings of the same role and cap any single company's share of the feed.
    seen = set()
    by_company = defaultdict(int)
    deduped = []
    records.sort(key=lambda r: (r["company"], r["category"], r["title"]))
    for r in records:
        key = (r["company"].lower(), r["title"].lower().strip())
        if key in seen:
            stats["dropped:duplicate"] += 1
            continue
        if by_company[r["company"]] >= max_per_company:
            stats["dropped:company_cap"] += 1
            continue
        seen.add(key)
        by_company[r["company"]] += 1
        deduped.append(r)

    return deduped, stats, errors


# --------------------------------------------------------------------------------------
# XML output
# --------------------------------------------------------------------------------------

FEED_FIELDS = [
    ("referencenumber", "id"), ("title", "title"), ("company", "company"),
    ("city", "city"), ("state", "state"), ("country", "country"),
    ("remote", None), ("workplace", "workplace"), ("jobtype", "job_type"),
    ("category", "category"), ("experience", "experience"), ("education", "education"),
    ("department", "department"), ("team", "team"), ("url", "url"), ("date", "date"),
    ("feedsource", "source"), ("description", "description"),
]


def write_xml(records, path):
    root = etree.Element("source")
    etree.SubElement(root, "publisher").text = "job-rec-demo tech feed"
    etree.SubElement(root, "publisherurl").text = "https://github.com/jimmymarsanico/job-rec-demo"
    etree.SubElement(root, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )
    for r in records:
        j = etree.SubElement(root, "job")
        for tag, key in FEED_FIELDS:
            el = etree.SubElement(j, tag)
            el.text = "true" if tag == "remote" and r["remote"] else (
                "false" if tag == "remote" else (r.get(key) or "")
            )
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    etree.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/tech_jobs_feed.xml")
    ap.add_argument("--cache-dir", default=None, help="reuse/populate raw board JSON here")
    ap.add_argument("--gzip", action="store_true", help="also write <out>.gz")
    ap.add_argument("--max-per-company", type=int, default=45)
    args = ap.parse_args()

    print(f"Fetching {len(BOARDS)} ATS job boards (greenhouse / lever / ashby)...")
    records, stats, errors = collect(args.cache_dir, max_per_company=args.max_per_company)

    for ats in ("greenhouse", "lever", "ashby"):
        print(f"  {ats:<11} {stats[f'raw:{ats}']:>6,} postings -> {stats[f'kept:{ats}']:>5,} tech US/CA")
    print(f"  dropped {stats['dropped:duplicate']:,} duplicate titles, "
          f"{stats['dropped:company_cap']:,} over the per-company cap")
    if errors:
        print(f"  {len(errors)} board(s) failed: {', '.join(errors[:5])}")

    print(f"\nFeed: {len(records):,} jobs, {len({r['company'] for r in records})} companies")
    print("  workplace:", dict(Counter(r["workplace"] for r in records)))
    print("  country:  ", dict(Counter(r["country"] for r in records)))
    print("  top families:", Counter(r["category"] for r in records).most_common(8))

    size = write_xml(records, args.out)
    print(f"\nWrote {args.out} ({size / 1024 / 1024:.1f} MB)")
    if args.gzip:
        gz = args.out + ".gz"
        with open(args.out, "rb") as fi, gzip.open(gz, "wb", compresslevel=9) as fo:
            shutil.copyfileobj(fi, fo)
        print(f"Wrote {gz} ({os.path.getsize(gz) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
