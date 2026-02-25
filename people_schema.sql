PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  note TEXT,
  source TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS person_aliases (
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  normalized_alias TEXT NOT NULL,
  note TEXT,
  source TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(person_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS idx_people_normalized_name
  ON people(normalized_name);

CREATE INDEX IF NOT EXISTS idx_person_aliases_person_id
  ON person_aliases(person_id);

CREATE INDEX IF NOT EXISTS idx_person_aliases_normalized_alias
  ON person_aliases(normalized_alias);
