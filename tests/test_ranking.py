"""Ranking includes all programs, stable global ranks and honest bar scales."""
import json
import math
import os
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class RankingTests(unittest.TestCase):
    def test_filter_sort_scale_and_missing_values(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=os.environ.get('PLAYWRIGHT_CHANNEL', 'chromium'))
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(os.environ.get('STATIC_URL', 'http://127.0.0.1:8765/docs/index.html'))
            raw = json.loads(page.locator('#trendData').text_content())
            root = page.locator('#rankingExplorer')
            rows = root.locator('.ranking-row')
            expected = sorted((s['data'][-1] for s in raw['series']), reverse=True)
            self.assertEqual(rows.count(), len(raw['series']))
            self.assertEqual(rows.evaluate_all('(rows) => rows.map(r => Number(r.dataset.value))'), expected)
            program = raw['series'][-1]
            before = rows.filter(has_text=program['name']).first.get_attribute('data-rank')
            root.get_by_label('排行搜索节目或机构').fill(program['name'])
            self.assertEqual(rows.first.get_attribute('data-rank'), before)
            root.get_by_role('button', name='重置排行').click()
            root.get_by_label('排行节目分类').select_option('公募基金')
            self.assertEqual(rows.count(), sum(s['category'] == '公募基金' for s in raw['series']))
            root.get_by_role('button', name='重置排行').click()
            root.get_by_role('button', name='前 10 名', exact=True).click()
            root.get_by_label('排行排列方式').select_option('asc')
            self.assertEqual(rows.evaluate_all('(rows) => rows.map(r => Number(r.dataset.value))'), sorted(expected[:10]))
            root.get_by_role('button', name='重置排行').click()
            root.get_by_label('排行条形比例').select_option('log')
            width = float(rows.nth(1).locator('.ranking-fill').evaluate('(el) => parseFloat(el.style.width)'))
            self.assertAlmostEqual(width, math.log1p(expected[1]) / math.log1p(expected[0]) * 100, places=3)
            self.assertIn('条长不代表人数倍数', root.locator('#rankingScaleNote').text_content())
            root.get_by_label('排行搜索节目或机构').fill('不存在的节目xyz')
            self.assertEqual(rows.count(), 0)
            self.assertTrue(root.get_by_text('没有匹配的节目，请调整搜索或分类。').is_visible())
            root.get_by_role('button', name='重置排行').click()
            page.set_viewport_size({'width': 320, 'height': 800})
            page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
            self.assertEqual(rows.count(), len(raw['series']))
            root.scroll_into_view_if_needed()
            page.screenshot(path='/tmp/ranking-mobile.png')
            fixture = {'dates': ['2026-10-16'], 'series': [
                {'name': name, 'data': [value], 'category': '测试', 'institution': ''}
                for name, value in [('甲', 100), ('乙', 100), ('丙', 0), ('丁', None)]
            ]}
            page.evaluate('''data => {
                document.getElementById('trendData').textContent = JSON.stringify(data);
                const old = document.getElementById('rankingExplorer');
                old.replaceWith(old.cloneNode(true));
            }''', fixture)
            page.add_script_tag(content=(Path(__file__).resolve().parents[1] / 'static_assets/ranking.js').read_text())
            self.assertEqual(rows.evaluate_all('(rows) => rows.map(r => r.dataset.rank)'), ['1', '1', '3', ''])
            self.assertEqual(rows.nth(2).locator('.ranking-fill').evaluate('(el) => el.style.width'), '0%')
            self.assertIn('暂无数据', rows.nth(3).text_content())
            self.assertIn('并列', root.locator('#rankingSummary').text_content())
            self.assertEqual(errors, [])
            browser.close()
