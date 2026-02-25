import os
import math
import re
import sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Tuple
from flask import Flask, request, jsonify, send_from_directory
import requests

# Configuration
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.environ.get("OPENAI_API_KEY")
PORT = int(os.environ.get("PORT", "8000"))
SITE_DIR = os.path.join(os.path.dirname(__file__), "site")
DIARY_DIR = os.path.join(os.path.dirname(__file__), "diary_by_date")
PEOPLE_DB_PATH = os.environ.get(
    "PEPYS_DB_PATH",
    os.path.join(os.path.dirname(__file__), "people.sqlite"),
)

if not API_KEY:
    raise SystemExit("OPENAI_API_KEY is required in the environment")

app = Flask(__name__, static_folder=SITE_DIR, static_url_path="")


def word_count(text: str) -> int:
    return len([w for w in text.split() if w])


NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return NORMALIZE_RE.sub(" ", text.lower()).strip()


@lru_cache(maxsize=2)
def load_people_terms(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Missing people database at {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.normalized_name AS term
            FROM people p
            UNION ALL
            SELECT p.id, p.name, a.normalized_alias AS term
            FROM person_aliases a
            JOIN people p ON p.id = a.person_id
            """
        ).fetchall()
    finally:
        conn.close()

    terms_by_person = {}
    for person_id, person_name, term in rows:
        if not term:
            continue
        entry = terms_by_person.setdefault(
            person_id,
            {"name": person_name, "terms": set()},
        )
        entry["terms"].add(term)

    terms = []
    for person_id, entry in terms_by_person.items():
        for term in entry["terms"]:
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")
            terms.append((person_id, entry["name"], pattern))
    return terms


def entities_for_text(text: str, limit: int = 10):
    normalized = normalize(text)
    if not normalized:
        return []

    terms = load_people_terms(PEOPLE_DB_PATH)
    counts = defaultdict(int)
    names = {}
    for person_id, person_name, pattern in terms:
        match_count = len(pattern.findall(normalized))
        if match_count:
            counts[person_id] += match_count
            names[person_id] = person_name

    entities = [
        {"name": names[person_id], "count": count}
        for person_id, count in counts.items()
    ]
    entities.sort(key=lambda x: (-x["count"], x["name"]))
    return entities[:limit]


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


@app.route("/entities")
def entities():
    date = (request.args.get("date") or "").strip()
    if not date:
        return jsonify({"error": "Missing date"}), 400

    limit_raw = (request.args.get("limit") or "").strip()
    try:
        limit = int(limit_raw) if limit_raw else 10
    except ValueError:
        limit = 10
    limit = max(1, min(limit, 50))

    path = Path(DIARY_DIR) / f"{date}.txt"
    if not path.exists():
        return jsonify({"error": f"Unknown date: {date}"}), 404

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == date:
        lines = lines[1:]
    body = "\n".join(lines)

    try:
        people = entities_for_text(body, limit=limit)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"entities": people})


# Static file fallback
@app.route("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(SITE_DIR, path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
