import json
import re
from pathlib import Path
from collections import defaultdict, Counter

DIARY_DIR = Path("diary_by_date")
OUTPUT_PATH = Path("site/entities.json")

# Simple stopwords to avoid leading articles/pronouns being treated as names
STOP = {
    "The","A","An","And","But","For","In","On","At","Of","To","From","With",
    "His","Her","He","She","They","We","It","My","Our","Their","This","That","These","Those",
    "Sir","Lady","Master","Mistress","Mr","Mrs","Ms","Dr","Lord","Dame","Madam",
}

# Regex for capitalized spans
SPAN_RE = re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*")


def extract_names(text: str):
    names = []
    for match in SPAN_RE.finditer(text):
        span = match.group().strip()
        parts = span.split()
        if not parts:
            continue
        if any(p in STOP or len(p) < 3 for p in parts):
            continue
        if any(ch.isdigit() for ch in span):
            continue
        names.append(span)
    return names


def main():
    if not DIARY_DIR.exists():
        raise SystemExit(f"Missing diary directory: {DIARY_DIR}")

    global_counts = Counter()
    per_date = defaultdict(Counter)

    for path in sorted(DIARY_DIR.glob("*.txt")):
        date = path.stem  # YYYY-MM-DD
        text = path.read_text(encoding="utf-8")
        # drop first line if it's the date header
        lines = text.splitlines()
        if lines and lines[0].strip() == date:
            lines = lines[1:]
        body = "\n".join(lines)
        names = extract_names(body)
        per_date[date].update(names)
        global_counts.update(names)

    entities = []
    for name, count in global_counts.most_common():
        dates = [d for d, cts in per_date.items() if name in cts]
        entities.append({"name": name, "count": count, "dates": dates})

    # Build per-date lists sorted by count then name
    date_entities = {}
    for d, cts in per_date.items():
        items = sorted(cts.items(), key=lambda x: (-x[1], x[0]))
        date_entities[d] = [{"name": n, "count": c} for n, c in items]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"entities": entities, "dateEntities": date_entities}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {len(entities)} entities")


if __name__ == "__main__":
    main()
