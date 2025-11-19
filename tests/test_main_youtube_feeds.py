import os

import pytest
import sys
import os

# Ensure project root is on sys.path so `import src` works in test runs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_main_includes_youtube_feeds(tmp_path, monkeypatch):
    """Ensure `src.main` merges `youtube-feeds` into the `feeds` list passed
    to `find_new_episodes`.
    """
    # Prepare a minimal config dict usable by main()
    cfg = {
        "feeds": ["https://example.org/feed1.xml"],
        "youtube-feeds": ["https://www.youtube.com/feeds/videos.xml?channel_id=UC111111"],
        "pipeline": {"per_feed_limit": 2, "max_download_mb": 10, "segment_seconds": 600, "language_hint": "en", "max_quotes": 5},
        "storage": {
            "data_dir": str(tmp_path / "data"),
            "episodes_dir": str(tmp_path / "data" / "episodes"),
            "state_file": str(tmp_path / "data" / "state.json"),
            "site_dir": str(tmp_path / "docs"),
        },
        "site": {"title": "Test", "description": "desc", "base_url": ""},
        "openai": {"transcription_model": "m", "summarize_model": "m"},
    }

    # Monkeypatch load_config to return our config
    monkeypatch.setattr("src.main.load_config", lambda path="config.yml": cfg)

    # Capture the feeds passed to find_new_episodes
    captured = {}

    def fake_find_new_episodes(all_feeds, processed_ids, per_feed_limit=3):
        captured["feeds"] = list(all_feeds)
        return []

    monkeypatch.setattr("src.main.find_new_episodes", fake_find_new_episodes)

    # Prevent publish_site from writing files
    monkeypatch.setattr("src.main.publish_site", lambda *a, **k: None)

    # Run main (should call our fake_find_new_episodes)
    import src.main as main_mod

    main_mod.main()

    assert "feeds" in captured
    assert captured["feeds"] == [
        "https://example.org/feed1.xml",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UC111111",
    ]
