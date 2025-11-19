import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger("downloader")


def _is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def _find_new_file(before: set, dirpath: str) -> Optional[str]:
    # Return the newest file in dirpath that wasn't in `before` set
    try:
        after = {os.path.join(dirpath, p) for p in os.listdir(dirpath)}
    except FileNotFoundError:
        after = set()
    added = after - before
    if not added:
        return None
    # Choose the file with the newest mtime
    best = max(added, key=lambda p: os.path.getmtime(p))
    return best


def download_audio(url: str, dest_dir: str, max_mb: int = 300) -> Optional[str]:
    """Download audio to dest_dir. Supports plain audio URLs and YouTube links via yt-dlp.

    Returns the local file path or None on failure/oversize.
    """
    os.makedirs(dest_dir, exist_ok=True)
    local = os.path.join(dest_dir, "audio")
    os.makedirs(local, exist_ok=True)

    # Handle YouTube URLs via yt-dlp (preferred) which can extract audio
    if _is_youtube_url(url):
        try:
            import yt_dlp as ytdlp
        except Exception:
            log.exception("yt-dlp is required to download from YouTube but is not available.")
            return None

        log.info("Downloading audio from YouTube: %s", url)
        # Snapshot files before download to detect the output file
        before_files = {os.path.join(local, f) for f in os.listdir(local)}

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(local, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "noplaylist": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
        try:
            with ytdlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception:
            log.exception("yt-dlp download failed for %s", url)
            return None

        # Try to find the new file created
        time.sleep(0.1)
        downloaded = _find_new_file(before_files, local)
        if not downloaded and info:
            # Fallback: construct expected mp3 filename from id
            expected = os.path.join(local, f"{info.get('id')}.mp3")
            if os.path.exists(expected):
                downloaded = expected

        if not downloaded:
            log.warning("Could not locate downloaded file for %s", url)
            return None

        size_mb = os.path.getsize(downloaded) / (1024 * 1024)
        if size_mb > max_mb:
            log.warning("Downloaded file exceeds max size (%.1f MB > %d MB). Removing.", size_mb, max_mb)
            try:
                os.remove(downloaded)
            except OSError:
                pass
            return None

        log.info("Downloaded YouTube audio to %s (%.1f MB)", downloaded, size_mb)
        return downloaded

    # Fallback: HTTP(s) stream download (existing behaviour)
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