"""
RemoteKazi aggregator: fetch -> dedupe -> Claude cleanup -> write jobs.json (read by index.html).

Install:  pip install requests feedparser anthropic
Env vars: ANTHROPIC_API_KEY (required), JOOBLE_KEY (optional)
Run:      python job_aggregator.py     (the GitHub Action in .github/workflows runs it daily)
"""
import hashlib
import html
import json
import os
import re
from datetime import date, datetime, timedelta

import anthropic
import feedparser
import requests

OUT, SEEN = "jobs.json", "seen.json"
JOOBLE_KEY = os.environ.get("JOOBLE_KEY")
MODEL = "claude-sonnet-5-5"
MAX_PER_SOURCE = 25       # max listings checked per source per run (caps cost)
MAX_PER_SOURCE_BOARDS = 60
MAX_AGE_DAYS = 14         # a listing stays up until its deadline, or at most 14 days after we first saw it
ALLOWED_RISK = {"low"}    # no human review step, so only publish low-risk jobs
HEADERS = {"User-Agent": "RemoteKaziBot/1.0 (+https://remotekazi.com/about/)"}

client = anthropic.Anthropic()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def strip(html):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html or "")).strip()


# ---------- FETCH (feeds/APIs that allow reuse; always link back to the source) ----------
def fetch_remoteok():
    r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=30)
    for j in r.json()[1:]:
        yield {"src": "RemoteOK", "title": j.get("position", ""), "company": j.get("company", ""),
               "location": j.get("location") or "Remote", "text": strip(j.get("description")), "url": j.get("url", "")}


def fetch_wwr():
    for e in feedparser.parse("https://weworkremotely.com/remote-jobs.rss").entries:
        yield {"src": "WeWorkRemotely", "title": e.title, "company": "", "location": "Remote",
               "text": strip(e.get("summary")), "url": e.link}


def fetch_jooble():
    if not JOOBLE_KEY:
        print("[fetch_jooble] skipped: JOOBLE_KEY secret is not set")
        return
    for loc in ["Nairobi", "Mombasa", "Kisumu", "Kenya"]:
        r = requests.post(f"https://jooble.org/api/{JOOBLE_KEY}", json={"keywords": "", "location": loc}, timeout=30)
        for j in r.json().get("jobs", []):
            yield {"src": "Jooble", "title": j.get("title", ""), "company": j.get("company", ""),
                   "location": j.get("location") or loc, "text": strip(j.get("snippet")), "url": j.get("link", "")}


def fetch_jvn():
    """Job Vacancies Now: uses its public WordPress REST API, falling back to its job feeds. Link-back only."""
    base = "https://jobvacanciesnow.com"
    try:
        r = requests.get(base + "/wp-json/wp/v2/job-listings?per_page=20", headers=HEADERS, timeout=30)
        data = r.json() if r.ok else None
        if isinstance(data, list) and data:
            for j in data:
                yield {"src": "JobVacanciesNow", "title": strip(j["title"]["rendered"]), "company": "",
                       "location": "Kenya", "text": strip(j.get("excerpt", {}).get("rendered")), "url": j["link"]}
            return
    except Exception as e:
        print(f"[jvn] REST failed: {e}")
    for u in (base + "/?feed=job_feed", base + "/feed/?post_type=job_listing"):
        entries = feedparser.parse(u).entries
        if entries:
            for e in entries:
                yield {"src": "JobVacanciesNow", "title": e.title, "company": "", "location": "Kenya",
                       "text": strip(e.get("summary")), "url": e.link}
            return
    print("[jvn] no feed found; check the site's job feed URL")


def fetch_remotive():
    """Remotive public API. Check their terms: link back and credit the source (done automatically)."""
    r = requests.get("https://remotive.com/api/remote-jobs?limit=60", headers=HEADERS, timeout=30)
    for j in r.json().get("jobs", []):
        yield {"src": "Remotive", "title": j.get("title", ""), "company": j.get("company_name", ""),
               "location": j.get("candidate_required_location") or "Remote", "text": strip(j.get("description")),
               "url": j.get("url", "")}


# Kenyan employers / NGOs / boards that allow reuse of their feed. Add as ("Name", "https://.../feed").
EMPLOYER_FEEDS = []


def fetch_employer_feeds():
    for name, url in EMPLOYER_FEEDS:
        for e in feedparser.parse(url).entries:
            yield {"src": name, "title": e.title, "company": name, "location": "Kenya",
                   "text": strip(e.get("summary")), "url": e.link}


RELIEFWEB_APPNAME = os.environ.get("RELIEFWEB_APPNAME")   # register a free app name at apidoc.reliefweb.int


def fetch_reliefweb():
    """UN / NGO / humanitarian jobs in Kenya from the ReliefWeb API (long descriptions, real deadlines)."""
    if not RELIEFWEB_APPNAME:
        print("[fetch_reliefweb] skipped: RELIEFWEB_APPNAME secret is not set")
        return
    body = {"limit": 30, "sort": ["date.created:desc"],
            "filter": {"field": "country.iso3", "value": "KEN"},
            "fields": {"include": ["title", "url", "body", "date.closing", "source.name"]}}
    r = requests.post(f"https://api.reliefweb.int/v2/jobs?appname={RELIEFWEB_APPNAME}", json=body, headers=HEADERS, timeout=30)
    r.raise_for_status()
    for it in r.json().get("data", []):
        f = it.get("fields", {})
        yield {"src": "ReliefWeb", "title": f.get("title", ""), "company": (f.get("source") or [{}])[0].get("name", ""),
               "location": "Kenya", "text": strip(f.get("body")) + " Closing date: " + (f.get("date", {}).get("closing", "") or "")[:10],
               "url": f.get("url", "")}


# Employer job boards that publish public JSON feeds. Add the board name from the careers-page address:
#   Greenhouse: boards.greenhouse.io/<name>   Lever: jobs.lever.co/<name>   Workable: apply.workable.com/<name>
# Format: ("Display name", "<board name>"). Only Kenya / Africa-eligible roles pass the Claude filter.
GREENHOUSE = []
LEVER = []
WORKABLE = []


def fetch_boards():
    for name, tok in GREENHOUSE:
        try:
            d = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=true", headers=HEADERS, timeout=30).json()
            for j in d.get("jobs", []):
                yield {"src": name, "title": j.get("title", ""), "company": name,
                       "location": (j.get("location") or {}).get("name", ""),
                       "text": strip(html.unescape(j.get("content", ""))), "url": j.get("absolute_url", "")}
        except Exception as e:
            print(f"[greenhouse:{tok}] {e}")
    for name, tok in LEVER:
        try:
            for j in requests.get(f"https://api.lever.co/v0/postings/{tok}?mode=json", headers=HEADERS, timeout=30).json():
                yield {"src": name, "title": j.get("text", ""), "company": name,
                       "location": (j.get("categories") or {}).get("location", ""),
                       "text": j.get("descriptionPlain", ""), "url": j.get("hostedUrl", "")}
        except Exception as e:
            print(f"[lever:{tok}] {e}")
    for name, tok in WORKABLE:
        try:
            d = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{tok}?details=true", headers=HEADERS, timeout=30).json()
            for j in d.get("jobs", []):
                yield {"src": name, "title": j.get("title", ""), "company": name,
                       "location": ", ".join(x for x in (j.get("city"), j.get("country")) if x),
                       "text": strip(j.get("description")), "url": j.get("url", "")}
        except Exception as e:
            print(f"[workable:{tok}] {e}")



# Add employer RSS feeds or career pages here after checking each site's robots.txt and terms.
SOURCES = [fetch_reliefweb, fetch_boards, fetch_jvn, fetch_employer_feeds, fetch_jooble, fetch_remoteok, fetch_wwr, fetch_remotive]  # Kenya sources first

PROMPT = """You clean job listings for a Kenyan job board. Return ONLY JSON, no markdown.

Title: {title}
Company: {company}
Location: {location}
Text: {text}

JSON keys:
- keep: true only if the job is based in Kenya, OR is remote AND open to applicants in Kenya/Africa/worldwide.
  false if remote but restricted to US/EU/other regions.
- scam_risk: "low", "medium" or "high". Raise it for fees/deposits, personal-email or WhatsApp-only contact,
  unrealistic pay, or a vague employer.
- detail: "good" if the text states duties or requirements, "basic" if it only names the role and employer,
  "none" if it says almost nothing beyond the title.
- title, company: cleaned
- location: "Nairobi", "Mombasa" or "Kisumu" only if the text says so; otherwise "Other Kenya" for Kenyan jobs, or "Remote".
- type: "Full-time", "Part-time", "Contract" or "Internship" only if stated; otherwise "Not stated"
- category: one of "Tech", "Finance", "Health", "Education", "Sales", "Logistics", "Other"
- pay: as stated, or ""
- deadline: YYYY-MM-DD or ""
- summary: 1-3 sentences in YOUR OWN words using only facts stated in the text. Never guess or assume. Never use
  the words assumed, likely, appears, truncated or excerpt, and never comment on missing information.
  If little is stated, write one short factual sentence.
"""


def clean(job):
    msg = client.messages.create(model=MODEL, max_tokens=700, messages=[{"role": "user", "content": PROMPT.format(
        title=job["title"], company=job["company"], location=job["location"], text=job["text"][:3500])}])
    raw = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
    return json.loads(raw)


def main():
    jobs = load(OUT, [])
    seen = set(load(SEEN, []))
    today = date.today()
    by_id = {}
    for j in jobs:                      # remove duplicates (keep the latest copy of each job)
        by_id[j["id"]] = j
    jobs = list(by_id.values())
    bad = re.compile(r"truncat|excerpt|assum|appears|likely|not stated|not named|unclear|not given", re.I)   # old low-quality summaries get redone with the new prompt
    stale = {j["id"] for j in jobs if bad.search(j.get("x", ""))}
    jobs = [j for j in jobs if j["id"] not in stale]
    seen -= stale

    # drop expired / old listings (manual edits such as "f": 1 for featured are preserved)
    def alive(j):
        if j.get("deadline") and j["deadline"] < today.isoformat():
            return False
        if j.get("src") == "Direct":     # jobs you add by hand last until their deadline
            return True
        return (today - datetime.fromisoformat(j["posted"]).date()).days < MAX_AGE_DAYS
    jobs = [j for j in jobs if alive(j)]

    new = skipped = risky = 0
    for fetch in SOURCES:
        try:
            batch = list(fetch())
        except Exception as e:
            print(f"[{fetch.__name__}] failed: {e}")
            continue
        n_src = 0
        k0, s0, r0 = new, skipped, risky
        for job in batch:
            if n_src >= (MAX_PER_SOURCE_BOARDS if fetch is fetch_boards else MAX_PER_SOURCE):
                break
            url = job["url"]
            if not url.startswith("http"):
                continue
            jid = hashlib.sha1(url.encode()).hexdigest()[:16]
            if jid in seen:
                continue
            seen.add(jid)
            n_src += 1
            try:
                c = clean(job)
            except Exception as e:
                print(f"Cleanup failed for {url}: {e}")
                continue
            if not c.get("keep") or c.get("detail") == "none":
                skipped += 1
                continue
            if c.get("scam_risk") not in ALLOWED_RISK:
                risky += 1
                continue
            jobs.append({"id": jid, "t": c["title"], "c": c["company"] or "Employer", "l": c["location"],
                         "k": c["category"], "y": c["type"], "p": c.get("pay", ""), "x": c["summary"],
                         "u": url, "src": job["src"], "deadline": c.get("deadline", ""),
                         "posted": today.isoformat(), "f": 0})
            new += 1
        print(f"[{fetch.__name__}] fetched {len(batch)}, checked {n_src}, added {new - k0}, "
              f"not Kenya-eligible {skipped - s0}, scam-risk {risky - r0}")

    jobs.sort(key=lambda j: j["posted"], reverse=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    with open(SEEN, "w") as f:
        json.dump(sorted(seen), f)
    print(f"Added {new}, filtered out {skipped}, total live {len(jobs)}")


if __name__ == "__main__":
    main()
