#!/usr/bin/env python3
import os
import json
import time
import re
import html
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
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


def clean_text(s: str, limit: int = 900) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)           # strip HTML tags
    s = html.unescape(s)                      # decode entities
    s = re.sub(r"\s+", " ", s).strip()        # collapse whitespace
    if len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def post_header_for_date(webhook_url: str, d: datetime, feed_name: str) -> bool:
    """Post a bold date header. Return True if OK, False if failed."""
    date_str = d.astimezone(timezone.utc).strftime("%Y-%m-%d")
    content = f"**🗓️ {date_str} — {feed_name.title()} patch notes**"
    try:
        resp = requests.post(webhook_url, json={"content": content}, timeout=20)
        if resp.status_code >= 300:
            print(f"[WARN] Header post failed: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"[WARN] Header post exception: {e}")
        return False


def post_to_discord(
    webhook_url: str,
    title: str,
    url: str,
    description: str,
    color: int,
    ts: datetime,
    feed_name: str,
    thumbnail_url: Optional[str] = None,
    bot_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> bool:
    """Post a single embed. Return True if OK, False otherwise."""
    embed = {
        "title": title[:256] if title else "Update",
        "url": url or None,
        "description": (description[:3500] if description else None),
        "color": color,
        "timestamp": ts.astimezone(timezone.utc).isoformat(),
        "footer": {"text": feed_name.upper()},
    }
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    payload: Dict[str, Any] = {
        "allowed_mentions": {"parse": []},  # avoid accidental @everyone pings
        "embeds": [embed],
    }
    if bot_name:
        payload["username"] = bot_name
    if avatar_url:
        payload["avatar_url"] = avatar_url

    try:
        resp = requests.post(webhook_url, json=payload, timeout=20)
        if resp.status_code >= 300:
            print(f"[ERR] Discord webhook failed: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERR] Discord webhook exception: {e}")
        return False


def should_keep(entry_
