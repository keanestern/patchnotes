#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from typing import Dict, List
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
    # Prefer GUID/id if present; fall back to link+title
    entry_id = getattr(entry, "id", "") or getattr(entry, "guid", "") or ""
    if not entry_id:
        entry_id = f"{getattr(entry, 'link', '')}::{getattr(entry, 'title', '')}"
    return entry_id

def post_to_discord(webhook_url: str, title: str, url: str, description: str = "") -> None:
    # Use an embed for nicer formatting
    payload = {
        "embeds": [{
            "title": title[:256] if title else "Update",
            "url": url if url else None,
            "description": (description or "")[:3500],
        }]
    }
    resp = requests.post(webhook_url, json=payload, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")

def main():
    if not FEEDS_PATH.exists():
        raise SystemExit("feeds.json not found. Create it with your feeds configuration.")
    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        feeds = json.load(f)

    state = load_state()

    for feed in feeds:
        name = feed["name"]
        feed_url = feed["feed_url"]
        webhook_secret_name = feed["webhook_secret"]  # e.g., DISCORD_WEBHOOK_CS2
        webhook_url = os.environ.get(webhook_secret_name)

        if not webhook_url:
            print(f"[WARN] Missing env for {webhook_secret_name}; skipping {name}.")
            continue

        print(f"[INFO] Fetching {name} -> {feed_url}")
        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            print(f"[WARN] Problem parsing {feed_url}: {parsed.bozo_exception}")
            continue

        seen = set(state.get(name, []))
        new_entries = []
        for entry in parsed.entries:
            eid = get_entry_id(entry)
            if eid and eid not in seen:
                # Try to only include patch-note-looking items if configured, but default: include all
                new_entries.append((eid, entry))

        # Sort by published date ascending so oldest posts first
        def sort_key(item):
            _eid, e = item
            # fall back to created/updated/0
            for attr in ("published_parsed", "updated_parsed", "created_parsed"):
                if getattr(e, attr, None):
                    return getattr(e, attr)
            return time.gmtime(0)
        new_entries.sort(key=sort_key)

        for eid, entry in new_entries:
            title = getattr(entry, "title", "Update")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")
            # Strip basic HTML tags if present in summary (very light)
            try:
                import re
                summary = re.sub(r"<[^>]+>", "", summary)
            except Exception:
                pass

            try:
                post_to_discord(webhook_url, title, link, summary)
                print(f"[OK] Posted: {title}")
                # Rate-limit a bit to be polite to Discord
                time.sleep(1.2)
                # Update state immediately
                state.setdefault(name, []).append(eid)
                # Keep last 100 ids per feed
                state[name] = state[name][-100:]
            except Exception as e:
                print(f"[ERR] Failed to post '{title}': {e}")

    save_state(state)

if __name__ == "__main__":
    main()
