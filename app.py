import os
import math
import re
import sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
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


TERM_BOUNDARY_PREFIX = r"(?<![A-Za-z0-9])"
TERM_BOUNDARY_SUFFIX = r"(?![A-Za-z0-9])"


def build_term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(
        rf"{TERM_BOUNDARY_PREFIX}{escaped}{TERM_BOUNDARY_SUFFIX}",
        re.IGNORECASE,
    )


@lru_cache(maxsize=2)
def load_people_terms(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Missing people database at {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.note, p.name AS term
            FROM people p
            UNION ALL
            SELECT p.id, p.name, p.note, a.alias AS term
            FROM person_aliases a
            JOIN people p ON p.id = a.person_id
            """
        ).fetchall()
    finally:
        conn.close()

    terms = []
    seen = set()
    for person_id, person_name, person_note, term in rows:
        if not term:
            continue
        cleaned = term.strip()
        if not cleaned:
            continue
        key = (person_id, cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        terms.append(
            {
                "person_id": int(person_id),
                "name": person_name,
                "note": person_note,
                "term": cleaned,
                "pattern": build_term_pattern(cleaned),
            }
        )
    return terms


def entities_for_text(text: str, limit: int = 10):
    if not text.strip():
        return {"entities": [], "matches": []}

    terms = load_people_terms(PEOPLE_DB_PATH)
    raw_matches = []
    for term in terms:
        for match in term["pattern"].finditer(text):
            raw_matches.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "person_id": term["person_id"],
                    "name": term["name"],
                    "note": term["note"],
                }
            )

    if not raw_matches:
        return {"entities": [], "matches": []}

    raw_matches.sort(key=lambda m: (m["start"], -(m["end"] - m["start"])))
    matches = []
    cursor = -1
    for match in raw_matches:
        if match["start"] < cursor:
            continue
        matches.append(match)
        cursor = match["end"]

    counts = defaultdict(int)
    people = {}
    for match in matches:
        person_id = match["person_id"]
        counts[person_id] += 1
        people.setdefault(
            person_id,
            {"id": person_id, "name": match["name"], "note": match["note"]},
        )

    name_entities = {}
    for person_id, count in counts.items():
        person = people.get(person_id)
        if not person:
            continue
        name = (person.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        existing = name_entities.get(key)
        if not existing:
            name_entities[key] = {
                "id": person_id,
                "name": name,
                "note": person.get("note"),
                "count": count,
                "_note_score": count,
            }
            continue
        existing["count"] += count
        if person.get("note") and (
            not existing.get("note") or count > existing.get("_note_score", 0)
        ):
            existing["note"] = person.get("note")
            existing["_note_score"] = count

    entities = list(name_entities.values())
    for entity in entities:
        entity.pop("_note_score", None)
    entities.sort(key=lambda x: (-x["count"], x["name"]))
    if limit:
        entities = entities[:limit]

    return {"entities": entities, "matches": matches}


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
    while lines and not lines[0].strip():
        lines = lines[1:]
    body = "\n".join(lines)

    try:
        data = entities_for_text(body, limit=limit)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(data)


# Static file fallback
@app.route("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(SITE_DIR, path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
