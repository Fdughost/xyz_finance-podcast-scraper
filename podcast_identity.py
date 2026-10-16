"""Stable program identity for reports, including legacy name-only exports.

Only exact, unambiguous names backed by stored IDs are resolved. Platform titles
and configured names are aliases, never primary identifiers. No fuzzy matching.
"""
import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import pandas as pd


class PodcastIdentity:
    def __init__(self, db_path='data/podcast_monitor.db', config_path='config.json'):
        self.aliases = defaultdict(set)
        self.dated_aliases = defaultdict(set)
        if Path(config_path).exists():
            for item in json.loads(Path(config_path).read_text(encoding='utf-8')).get('podcasts', []):
                self._add(item.get('name'), item.get('podcast_id'))
        if Path(db_path).exists():
            with closing(sqlite3.connect(f'{Path(db_path).resolve().as_uri()}?mode=ro', uri=True)) as conn:
                for pid, name, date, raw in conn.execute(
                    'SELECT podcast_id, podcast_name, crawl_date, raw_data FROM podcast_snapshots'
                ):
                    self._add(name, pid, date)
                    try:
                        data = json.loads(raw or '{}')
                    except (ValueError, TypeError):
                        data = {}
                    for field in ('title', 'config_name'):
                        self._add(data.get(field), pid, date)

    def _add(self, name, pid, date=None):
        if name and pid:
            name, pid = str(name).strip(), str(pid).strip()
            self.aliases[name].add(pid)
            if date:
                self.dated_aliases[date, name].add(pid)

    def key(self, row, date=None):
        pid = row.get('节目ID', row.get('podcast_id'))
        if pd.notna(pid) and str(pid).strip():
            return str(pid).strip()
        name = str(row.get('节目名称', '')).strip()
        candidates = self.dated_aliases.get((date, name)) or self.aliases.get(name, set())
        if len(candidates) == 1:
            return next(iter(candidates))
        # Preserve unknown legacy programs without guessing an ID. Ambiguous
        # names must not silently combine two different programs.
        if len(candidates) > 1:
            raise ValueError(f'节目名称对应多个 ID，请在报表中补充节目ID: {name}')
        return f'legacy-name:{name}'

    def read_report(self, filepath):
        df = pd.read_excel(filepath)
        date = Path(filepath).stem.removeprefix('播客监控日报_')
        df['节目ID'] = [self.key(row, date) for _, row in df.iterrows()]
        return df

    def subs_map(self, filepath):
        if not filepath or not Path(filepath).exists():
            return {}
        df = self.read_report(filepath)
        if df['节目ID'].duplicated().any():
            raise ValueError(f'报表包含重复节目ID: {filepath}')
        return dict(zip(df['节目ID'], df['订阅数']))
