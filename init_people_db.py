import re
import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path("people.sqlite")
SCHEMA_PATH = Path("people_schema.sql")
PERSONS_PATH = Path("persons.md")

EM_DASH = "\u2014"
PAREN_RE = re.compile(r"\(([^)]+)\)")
QUOTE_RE = re.compile(
    r"[\"\u201c\u201d\u2018\u2019]([^\"\u201c\u201d\u2018\u2019]+)[\"\u201c\u201d\u2018\u2019]"
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def extract_aliases_and_clean_name(name: str):
    aliases = []

    def replace(match):
        content = match.group(1)
        quoted = QUOTE_RE.findall(content)
        if quoted:
            aliases.extend([q.strip() for q in quoted if q.strip()])
            return ""
        return match.group(0)

    cleaned = PAREN_RE.sub(replace, name)
    cleaned = cleaned.replace(" ,", ",")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip(), aliases


def parse_people_lines(text: str):
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        if not item:
            continue
        if EM_DASH in item:
            name_part, note = item.split(EM_DASH, 1)
            name_part = name_part.strip()
            note = note.strip()
        else:
            name_part, note = item, None
        yield name_part, note


def parse_servants(name_part: str):
    if not name_part.lower().startswith("servants:"):
        return None
    rest = name_part.split(":", 1)[1]
    names = [name.strip() for name in rest.split(";") if name.strip()]
    return names


def main():
    if not SCHEMA_PATH.exists():
        raise SystemExit(f"Missing schema: {SCHEMA_PATH}")
    if not PERSONS_PATH.exists():
        raise SystemExit(f"Missing people list: {PERSONS_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def find_person_id(
        normalized_name: str,
        note: Optional[str],
        allow_any_note: bool = False,
    ) -> Optional[int]:
        if allow_any_note:
            cur = conn.execute(
                "SELECT id FROM people WHERE normalized_name = ? ORDER BY id LIMIT 1",
                (normalized_name,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
        if note is None:
            cur = conn.execute(
                "SELECT id FROM people WHERE normalized_name = ? AND note IS NULL ORDER BY id LIMIT 1",
                (normalized_name,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
        cur = conn.execute(
            "SELECT id FROM people WHERE normalized_name = ? AND note = ? ORDER BY id LIMIT 1",
            (normalized_name, note),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None

    def upsert_person(
        name: str,
        note: Optional[str] = None,
        source: str = "persons.md",
        allow_any_note: bool = False,
    ) -> int:
        normalized_name = normalize(name)
        person_id = find_person_id(normalized_name, note, allow_any_note=allow_any_note)
        if person_id is not None:
            return person_id
        cur = conn.execute(
            "INSERT INTO people (name, normalized_name, note, source) VALUES (?, ?, ?, ?)",
            (name, normalized_name, note, source),
        )
        if cur.lastrowid is None:
            raise RuntimeError("Failed to insert person")
        return int(cur.lastrowid)

    def add_alias(
        person_id: int,
        alias: str,
        note: Optional[str] = None,
        source: str = "persons.md",
    ):
        normalized_alias = normalize(alias)
        if not normalized_alias:
            return
        conn.execute(
            """
            INSERT OR IGNORE INTO person_aliases
              (person_id, alias, normalized_alias, note, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (person_id, alias, normalized_alias, note, source),
        )

    text = PERSONS_PATH.read_text(encoding="utf-8")
    for name_part, note in parse_people_lines(text):
        servants = parse_servants(name_part)
        if servants:
            for servant in servants:
                upsert_person(servant, note="Servants")
            continue

        if note and note.lower().startswith("see "):
            alias_name = name_part
            target_name = note[4:].strip()
            cleaned_target, aliases = extract_aliases_and_clean_name(target_name)
            person_id = upsert_person(cleaned_target, allow_any_note=True)
            add_alias(person_id, alias_name, note="see")
            for alias in aliases:
                add_alias(person_id, alias)
            continue

        cleaned_name, aliases = extract_aliases_and_clean_name(name_part)
        person_id = upsert_person(cleaned_name, note=note)
        for alias in aliases:
            add_alias(person_id, alias)

    conn.commit()
    conn.close()
    print(f"Initialized {DB_PATH} with people + aliases from {PERSONS_PATH}")


if __name__ == "__main__":
    main()
