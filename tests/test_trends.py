"""All-program trends, missing observations, filtering and batch comparison."""
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from playwright.sync_api import sync_playwright
import generate_html


class TrendDataTests(unittest.TestCase):
    def test_all_programs_missing_days_and_new_program(self):
        with tempfile.TemporaryDirectory() as directory:
            first = pd.DataFrame([{'节目名称': f'节目{i}', '订阅数': 100 + i} for i in range(12)])
            latest = pd.DataFrame([{'节目名称': f'节目{i}', '订阅数': 110 + i, '分类': '公募基金'} for i in range(13)])
            first.to_excel(Path(directory) / '播客监控日报_2026-10-01.xlsx', index=False)
            latest.to_excel(Path(directory) / '播客监控日报_2026-10-03.xlsx', index=False)
            with patch.object(generate_html, 'REPORTS_DIR', directory):
                data = generate_html.build_trend_data(latest, datetime(2026, 10, 3))
            self.assertEqual(len(data['series']), 13)
            self.assertEqual(data['dates'], ['2026-10-01', '2026-10-02', '2026-10-03'])
            self.assertEqual(data['series'][0]['data'], [100, None, 110])
            self.assertEqual(data['series'][-1]['data'], [None, None, 122])


class TrendBrowserTests(unittest.TestCase):
    def test_overview_filters_comparison_and_mobile(self):
        with sync_playwright() as driver:
            browser = driver.chromium.launch(channel=os.environ.get('PLAYWRIGHT_CHANNEL', 'chromium'))
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(os.environ.get('STATIC_URL', 'http://127.0.0.1:8765/docs/index.html'))
            raw = json.loads(page.locator('#trendData').text_content())
            self.assertGreater(len(raw['series']), 10)
            self.assertEqual(page.locator('.trend-mini').count(), len(raw['series']))
            self.assertEqual(page.locator('.ranking-row').count(), len(raw['series']))
            page.get_by_label('节目分类', exact=True).select_option('公募基金')
            count = sum(s['category'] == '公募基金' for s in raw['series'])
            self.assertEqual(page.locator('.trend-mini').count(), count)
            page.get_by_role('button', name='对比筛选结果', exact=True).click()
            self.assertEqual(page.evaluate("Chart.getChart('trendCompareCanvas').data.datasets.length"), count)
            page.get_by_role('button', name='重置筛选', exact=True).click()
            page.get_by_role('button', name='一键对比增长前 5').click()
            datasets = page.evaluate("Chart.getChart('trendCompareCanvas').data.datasets")
            self.assertEqual(len(datasets), 5)
            for ds in datasets:
                original = next(s for s in raw['series'] if s['name'] == ds['label'])['data'][-30:]
                base = next(v for v in original if v is not None)
                self.assertAlmostEqual(ds['data'][-1], (original[-1] / base - 1) * 100)
                self.assertFalse(ds['spanGaps'])
            page.get_by_label('对比指标', exact=True).select_option('absolute')
            datasets = page.evaluate("Chart.getChart('trendCompareCanvas').data.datasets")
            for ds in datasets:
                original = next(s for s in raw['series'] if s['name'] == ds['label'])['data'][-30:]
                self.assertEqual(ds['data'], original)
            page.get_by_role('button', name='清空已选', exact=True).click()
            self.assertTrue(page.locator('#trendCompareEmpty').is_visible())
            page.get_by_role('button', name='全部总览', exact=True).click()
            name = raw['series'][-1]['name']
            page.get_by_label('搜索节目或机构', exact=True).fill(name)
            self.assertGreaterEqual(page.locator('.trend-mini').count(), 1)
            page.get_by_label('搜索节目或机构', exact=True).fill('没有这个节目xyz')
            self.assertEqual(page.locator('.trend-mini').count(), 0)
            self.assertTrue(page.locator('#trendBatch').is_disabled())
            page.get_by_role('button', name='重置筛选', exact=True).click()
            for length in [7, 60]:
                page.get_by_label('观察区间').select_option(str(length))
                page.get_by_role('button', name='一键对比规模前 5').click()
                self.assertEqual(page.evaluate("Chart.getChart('trendCompareCanvas').data.labels.length"), min(length, len(raw['dates'])))
            page.set_viewport_size({'width': 320, 'height': 740})
            page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
            self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            page.get_by_role('button', name='全部总览', exact=True).click()
            self.assertEqual(page.locator('.trend-mini').count(), len(raw['series']))
            self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            self.assertEqual(errors, [])
            browser.close()
