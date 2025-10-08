import glob
import logging
import os
import shlex
import shutil
import subprocess
from typing import List, Optional

from tenacity import retry, wait_exponential, stop_after_attempt
from openai import OpenAI

log = logging.getLogger("transcriber")

def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def segment_audio(input_path: str, out_dir: str, segment_seconds: int) -> List[str]:
    """Split audio into chunks using ffmpeg. Returns list of chunk paths."""
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, "chunk_%03d.mp3")
    cmd = f'ffmpeg -hide_banner -loglevel error -y -i {shlex.quote(input_path)} -f segment -segment_time {segment_seconds} -c copy {shlex.quote(pattern)}'
    log.info("Segmenting audio (%ss): %s", segment_seconds, cmd)
    subprocess.run(cmd, shell=True, check=True)
    chunks = sorted(glob.glob(os.path.join(out_dir, "chunk_*.mp3")))
    log.info("Created %d chunks", len(chunks))
    return chunks

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(4))
def transcribe_chunk(client: OpenAI, model: str, path: str, language_hint: Optional[str]) -> str:
    with open(path, "rb") as f:
        log.info("Transcribing chunk: %s", os.path.basename(path))
        kwargs = {}
        if language_hint:
            kwargs["language"] = language_hint
        result = client.audio.transcriptions.create(
            model=model,
            file=f,
            **kwargs
        )
        return result.text

def transcribe_audio(input_path: str, work_dir: str, model: str = "whisper-1", segment_seconds: int = 600, language_hint: Optional[str] = None) -> str:
    """Transcribe potentially large audio by chunking, then concatenating text."""
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg is required for chunking. Install ffmpeg and retry.")

    chunks_dir = os.path.join(work_dir, "chunks")
    chunks = segment_audio(input_path, chunks_dir, segment_seconds)
    client = OpenAI()
    full_text_parts: List[str] = []
    for c in chunks:
        text = transcribe_chunk(client, model, c, language_hint)
        full_text_parts.append(text.strip())
    transcript = "\n\n".join(full_text_parts).strip()
    log.info("Transcript length (chars): %d", len(transcript))
    return transcript