"""Renames retain history; identical titles must not merge different IDs."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

import pandas as pd
from podcast_identity import PodcastIdentity
from data_manager import PodcastDataManager
from excel_generator import PodcastExcelGenerator
import generate_html
import generate_data_json


class IdentityTests(unittest.TestCase):
    def test_rename_legacy_history_and_both_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'history.db'
            PodcastDataManager(str(db))
            with sqlite3.connect(db) as conn:
                for date, title, subs in [('2026-10-01', '旧名', 100), ('2026-10-08', '新名', 130)]:
                    conn.execute('INSERT INTO podcast_snapshots (podcast_id,podcast_name,crawl_date,crawl_time,raw_data) VALUES (?,?,?,?,?)',
                                 ('stable-id', '旧名', date, date, json.dumps({'title': title})))
            identity = PodcastIdentity(db, root / 'missing.json')
            pd.DataFrame([{'节目名称': '旧名', '订阅数': 100}]).to_excel(root / '播客监控日报_2026-10-01.xlsx', index=False)
            latest = PodcastExcelGenerator(tmp).generate_daily_report([
                {'podcast_id': 'stable-id', 'title': '新名', 'subscribers': 130,
                 'latest_episode_play': 0, 'latest_episode_interaction': 0}
            ], '播客监控日报_2026-10-08.xlsx')
            self.assertEqual(pd.read_excel(latest).iloc[0]['节目ID'], 'stable-id')
            with patch.object(generate_html, 'REPORTS_DIR', tmp), patch.object(generate_html, 'DOCS_DIR', str(root / 'docs')), patch.object(generate_html, 'PodcastIdentity', return_value=identity):
                trend = generate_html.build_trend_data(identity.read_report(latest), datetime(2026, 10, 8))
                generate_html.generate_html()
            self.assertEqual(trend['series'][0]['data'], [100, None, None, None, None, None, None, 130])
            self.assertEqual(trend['series'][0]['name'], '新名')
            output = root / 'data.json'
            with patch.object(generate_data_json, 'REPORTS_DIR', tmp), patch.object(generate_data_json, 'OUTPUT_PATH', str(output)), patch.object(generate_data_json, 'PodcastIdentity', return_value=identity):
                generate_data_json.generate_data_json()
            data = json.loads(output.read_text())
            self.assertEqual(data['podcasts'][0]['delta_7d'], 30)
            self.assertEqual(data['trend']['series'][0]['data'], [100, 130])
            self.assertIn('+30', (root / 'docs/index.html').read_text())

    def test_explicit_ids_override_names_and_ambiguity_is_rejected(self):
        identity = PodcastIdentity('/nonexistent/db', '/nonexistent/config')
        identity._add('同名', 'id-a', '2026-10-01')
        identity._add('同名', 'id-b', '2026-10-02')
        self.assertEqual(identity.key({'节目名称': '同名', '节目ID': 'id-c'}), 'id-c')
        self.assertEqual(identity.key({'节目名称': '同名'}, '2026-10-01'), 'id-a')
        with self.assertRaises(ValueError):
            identity.key({'节目名称': '同名'})

    def test_database_keeps_rename_under_same_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = PodcastDataManager(str(Path(tmp) / 'db.sqlite'))
            for title in ['旧名', '新名']:
                self.assertEqual(manager.save_batch_data([{'podcast_id': 'stable-id', 'title': title, 'subscribers': 100}]), 1)
            self.assertEqual(manager.get_latest_snapshot('stable-id')['podcast_name'], '新名')
            with sqlite3.connect(manager.db_path) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM podcast_snapshots').fetchone()[0], 1)
