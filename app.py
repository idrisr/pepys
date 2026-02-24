import os
import math
from typing import Tuple
from flask import Flask, request, jsonify, send_from_directory
import requests

# Configuration
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.environ.get("OPENAI_API_KEY")
PORT = int(os.environ.get("PORT", "8000"))
SITE_DIR = os.path.join(os.path.dirname(__file__), "site")

if not API_KEY:
    raise SystemExit("OPENAI_API_KEY is required in the environment")

app = Flask(__name__, static_folder=SITE_DIR, static_url_path="")


def word_count(text: str) -> int:
    return len([w for w in text.split() if w])


def limit_for_mode(mode: str, text: str) -> int:
    mode = mode or "w100"
    if mode == "w10":
        return 10
    if mode == "w100":
        return 100
    if mode == "half":
        return max(1, math.ceil(word_count(text) / 2))
    # default safe cap
    return 100


def summarize_with_openai(text: str, mode: str) -> str:
    limit = limit_for_mode(mode, text)
    prompt = (
        f"Summarize this 17th-century diary entry in at most {limit} words. "
        f"Preserve key events, names, and places. If fewer words suffice, be concise.\n\n"
        f"Entry:\n{text}"
    )

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Upstream error {resp.status_code}: {resp.text}")
    data = resp.json()
    summary = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not summary:
        raise RuntimeError("No summary returned")
    return summary


@app.route("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json(force=True, silent=True) or {}
    text = (payload.get("text") or "").strip()
    mode = payload.get("mode") or "w100"
    if not text:
        return jsonify({"error": "Missing text"}), 400
    try:
        summary = summarize_with_openai(text, mode)
        return jsonify({"summary": summary})
    except Exception as e:  # noqa: BLE001
        app.logger.exception("Summarize failed")
        return jsonify({"error": str(e)}), 500


# Static file fallback
@app.route("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(SITE_DIR, path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
