"""
Bolo Bill - Gnani Timbre text-to-speech.

text_to_speech("आज की कुल बिक्री 500 रुपये है।") -> WAV bytes

Needs the environment variable GNANI_API_KEY.
Only one request at a time is allowed (429 if you send two together).
"""

import os
import sys
import time

import requests

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
API_KEY = os.getenv("GNANI_API_KEY")

MODEL = "timbre-v3.0"      # v3.0 voices all speak Hindi. Voices are NOT shared with v2.5.
VOICE = "Shivani"          # others on v3.0: Avinash, Lakshmi, Kalpana, Shubham, Prakash...
LANGUAGE = "hi-IN"         # use "hi-en" if the text is mixed Hindi + English
SPEED = 1.0                # allowed 0.85 to 1.15


def explain_error(response):
    """Turn any Gnani TTS error into one easy sentence."""
    try:
        body = response.json()
    except ValueError:
        body = {}

    message = ""
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):            # 401, 402, 403, 429
            message = detail.get("message", "")
        elif isinstance(detail, list):          # 422
            message = str(detail)
        else:                                   # 400, 500: flat body
            message = str(body.get("message", ""))

    hints = {
        400: "Something in the request is wrong (voice, model or text).",
        401: "API key is missing or wrong.",
        402: "Account is not verified yet, or no credit left.",
        403: "This key is not allowed to use text-to-speech.",
        429: "Too many requests. Wait a few seconds and try again.",
        500: "Gnani had a problem (or the text is too long). Try again.",
    }
    hint = hints.get(response.status_code, "Unexpected error.")
    return f"Timbre error {response.status_code}: {hint} {message}".strip()


def text_to_speech(text, voice=VOICE, speed=SPEED, language=LANGUAGE):
    """Send text to Timbre and return the WAV audio as bytes.

    language: "hi-IN" for pure Hindi, or "auto" when the text mixes Hindi
    with English letters (for example a customer name like "Ramesh").
    """
    if not API_KEY:
        sys.exit("GNANI_API_KEY is not set.")
    if not text.strip():
        sys.exit("Nothing to say: the text is empty.")

    payload = {
        "text": text,
        "voice": voice,
        "model": MODEL,
        "language": language,
        "speed": speed,
        "audio_config": {
            "sample_rate": 24000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    headers = {"X-API-Key-ID": API_KEY, "Content-Type": "application/json"}

    for attempt in (1, 2):                      # retry once on 429 / 500
        try:
            response = requests.post(TTS_URL, json=payload, headers=headers, timeout=60)
        except requests.RequestException as e:
            sys.exit(f"Could not reach Gnani: {e}")
        if response.status_code == 200:
            return response.content
        if response.status_code in (429, 500) and attempt == 1:
            time.sleep(2)
            continue
        sys.exit(explain_error(response))


if __name__ == "__main__":
    line = sys.argv[1] if len(sys.argv) > 1 else "आज की कुल बिक्री 500 रुपये है।"
    audio = text_to_speech(line)
    with open("test_tts.wav", "wb") as f:
        f.write(audio)
    print("Saved test_tts.wav - play it to check the voice.")
