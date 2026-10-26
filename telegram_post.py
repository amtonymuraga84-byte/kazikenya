"""
Posts new jobs to your Telegram channel with a link back to the job page on your site.
Needs two GitHub secrets: TELEGRAM_BOT_TOKEN (from @BotFather) and TELEGRAM_CHAT_ID (e.g. @kazikejobs).
The bot must be an admin of the channel. Without the secrets this script only reports how many jobs are waiting.
"""
import html
import json
import os
import time
from pathlib import Path

import requests

from build_site import SITE_URL

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT = os.environ.get("TELEGRAM_CHAT_ID")
MAX_POSTS = 10  # per run, so the channel is never flooded


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    jobs = load("jobs.json", [])
    posted = set(load("posted.json", []))
    new = sorted([j for j in jobs if j["id"] not in posted and j.get("slug")], key=lambda j: j["posted"], reverse=True)
    if not (TOKEN and CHAT):
        print(f"Telegram not configured; {len(new)} jobs waiting to be posted")
        return
    for j in new[:MAX_POSTS]:
        e = html.escape
        text = (f"💼 <b>{e(j['t'])}</b>\n{e(j['c'])} · {e(j['l'])} · {e(j['y'])}\n"
                + (f"💰 {e(j['p'])}\n" if j.get("p") else "")
                + f"\n🔗 {SITE_URL}/jobs/{j['slug']}/\n\nMore jobs: {SITE_URL}")
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          data={"chat_id": CHAT, "text": text, "parse_mode": "HTML"}, timeout=30)
        if r.ok:
            posted.add(j["id"])
        else:
            print("Telegram error:", r.status_code, r.text[:200])
            if r.status_code in (401, 403, 429):
                break
        time.sleep(3)
    for j in new[MAX_POSTS:]:  # older backlog is skipped, not posted later
        posted.add(j["id"])
    Path("posted.json").write_text(json.dumps(sorted(posted)), encoding="utf-8")
    print(f"Posted up to {MAX_POSTS} jobs; {len(posted)} marked as posted")


if __name__ == "__main__":
    main()
