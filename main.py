#!/usr/bin/env python3
import os
import json
import time
import re
import html
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone
import requests
import feedparser

STATE_PATH = Path("state.json")
FEEDS_PATH = Path("feeds.json")

def load_state() -> Dict[str, List[str]]:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: Dict[str, List[str]]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_entry_id(entry) -> str:
    entry_id = getattr(entry, "id", "") or getattr(entry, "guid", "") or ""
    if not entry_id:
        entry_id = f"{getattr(entry, 'link', '')}::{getattr(entry, 'title', '')}"
    return entry_id

def coerce_dt(entry) -> datetime:
    """Return a timezone-aware UTC datetime for the entry (fallback to now)."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

def clean_text(s: str, limit: int = 800) -> str:
    if not s:
        return ""
    # strip HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # decode entities, collapse whitespace
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s

def post_header_for_date(webhook_url: str, d: datetime, feed_name: str):
    date_str = d.astimezone(timezone.utc).strftime("%Y-%m-%d")
    content = f"**🗓️ {date_str} — {feed_name.title()} patch notes**"
    resp = requests.post(webhook_url, json={"content": content}, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord header post failed: {resp.status_code} {resp.text}")

def post_to_discord(webhook_url: str, title: str, url: str, description: str,
                    color: int, ts: datetime, feed_name: str,
                    thumbnail_url: str | None = None) -> None:
    embed = {
        "title": title[:256] if title else "Update",
        "url": url if url else None,
        "description": description[:3500] if description else None,
        "color": color,
        "timestamp": ts.astimezone(timezone.utc).isoformat(),
        "footer": {"text": feed_name.upper()}
    }
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    payload = {"embeds": [embed]}
    resp = requests.post(webhook_url, json=payload, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")

def should_keep(entry_title: str, pattern: str | None) -> bool:
    if not pattern:
        return True
    try:
        return re.search(pattern, entry_title or "", flags=re.I) is not None
    except re.error:
        return True

def main():
    if not FEEDS_PATH.exists():
        raise SystemExit("feeds.json not found. Create it with your feeds configuration.")
    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        feeds: List[Dict[str, Any]] = json.load(f)

    state = load_state()

    for feed in feeds:
        name = feed["name"]
        feed_url = feed["feed_url"]
        webhook_secret_name = feed["webhook_secret"]
        webhook_url = os.environ.get(webhook_secret_name)
        color = int(feed.get("color", 0x5865F2))  # default blurple
        title_filter = feed.get("title_filter_regex")
        max_new = int(feed.get("max_new_per_run", 10))

        if not webhook_url:
            print(f"[WARN] Missing env for {webhook_secret_name}; skipping {name}.")
            continue

        print(f"[INFO] Fetching {name} -> {feed_url}")
        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            print(f"[WARN] Problem parsing {feed_url}: {parsed.bozo_exception}")
            continue

        seen = set(state.get(name, []))
        candidates: List[Tuple[str, Any, datetime]] = []

        for entry in parsed.entries:
            title = getattr(entry, "title", "") or "Update"
            if not should_keep(title, title_filter):
                continue
            eid = get_entry_id(entry)
            if eid and eid not in seen:
                dt = coerce_dt(entry)
                candidates.append((eid, entry, dt))

        # sort by date ascending, then cap to max_new
        candidates.sort(key=lambda t: t[2])
        if max_new and len(candidates) > max_new:
            candidates = candidates[-max_new:]

        # group by date (UTC day)
        posted_dates: set[str] = set()
        for eid, entry, dt in candidates:
            day_key = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
            if day_key not in posted_dates:
                try:
                    post_header_for_date(webhook_url, dt, name)
                except Exception as e:
                    print(f"[WARN] Header post failed for {day_key}: {e}")
                posted_dates.add(day_key)

            title = getattr(entry, "title", "Update")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = clean_text(summary, limit=900)

            try:
                post_to_discord(webhook_url, title, link, summary, color, dt, name)
                print(f"[OK] Posted: {title} @ {dt.isoformat()}")
