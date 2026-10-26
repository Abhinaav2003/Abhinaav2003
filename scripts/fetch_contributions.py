#!/usr/bin/env python3
"""Fetch daily contributions for the user in config.py and write data/contributions.json.
Tries GitHub's public contributions page first, then falls back to a public API."""
import datetime, json, os, re, sys
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import USERNAME

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "contributions.json")
HEAD = {"User-Agent": "Mozilla/5.0 (profile-readme-bot)"}


def from_github():
    r = requests.get(f"https://github.com/users/{USERNAME}/contributions", headers=HEAD, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    days = []
    for td in soup.select("td.ContributionCalendar-day"):
        date = td.get("data-date")
        if not date:
            continue
        tip = soup.find("tool-tip", attrs={"for": td.get("id")}) if td.get("id") else None
        text = tip.get_text(strip=True) if tip else ""
        m = re.match(r"(\d+)", text)
        days.append({"date": date, "count": int(m.group(1)) if m else 0})
    if not days:
        raise RuntimeError("no calendar cells found")
    return days


def from_api():
    r = requests.get(f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last", timeout=30)
    r.raise_for_status()
    return [{"date": d["date"], "count": d["count"]} for d in r.json()["contributions"]]


def get_days():
    for fn in (from_github, from_api):
        try:
            days = fn()
            if days:
                print("source:", fn.__name__)
                return sorted(days, key=lambda d: d["date"])
        except Exception as e:
            print(f"{fn.__name__} failed: {e}", file=sys.stderr)
    sys.exit("could not fetch contributions from any source")


def streaks(days):
    cur = idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1
    end = idx
    n = 0
    while idx >= 0 and days[idx]["count"] > 0:
        n += 1; idx -= 1
    cur_s = {"length": n, "start": days[idx + 1]["date"] if n else None, "end": days[end]["date"] if n else None}
    best = run = 0; bs = be = None; rs = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0: rs = i
            run += 1
            if run > best: best, bs, be = run, days[rs]["date"], d["date"]
        else:
            run = 0
    return cur_s, {"length": best, "start": bs, "end": be}


def main():
    days = get_days()
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"] > 0)
    top = max(days, key=lambda d: d["count"])
    cur, lng = streaks(days)
    monthly = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]
    data = {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active,
        "avg_per_active_day": round(total / active, 1) if active else 0,
        "current_streak": cur,
        "longest_streak": lng,
        "best_day": {"date": top["date"], "count": top["count"]},
        "monthly": [{"month": k, "total": v} for k, v in sorted(monthly.items())],
        "days": days,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), indent=2)
    print(f"wrote {total} contributions, streak {cur['length']}")


main()
