import logging
import os
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus

from jinja2 import Environment, FileSystemLoader, select_autoescape
from .utils import ensure_dir, read_json, write_json

log = logging.getLogger("publisher")

def load_episodes(episodes_dir: str) -> List[Dict[str, Any]]:
    """Load episode meta + summary/transcript for rendering."""
    items = []
    if not os.path.exists(episodes_dir):
        return items
    for ep_id in sorted(os.listdir(episodes_dir)):
        ep_path = os.path.join(episodes_dir, ep_id)
        if not os.path.isdir(ep_path):
            continue
        meta = read_json(os.path.join(ep_path, "meta.json"), {})
        summary = read_json(os.path.join(ep_path, "summary.json"), {})
        transcript = read_json(os.path.join(ep_path, "transcript.json"), {}).get("text", "")
        items.append({
        "id": ep_id,
        "title": meta.get("title", ep_id),
        "published": meta.get("published", ""),
        "published_ts": meta.get("published_ts", 0),  # add this
        "link": meta.get("link", ""),
        "image_url": meta.get("image_url", None),
        "summary": summary,
        "transcript": transcript,
        })
    return items

def publish_site(site_dir: str, episodes: List[Dict], site_title: str, site_description: str, base_url: str = ""):
    """Render HTML pages into docs/. Uses relative links to avoid 404s on GitHub Pages."""
    ensure_dir(site_dir)
    ensure_dir(os.path.join(site_dir, "episodes"))

    # Ensure GitHub Pages does not try to run Jekyll
    with open(os.path.join(site_dir, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape()
    )

    # Filter: turn a Bible passage string into a BibleGateway link (NIV)
    def bible_link(ref: str) -> str:
        return f"https://www.biblegateway.com/passage/?search={quote_plus(ref)}&version=NIV"
    env.filters["bible_link"] = bible_link

    ctx_common = {
        "site_title": site_title,
        "site_description": site_description,
        "build_time": datetime.utcnow().isoformat() + "Z",
    }

    # Index
    tmpl_idx = env.get_template("index.html")
    html = tmpl_idx.render(title="Home", episodes=episodes, **ctx_common)
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # Episode pages
    tmpl_ep = env.get_template("episode.html")
    for ep in episodes:
        html = tmpl_ep.render(title=ep["title"], episode=ep, **ctx_common)
        with open(os.path.join(site_dir, "episodes", f"{ep['id']}.html"), "w", encoding="utf-8") as f:
            f.write(html)

    # JSON feed for programmatic access
    write_json(os.path.join(site_dir, "feed.json"), episodes)
    log.info("Published %d episodes to %s", len(episodes), site_dir)