import logging
import os
import shutil
from typing import Any, Dict, List

import yaml

from .utils import setup_logging, read_json, write_json, read_text, ensure_dir
from .feed_watcher import find_new_episodes
from .downloader import download_audio
from .transcriber import transcribe_audio
from .summarizer import extract_key_info
from .publisher import load_episodes, publish_site

log = logging.getLogger("main")

def load_config(path: str = "config.yml") -> Dict[str, Any]:
    if not os.path.exists(path):
        log.warning("config.yml not found. Using config.example.yml. Copy it to config.yml to customize.")
        path = "config.example.yml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    setup_logging()
    log.info("Starting pipeline")

    cfg = load_config()
    data_dir = cfg["storage"]["data_dir"]
    episodes_dir = cfg["storage"]["episodes_dir"]
    state_file = cfg["storage"]["state_file"]
    site_dir = cfg["storage"]["site_dir"]
    ensure_dir(data_dir)
    ensure_dir(episodes_dir)

    state = read_json(state_file, {"processed_ids": []})
    processed_ids: List[str] = state.get("processed_ids", [])

    # Find new episodes
    feeds = cfg["feeds"]
    new_eps = find_new_episodes(feeds, processed_ids)
    log.info("New episodes to process: %d", len(new_eps))

    if not new_eps:
        # Still republish site with existing content; keeps "last updated" fresh during manual runs
        episodes = load_episodes(episodes_dir)
        publish_site(site_dir, episodes, cfg["site"]["title"], cfg["site"]["description"], cfg["site"].get("base_url", ""))
        log.info("No new episodes. Done.")
        return

    # Load prompt
    prompt_path = "prompt.txt" if os.path.exists("prompt.txt") else "prompt.example.txt"
    user_prompt = read_text(prompt_path)
    log.info("Using prompt from %s", prompt_path)

    for ep in new_eps:
        ep_id = ep["id"]
        ep_dir = os.path.join(episodes_dir, ep_id)
        ensure_dir(ep_dir)

        # Save minimal meta
        meta = {
            "id": ep_id,
            "guid": ep["guid"],
            "title": ep["title"],
            "link": ep["link"],
            "published": ep["published"],
            "feed_audio_url": ep["audio_url"],
        }
        write_json(os.path.join(ep_dir, "meta.json"), meta)

        # Download audio
        tmp_dir = os.path.join(data_dir, "tmp", ep_id)
        ensure_dir(tmp_dir)
        audio_path = download_audio(ep["audio_url"], data_dir, cfg["pipeline"]["max_download_mb"])
        if not audio_path:
            log.error("Skipping %s due to download failure/size.", ep_id)
            continue

        try:
            # Transcribe
            transcript_text = transcribe_audio(
                input_path=audio_path,
                work_dir=tmp_dir,
                model=cfg["openai"]["transcription_model"],
                segment_seconds=cfg["pipeline"]["segment_seconds"],
                language_hint=cfg["pipeline"].get("language_hint"),
            )
            write_json(os.path.join(ep_dir, "transcript.json"), {"text": transcript_text})

            # Summarize/extract
            summary = extract_key_info(
                transcript=transcript_text,
                user_prompt=user_prompt,
                model=cfg["openai"]["summarize_model"],
                temperature=float(cfg["openai"].get("temperature", 0.2)),
            )
            # Trim quotes if needed
            max_quotes = int(cfg["pipeline"].get("max_quotes", 5))
            summary["quotes"] = summary.get("quotes", [])[:max_quotes]
            write_json(os.path.join(ep_dir, "summary.json"), summary)

            # Mark processed
            processed_ids.append(ep_id)
            state["processed_ids"] = processed_ids
            write_json(state_file, state)

        finally:
            # Cleanup temp/audio
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass

    # Rebuild site
    episodes = load_episodes(episodes_dir)
    # Sort newest first by published if available
    episodes.sort(key=lambda e: e.get("published", ""), reverse=True)
    publish_site(site_dir, episodes, cfg["site"]["title"], cfg["site"]["description"], cfg["site"].get("base_url", ""))

    log.info("Pipeline complete.")

if __name__ == "__main__":
    main()