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
    if itunes_img is None and hasattr(entry, "get"):
        itunes_img = entry.get("itunes_image")
    if isinstance(itunes_img, dict):
        for k in ("href", "url", "@href", "@url"):
            if itunes_img.get(k):
                return itunes_img.get(k)
        # Some feedparser variants put the text value under keys like '#text' or 'value'
        for k in ("#text", "text", "value"):
            if itunes_img.get(k) and isinstance(itunes_img.get(k), str):
                v = itunes_img.get(k).strip()
                if v:
                    return v
    if isinstance(itunes_img, list) and itunes_img:
        first = itunes_img[0]
        if isinstance(first, dict):
            for k in ("href", "url", "@href", "@url"):
                if first.get(k):
                    return first.get(k)
        if isinstance(first, str) and first.strip():
            return first.strip()
    if isinstance(itunes_img, str) and itunes_img.strip():
        return itunes_img.strip()

    # 2) feedparser sometimes maps image differently
    # Sometimes feedparser exposes a top-level 'href' attribute containing the image URL
    href_attr = getattr(entry, "href", None)
    if href_attr is None and hasattr(entry, "get"):
        href_attr = entry.get("href")
    if href_attr and isinstance(href_attr, str):
        low = href_attr.lower()
        if low.startswith("http") and any(low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return href_attr

    image = getattr(entry, "image", None)
    if image is None and hasattr(entry, "get"):
        image = entry.get("image")
    if isinstance(image, dict):
        for k in ("href", "url", "@href", "@url"):
            if image.get(k):
                return image.get(k)
        for k in ("#text", "text", "value"):
            if image.get(k) and isinstance(image.get(k), str):
                v = image.get(k).strip()
                if v:
                    return v
    if isinstance(image, str) and image.strip():
        return image.strip()

    # 3) media:thumbnail
    media_thumb = getattr(entry, "media_thumbnail", None)
    if media_thumb is None and hasattr(entry, "get"):
        media_thumb = entry.get("media_thumbnail")
    if isinstance(media_thumb, list) and media_thumb:
        thumb = media_thumb[0]
        if isinstance(thumb, dict):
            for k in ("url", "@url"):
                if thumb.get(k):
                    return thumb.get(k)
        if isinstance(thumb, str) and thumb.strip():
            return thumb.strip()
    # If feedparser gave a bare string or other value, try stringifying it
    if media_thumb and not isinstance(media_thumb, (list, dict)):
        s = str(media_thumb).strip()
        if s:
            return s

    # 4) media:content (prefer explicit images)
    media_content = getattr(entry, "media_content", None)
    if media_content is None and hasattr(entry, "get"):
        media_content = entry.get("media_content")
    if isinstance(media_content, list):
        # Prefer type image/* or medium image
        for m in media_content:
            if isinstance(m, dict):
                mtype = str(m.get("type", ""))
                medium = m.get("medium")
                for k in ("url", "@url"):
                    if (medium == "image" or mtype.startswith("image")) and m.get(k):
                        return m.get(k)
            elif isinstance(m, str) and m.strip():
                return m.strip()
    # fallback: if media_content is a single string-like value
    if media_content and not isinstance(media_content, (list, dict)):
        s = str(media_content).strip()
        if s:
            return s

    # 5) links that are images
    for lnk in (getattr(entry, "links", None) or (entry.get("links") if hasattr(entry, "get") else []) or []):
        href = (lnk.get("href") if isinstance(lnk, dict) else None) or (lnk.get("url") if isinstance(lnk, dict) else None) or (lnk.get("@href") if isinstance(lnk, dict) else None) or (lnk.get("@url") if isinstance(lnk, dict) else None)
        if href and (lnk.get("rel") == "image" or str(lnk.get("type", "")).startswith("image")):
            return href

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

    # Final attempt: if entry has an 'itunes_image' or 'image' that is non-empty when stringified
    try:
        for cand in (getattr(entry, "itunes_image", None), getattr(entry, "image", None)):
            if cand and not isinstance(cand, (list, dict)):
                s = str(cand).strip()
                if s and s.startswith("http"):
                    return s
    except Exception:
        pass

    return None

def _extract_image_from_feed(parsed) -> Optional[str]:
    feed = getattr(parsed, "feed", None)
    if not feed:
        return None
    # itunes:image at feed level
    itunes_img = getattr(feed, "itunes_image", None)
    if isinstance(itunes_img, dict):
        for k in ("href", "url", "@href", "@url"):
            if itunes_img.get(k):
                return itunes_img.get(k)
    if isinstance(itunes_img, list) and itunes_img:
        first = itunes_img[0]
        if isinstance(first, dict):
            for k in ("href", "url", "@href", "@url"):
                if first.get(k):
                    return first.get(k)
        if isinstance(first, str) and first.strip():
            return first.strip()
    if isinstance(itunes_img, str) and itunes_img.strip():
        return itunes_img.strip()
    # feed image
    image = getattr(feed, "image", None)
    if isinstance(image, dict):
        for k in ("href", "url", "@href", "@url"):
            if image.get(k):
                return image.get(k)
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
        if not image_url:
            log.debug("No image found for entry titled '%s'. Available keys: %s",
                      getattr(entry, "title", "Untitled"), list(entry.keys()))

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