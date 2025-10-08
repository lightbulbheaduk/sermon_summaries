import logging
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
        # Fallback: some feeds store audio url in links
        if not audio_url:
            for lnk in getattr(entry, "links", []):
                if lnk.get("type", "").startswith("audio"):
                    audio_url = lnk.get("href")
                    break

        ep = {
            "guid": str(guid),
            "id": slugify(str(guid))[:80],  # short id safe for filenames
            "title": getattr(entry, "title", "Untitled Episode"),
            "link": getattr(entry, "link", ""),
            "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "audio_url": audio_url,
            "summary": getattr(entry, "summary", ""),
        }
        episodes.append(ep)
    log.info("Parsed %d episodes from feed: %s", len(episodes), url)
    return episodes

def find_new_episodes(all_feeds: List[str], processed_ids: List[str]) -> List[Dict]:
    """Return episodes not seen before across all feeds."""
    new_eps = []
    for feed in all_feeds:
        for ep in parse_feed(feed):
            if ep["audio_url"] and ep["id"] not in processed_ids:
                new_eps.append(ep)
    return new_eps