import logging
import time
from typing import Dict, List, Optional
import feedparser
from .utils import slugify

log = logging.getLogger("feed_watcher")

def _extract_image_from_entry(entry) -> Optional[str]:
    # Try common fields in order of likelihood
    # itunes:image
    itunes_img = getattr(entry, "itunes_image", None)
    if isinstance(itunes_img, dict) and itunes_img.get("href"):
        return itunes_img["href"]
    if isinstance(itunes_img, str):
        return itunes_img

    # media:thumbnail
    media_thumb = getattr(entry, "media_thumbnail", None)
    if isinstance(media_thumb, list) and media_thumb:
        url = media_thumb[0].get("url")
        if url:
            return url

    # media:content (where medium == image)
    media_content = getattr(entry, "media_content", None)
    if isinstance(media_content, list):
        for m in media_content:
            if m.get("medium") == "image" and m.get("url"):
                return m["url"]

    # image href (rare)
    image = getattr(entry, "image", None)
    if isinstance(image, dict) and image.get("href"):
        return image["href"]

    return None

def _extract_image_from_feed(parsed) -> Optional[str]:
    feed = getattr(parsed, "feed", None)
    if not feed:
        return None
    # itunes:image at feed level
    itunes_img = getattr(feed, "itunes_image", None)
    if isinstance(itunes_img, dict) and itunes_img.get("href"):
        return itunes_img["href"]
    if isinstance(itunes_img, str):
        return itunes_img
    # feed image
    image = getattr(feed, "image", None)
    if isinstance(image, dict) and image.get("href"):
        return image["href"]
    return None

def parse_feed(url: str) -> List[Dict]:
    """Parse RSS and return episode dicts with fields we need."""
    parsed = feedparser.parse(url)
    feed_image_fallback = _extract_image_from_feed(parsed)

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

        image_url = _extract_image_from_entry(entry) or feed_image_fallback

        ep = {
            "guid": str(guid),
            "id": slugify(str(guid))[:80],
            "title": getattr(entry, "title", "Untitled Episode"),
            "link": getattr(entry, "link", ""),
            "published": published,
            "published_ts": ts,
            "audio_url": audio_url,
            "image_url": image_url,
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
        eps.sort(key=lambda e: e.get("published_ts", 0), reverse=True)
        limited = eps[:max(0, int(per_feed_limit))]
        added = 0
        for ep in limited:
            if ep["audio_url"] and ep["id"] not in processed_ids:
                new_eps.append(ep)
                added += 1
        log.info("Feed considered newest %d; %d new to process", len(limited), added)
    return new_eps