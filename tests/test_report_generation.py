"""Exercise report → static page/JSON without network crawling or production writes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import generate_html
import generate_data_json
from excel_generator import PodcastExcelGenerator


class ReportGeneration(unittest.TestCase):
    def test_new_report_reaches_both_download_inventories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports, docs = root / 'reports', root / 'docs'
            generator = PodcastExcelGenerator(str(reports))
            data = [{'title': '验收播客', 'subscribers': 100, 'latest_episode_play': 12,
                     'latest_episode_interaction': 3, 'latest_episode_duration': '10分钟',
                     'latest_episode_date': '2024-02-29', 'latest_episode_title': '验收单集'}]
            name = '播客监控日报_2024-02-29.xlsx'
            result = generator.generate_daily_report(data, name)
            self.assertEqual(pd.read_excel(result).iloc[0]['节目名称'], '验收播客')
            with patch.object(generate_html, 'REPORTS_DIR', str(reports)), patch.object(generate_html, 'DOCS_DIR', str(docs)):
                generate_html.generate_html()
            html = (docs / 'index.html').read_text()
            self.assertIn(name, html)
            self.assertIn('customElements.define', html)
            self.assertNotIn('supabase', html.lower())
            output = root / 'data.json'
            with patch.object(generate_data_json, 'REPORTS_DIR', str(reports)), patch.object(generate_data_json, 'OUTPUT_PATH', str(output)):
                generate_data_json.generate_data_json()
            self.assertEqual(json.loads(output.read_text())['reports'], [name])
