import logging
import os
from typing import Optional
import requests

log = logging.getLogger("downloader")

def download_audio(url: str, dest_dir: str, max_mb: int = 300) -> Optional[str]:
    """Stream-download audio to dest_dir. Returns file path or None."""
    os.makedirs(dest_dir, exist_ok=True)
    local = os.path.join(dest_dir, "audio")
    os.makedirs(local, exist_ok=True)
    filename = os.path.basename(url.split("?")[0]) or "episode.mp3"
    path = os.path.join(local, filename)

    log.info("Downloading audio: %s", url)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
                    if (total / (1024 * 1024)) > max_mb:
                        log.warning("File exceeds max size (%d MB). Aborting.", max_mb)
                        f.close()
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                        return None
    log.info("Downloaded to %s (%.1f MB)", path, os.path.getsize(path) / (1024 * 1024))
    return path