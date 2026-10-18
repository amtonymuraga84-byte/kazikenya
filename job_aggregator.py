"""
KaziKE aggregator: fetch -> dedupe -> Claude cleanup -> write jobs.json (read by index.html).

Install:  pip install requests feedparser anthropic
Env vars: ANTHROPIC_API_KEY (required), JOOBLE_KEY (optional)
Run:      python job_aggregator.py     (the GitHub Action in .github/workflows runs it daily)
"""
import hashlib
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
MAX_NEW_PER_RUN = 40      # caps API cost per run
MAX_AGE_DAYS = 45         # drop listings older than this
ALLOWED_RISK = {"low"}    # no human review step, so only publish low-risk jobs
HEADERS = {"User-Agent": "KaziKEBot/1.0 (+https://yoursite.co.ke/#about)"}

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
        return
    for loc in ["Nairobi", "Mombasa", "Kisumu", "Kenya"]:
        r = requests.post(f"https://jooble.org/api/{JOOBLE_KEY}", json={"keywords": "", "location": loc}, timeout=30)
        for j in r.json().get("jobs", []):
            yield {"src": "Jooble", "title": j.get("title", ""), "company": j.get("company", ""),
                   "location": j.get("location") or loc, "text": strip(j.get("snippet")), "url": j.get("link", "")}


# Add employer RSS feeds or career pages here after checking each site's robots.txt and terms.
SOURCES = [fetch_remoteok, fetch_wwr, fetch_jooble]

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
- title, company: cleaned
- location: one of "Nairobi", "Mombasa", "Kisumu", "Other Kenya", "Remote"
- type: "Full-time", "Part-time", "Contract" or "Internship"
- category: one of "Tech", "Finance", "Health", "Education", "Sales", "Logistics", "Other"
- pay: as stated, or ""
- deadline: YYYY-MM-DD or ""
- summary: 2-3 sentences in YOUR OWN words on the role and key requirements (never copy the text)
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

    # drop expired / old listings (manual edits such as "f": 1 for featured are preserved)
    def alive(j):
        if j.get("deadline") and j["deadline"] < today.isoformat():
            return False
        return datetime.fromisoformat(j["posted"]).date() >= today - timedelta(days=MAX_AGE_DAYS)
    jobs = [j for j in jobs if alive(j)]

    new = skipped = 0
    for fetch in SOURCES:
        try:
            batch = list(fetch())
        except Exception as e:
            print(f"[{fetch.__name__}] failed: {e}")
            continue
        for job in batch:
            if new >= MAX_NEW_PER_RUN:
                break
            url = job["url"]
            if not url.startswith("http"):
                continue
            jid = hashlib.sha1(url.encode()).hexdigest()[:16]
            if jid in seen:
                continue
            seen.add(jid)
            try:
                c = clean(job)
            except Exception as e:
                print(f"Cleanup failed for {url}: {e}")
                continue
            if not c.get("keep") or c.get("scam_risk") not in ALLOWED_RISK:
                skipped += 1
                continue
            jobs.append({"id": jid, "t": c["title"], "c": c["company"] or "Employer", "l": c["location"],
                         "k": c["category"], "y": c["type"], "p": c.get("pay", ""), "x": c["summary"],
                         "u": url, "src": job["src"], "deadline": c.get("deadline", ""),
                         "posted": today.isoformat(), "f": 0})
            new += 1

    jobs.sort(key=lambda j: j["posted"], reverse=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    with open(SEEN, "w") as f:
        json.dump(sorted(seen), f)
    print(f"Added {new}, filtered out {skipped}, total live {len(jobs)}")


if __name__ == "__main__":
    main()
