import json
import logging
from typing import Dict

from tenacity import retry, wait_exponential, stop_after_attempt
from openai import OpenAI

log = logging.getLogger("summarizer")

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(4))
def extract_key_info(transcript: str, user_prompt: str, model: str, temperature: float = 0.2) -> Dict:
    client = OpenAI()
    messages = [
        {"role": "system", "content": "You are a careful, faithful extractor. Answer ONLY in JSON."},
        {"role": "user", "content": user_prompt.strip()},
        {"role": "user", "content": f"Transcript:\n\n{transcript}"},
    ]
    # Request JSON output. Some models support response_format for strict JSON.
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
    except Exception:
        # Fallback if response_format not supported
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        content = resp.choices[0].message.content

    # Parse JSON safely
    try:
        data = json.loads(content)
    except Exception:
        # Attempt to recover a JSON object from content
        import re
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise RuntimeError("Model did not return JSON.")
        data = json.loads(m.group(0))

    # Basic normalization and defaults
    data.setdefault("overall_theme", "")
    data.setdefault("quotes", [])
    data.setdefault("bible_passages", [])
    data.setdefault("follow_on_questions", [])
    data.setdefault("further_bible_passages", [])
    if not isinstance(data["quotes"], list):
        data["quotes"] = [str(data["quotes"])]
    if not isinstance(data["bible_passages"], list):
        data["bible_passages"] = [str(data["bible_passages"])]
    if not isinstance(data["follow_on_questions"], list):
        data["follow_on_questions"] = [str(data["follow_on_questions"])]
    if not isinstance(data["further_bible_passages"], list):
        data["further_bible_passages"] = [str(data["further_bible_passages"])]

    log.info("Extraction done: %d quotes, %d passages, %d questions, %d further_passages",
             len(data["quotes"]), len(data["bible_passages"]), len(data["follow_on_questions"]), len(data["further_bible_passages"]))
    return data