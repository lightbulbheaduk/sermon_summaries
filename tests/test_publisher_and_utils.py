import json
import os
import shutil
from pathlib import Path
import tempfile
import time

import pytest

from src.utils import write_json, slugify
from src.publisher import load_episodes


def make_episode(tmpdir, ep_id, title, published_str=None, published_ts=None):
    ep_dir = tmpdir / ep_id
    ep_dir.mkdir()
    meta = {
        "id": ep_id,
        "title": title,
        "published": published_str or "",
        # allow published_ts to be omitted to test fallback logic
    }
    if published_ts is not None:
        meta["published_ts"] = published_ts
    write_json(str(ep_dir / "meta.json"), meta)
    write_json(str(ep_dir / "summary.json"), {"overall_theme": "t"})
    write_json(str(ep_dir / "transcript.json"), {"text": "t"})
    return ep_dir


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  Multiple   Spaces ") == "multiple-spaces"
    assert slugify("Café & Co") == "caf-co"


def test_load_episodes_sorts_by_published_ts(tmp_path):
    # create three episodes with explicit published_ts values
    # newest should come first
    ep1 = make_episode(tmp_path, "a", "First", "Mon, 10 Nov 2025 15:43:10 GMT", 1762789390)
    ep2 = make_episode(tmp_path, "b", "Second", "Mon, 17 Nov 2025 10:56:08 GMT", 1763376968)
    ep3 = make_episode(tmp_path, "c", "Third", "Tue, 28 Oct 2025 16:30:11 GMT", 1761669011)

    episodes = load_episodes(str(tmp_path))
    ids = [e["id"] for e in episodes]
    assert ids == ["b", "a", "c"]  # b (1763376...) newest


def test_load_episodes_with_and_without_published_ts(tmp_path):
    # create episodes: one with explicit published_ts and two without
    # ensure the item with published_ts sorts before those that lack it
    ep_with_ts = make_episode(tmp_path, "has_ts", "WithTS", "Mon, 17 Nov 2025 10:56:08 GMT", 1763376968)
    ep_no_ts_a = make_episode(tmp_path, "no_ts_a", "NoTS A", "Mon, 10 Nov 2025 15:43:10 GMT")
    ep_no_ts_b = make_episode(tmp_path, "no_ts_b", "NoTS B", "Tue, 28 Oct 2025 16:30:11 GMT")

    episodes = load_episodes(str(tmp_path))
    ids = [e["id"] for e in episodes]
    # The episode with an explicit published_ts should come first (newest)
    assert ids[0] == "has_ts"
    # Episodes without published_ts are present as well
    assert set(ids) >= {"no_ts_a", "no_ts_b"}


if __name__ == "__main__":
    pytest.main([str(Path(__file__))])
