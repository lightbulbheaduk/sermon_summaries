import logging
import time
from typing import Dict, List
import feedparser
from .utils import slugify

log = logging.getLogger("feed_watcher")

def parse_feed(url: str) -> List[Dict]:
    """Parse RSS and return episode dicts with fields we need."""
    parsed = feedparser.parse(url)
    episodes = []
    for entry in parsed.entries:
        guid = (
            getattr(entry, "id", None)
            or getattr(entry, "guid", None)
            or getattr(entry, "link", None)
            or getattr(entry, "title", None)
        )
        if not guid:
            continue

        # Prefer audio enclosures
        audio_url = None
        for enc in getattr(entry, "enclosures", []):
            if "audio" in enc.get("type", "") or enc.get("href", "").endswith((".mp3", ".m4a", ".aac")):
                audio_url = enc.get("href")
                break
        if not audio_url:
            for lnk in getattr(entry, "links", []):
                if lnk.get("type", "").startswith("audio"):
                    audio_url = lnk.get("href")
                    break

        # Publish date handling (best-effort)
        published = getattr(entry, "published", "") or getattr(entry, "updated", "")
        ts = 0
        try:
            if getattr(entry, "published_parsed", None):
                ts = int(time.mktime(entry.published_parsed))
            elif getattr(entry, "updated_parsed", None):
                ts = int(time.mktime(entry.updated_parsed))
        except Exception:
            ts = 0

        ep = {
            "guid": str(guid),
            "id": slugify(str(guid))[:80],
            "title": getattr(entry, "title", "Untitled Episode"),
            "link": getattr(entry, "link", ""),
            "published": published,
            "published_ts": ts,
            "audio_url": audio_url,
            "summary": getattr(entry, "summary", ""),
        }
        episodes.append(ep)
    log.info("Parsed %d episodes from feed: %s", len(episodes), url)
    return episodes

def find_new_episodes(all_feeds: List[str], processed_ids: List[str], per_feed_limit: int = 3) -> List[Dict]:
    """
    Return new episodes not seen before, but only consider the newest 'per_feed_limit'
    items per feed.
    """
    new_eps: List[Dict] = []
    for feed in all_feeds:
        eps = parse_feed(feed)
        # Sort newest first by timestamp (fallback to original order if ts == 0)
        eps.sort(key=lambda e: e.get("published_ts", 0), reverse=True)
        limited = eps[:max(0, int(per_feed_limit))]
        added = 0
        for ep in limited:
            if ep["audio_url"] and ep["id"] not in processed_ids:
                new_eps.append(ep)
                added += 1
        log.info("Feed considered newest %d; %d new to process", len(limited), added)
    return new_eps