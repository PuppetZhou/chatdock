"""Manager-only aliases and tags; never modifies an agent's history."""
import json
import os
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'codex-status/labels.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS labels (key TEXT PRIMARY KEY, alias TEXT NOT NULL, tags TEXT NOT NULL)')
        self.path.chmod(0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def all(self):
        with self.connect() as db:
            return {key: dict(alias=alias, tags=json.loads(tags)) for key, alias, tags in db.execute('SELECT key,alias,tags FROM labels')}

    def save(self, key, alias, tags):
        alias = alias.strip()
        tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
        if len(alias) > 160 or len(tags) > 20 or any(len(t) > 40 for t in tags):
            raise ValueError('名称最多 160 字；最多 20 个标签，每个最多 40 字。')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?)', (key, alias, json.dumps(tags, ensure_ascii=False)))

    def preferences(self):
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            return dict(db.execute('SELECT key,value FROM preferences'))

    def save_preferences(self, language, theme):
        from .appearance import PALETTES
        if language not in ('zh', 'en') or theme not in PALETTES:
            raise ValueError('Invalid language or theme')
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.executemany('INSERT OR REPLACE INTO preferences VALUES (?,?)', [('language', language), ('theme', theme)])
