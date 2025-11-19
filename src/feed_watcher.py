import logging
import time
import re
from typing import Dict, List, Optional
import feedparser
from .utils import slugify

log = logging.getLogger("feed_watcher")

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

def _first_img_from_html(html: Optional[str]) -> Optional[str]:
    if not html:
        return None
    m = IMG_TAG_RE.search(html)
    return m.group(1) if m else None

def _extract_image_from_entry(entry) -> Optional[str]:
    # 1) itunes:image (can be dict, list, or string)
    itunes_img = getattr(entry, "itunes_image", None)
    if isinstance(itunes_img, dict) and itunes_img.get("href"):
        return itunes_img["href"]
    if isinstance(itunes_img, list) and itunes_img:
        # Some feeds provide a list of dicts
        href = itunes_img[0].get("href") if isinstance(itunes_img[0], dict) else None
        if href:
            return href
    if isinstance(itunes_img, str) and itunes_img.strip():
        return itunes_img.strip()

    # 2) feedparser sometimes maps image differently
    image = getattr(entry, "image", None)
    if isinstance(image, dict):
        # Common keys: href, url
        if image.get("href"):
            return image["href"]
        if image.get("url"):
            return image["url"]
    if isinstance(image, str) and image.strip():
        return image.strip()

    # 3) media:thumbnail
    media_thumb = getattr(entry, "media_thumbnail", None)
    if isinstance(media_thumb, list) and media_thumb:
        url = media_thumb[0].get("url")
        if url:
            return url

    # 4) media:content (prefer explicit images)
    media_content = getattr(entry, "media_content", None)
    if isinstance(media_content, list):
        # Prefer type image/* or medium image
        for m in media_content:
            if (m.get("medium") == "image" or str(m.get("type", "")).startswith("image")) and m.get("url"):
                return m["url"]

    # 5) links that are images
    for lnk in getattr(entry, "links", []):
        if (lnk.get("rel") == "image" or str(lnk.get("type", "")).startswith("image")) and lnk.get("href"):
            return lnk["href"]

    # 6) Try to parse first <img> from summary/content HTML
    summary = getattr(entry, "summary", None)
    if isinstance(summary, str):
        url = _first_img_from_html(summary)
        if url:
            return url
    summary_detail = getattr(entry, "summary_detail", None)
    if isinstance(summary_detail, dict):
        url = _first_img_from_html(summary_detail.get("value"))
        if url:
            return url
    content = getattr(entry, "content", None)
    if isinstance(content, list) and content:
        val = content[0].get("value")
        url = _first_img_from_html(val)
        if url:
            return url

    return None

def _extract_image_from_feed(parsed) -> Optional[str]:
    feed = getattr(parsed, "feed", None)
    if not feed:
        return None
    # itunes:image at feed level
    itunes_img = getattr(feed, "itunes_image", None)
    if isinstance(itunes_img, dict) and itunes_img.get("href"):
        return itunes_img["href"]
    if isinstance(itunes_img, list) and itunes_img:
        href = itunes_img[0].get("href") if isinstance(itunes_img[0], dict) else None
        if href:
            return href
    if isinstance(itunes_img, str) and itunes_img.strip():
        return itunes_img.strip()
    # feed image
    image = getattr(feed, "image", None)
    if isinstance(image, dict):
        if image.get("href"):
            return image["href"]
        if image.get("url"):
            return image["url"]
    if isinstance(image, str) and image.strip():
        return image.strip()
    # Try HTML in feed subtitle/description
    subtitle = getattr(feed, "subtitle", None)
    if isinstance(subtitle, str):
        u = _first_img_from_html(subtitle)
        if u:
            return u
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
                if str(lnk.get("type", "")).startswith("audio") and lnk.get("href"):
                    audio_url = lnk.get("href")
                    break

        # If media:content exists (common in YouTube RSS) prefer it for video URL
        media_content = getattr(entry, "media_content", None)
        if not audio_url and isinstance(media_content, list) and media_content:
            # media_content items may include video URLs (youtube watch URLs)
            for mc in media_content:
                url = mc.get("url")
                if url:
                    audio_url = url
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

        # Prefer media:thumbnail when present (YouTube RSS provides media:thumbnail)
        image_url = None
        media_thumb = getattr(entry, "media_thumbnail", None)
        if isinstance(media_thumb, list) and media_thumb:
            image_url = media_thumb[0].get("url")
        image_url = image_url or _extract_image_from_entry(entry) or feed_image_fallback
        if not image_url:
            log.debug("No image found for entry titled '%s'. Available keys: %s",
                      getattr(entry, "title", "Untitled"), list(entry.keys()))

        # Prefer media:title if present (YouTube RSS includes media:title)
        media_title = getattr(entry, "media_title", None)
        title = getattr(entry, "title", "Untitled Episode")
        if isinstance(media_title, str) and media_title.strip():
            title = media_title

        ep = {
            "guid": str(guid),
            "id": slugify(str(guid))[:80],
            "title": title,
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