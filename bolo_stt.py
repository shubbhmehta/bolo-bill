"""
Bolo Bill - speech to text part (Gnani Prisma v3.0).

Run to test:
    python bolo_stt.py sale.wav

It sends the same recording in 2 styles so you can compare:
  - transcribe    -> numbers as digits   (e.g. "आज 500 का माल बेचा")
  - transliterate -> English letters     (e.g. "aaj paanch sau ka maal becha")

Before running:
    pip install requests
    set GNANI_API_KEY=your_key      (Windows)   /   export GNANI_API_KEY=your_key  (Mac/Linux)

Rules from the Gnani docs:
  - Audio: WAV, MP3, OGG, FLAC, AAC or M4A, up to 30 seconds, mono (one channel).
  - Very short clips (under about 1 second) are the least reliable.
  - Send ONE request at a time. Some accounts get error 429 if two run together.
"""

import json
import os
import sys
import time
import requests

STT_URL = "https://api.vachana.ai/stt/v3"
API_KEY = os.getenv("GNANI_API_KEY")

# ---------- Settings you can change while testing ----------
# Hints: words a shopkeeper says. The docs say hints can sometimes make results
# WORSE, so test with True and with False, and keep what works better.
USE_KEYTERMS = True
KEYTERMS = ["becha", "kharida", "udhaar", "maal", "rupaye",
            "बेचा", "खरीदा", "उधार", "माल", "रुपये"]

# Find-and-replace on the final text (works on Prisma v3.0 too, max 10 rules).
# Example: make different spellings of udhaar into one word for the ledger code.
# Start with False so you can see the plain result first.
USE_SUBSTITUTION = False
SUBSTITUTION_RULES = [
    {"patterns": ["udhar", "udhari", "उधार", "उधारी"], "replacement": "udhaar"},
]
# -----------------------------------------------------------


def explain_error(response):
    """Turn any Gnani error into one clear sentence. Gnani uses several shapes."""
    status = response.status_code
    try:
        body = response.json()
    except ValueError:
        return f"Error {status}: {response.text[:200]}"

    kind, message = None, None

    if isinstance(body, dict):
        err = body.get("error")
        detail = body.get("detail")
        if isinstance(err, dict):                       # normal error shape
            kind, message = err.get("type"), err.get("message")
        elif isinstance(detail, dict):                  # login / rate limit shape
            kind, message = detail.get("error_code"), detail.get("message")
        elif isinstance(detail, list) and detail:       # missing field shape (422)
            first = detail[0]
            kind = "MISSING_OR_BAD_FIELD"
            message = f"{first.get('loc')} - {first.get('msg')}"
        elif body.get("code"):                          # timeout shape (504)
            kind, message = body.get("code"), body.get("message")

    hints = {
        401: "Your API key is missing or wrong. Check GNANI_API_KEY.",
        402: "No credit, or your account is not verified yet. Check the dashboard / wait for Gnani.",
        403: "This key is not allowed to use speech-to-text.",
        429: "Too many requests. Wait a moment and send only one at a time.",
        504: "Gnani took too long. Try again.",
    }
    return f"Error {status} [{kind}] {message}. {hints.get(status, '')}".strip()


def speech_to_text(audio_path, style="transcribe"):
    """
    Send one short audio file to Gnani Prisma v3.0. Returns the transcript text.

    style:
      "transcribe"    numbers as digits (500)
      "transliterate" whole text in English letters, numbers as words
    """
    if not API_KEY:
        sys.exit("Set GNANI_API_KEY first (see top of this file).")

    data = {"model": "prisma-v3.0", "format": style}

    # language_code is required for every style except "transliterate".
    # "hi-IN" is a hint, not a lock. Use "indic-auto" to let the model guess,
    # or "hi-IN,en-IN" for Hindi + English.
    if style != "transliterate":
        data["language_code"] = "hi-IN"

    if USE_KEYTERMS:
        data["keyterms"] = json.dumps(KEYTERMS, ensure_ascii=False)

    if USE_SUBSTITUTION:
        data["enable_substitution"] = "true"
        data["substitution_map"] = json.dumps(SUBSTITUTION_RULES, ensure_ascii=False)

    # Try up to 2 times for temporary problems (timeout or "too many requests").
    for attempt in (1, 2):
        with open(audio_path, "rb") as audio:
            response = requests.post(
                STT_URL,
                headers={"X-API-Key-ID": API_KEY},
                files={"audio_file": (os.path.basename(audio_path), audio)},
                data=data,
                timeout=60,
            )

        if response.status_code in (429, 504) and attempt == 1:
            time.sleep(2)
            continue
        break

    if response.status_code != 200:
        sys.exit(explain_error(response))

    body = response.json()
    if not body.get("success"):
        sys.exit(explain_error(response))

    if body.get("truncated"):
        print("Warning: text was cut short. Use a shorter recording.")

    # An empty transcript is NOT an error: it just means no speech was heard.
    return body.get("transcript", "")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python bolo_stt.py sale.wav")
    if not os.path.exists(sys.argv[1]):
        sys.exit(f"File not found: {sys.argv[1]}")

    for style in ("transcribe", "transliterate"):
        text = speech_to_text(sys.argv[1], style)
        print(f"{style:14} ->", text if text else "(no speech heard)")
