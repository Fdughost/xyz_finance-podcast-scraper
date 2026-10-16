"""Browser acceptance against running static (8765) and Next.js (8766) servers.

Run: python3 -m unittest discover -s tests -v
Requires playwright, its Chromium browser, and the project's requirements.txt.
Downloads are real public GitHub responses, never mocked.
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class DownloadAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = sync_playwright().start()
        cls.browser = cls.driver.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL", "chromium"))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.driver.stop()

    def test_both_frontends_real_downloads(self):
        for url in [os.environ.get('STATIC_URL', 'http://127.0.0.1:8765/docs/index.html'), 'http://127.0.0.1:8766']:
            with self.subTest(url=url):
                context = self.browser.new_context(accept_downloads=True, timezone_id='America/Los_Angeles')
                page = context.new_page()
                requests, errors = [], []
                page.on('request', lambda request: requests.append(request.url))
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url)
                host = page.locator('report-download')
                trigger = host.get_by_role('button', name='下载日报', exact=True)
                self.assertEqual(page.get_by_text('登录', exact=False).count(), 0)
                self.assertEqual(page.get_by_text('历史报表下载', exact=True).count(), 0)
                if page.locator('#trendExplorer').count():
                    page.locator('.trend-mini').first.wait_for(state='visible')
                    page.locator('.ranking-row').first.wait_for(state='visible')
                else:
                    page.locator('.recharts-wrapper > svg').nth(1).wait_for(state='visible')
                reports = sorted(json.loads(host.get_attribute('data-reports')))
                for filename in [reports[-1], reports[0]]:
                    trigger.click()
                    dialog = host.get_by_role('dialog')
                    self.assertTrue(dialog.is_visible())
                    self.assertIn(reports[-1][7:17], host.locator('[aria-pressed=true]').get_attribute('data-date'))
                    date = filename.removeprefix('播客监控日报_').removesuffix('.xlsx')
                    host.get_by_label('年份', exact=True).select_option(date[:4])
                    host.get_by_label('月份', exact=True).select_option(date[5:7])
                    host.locator(f'[data-date="{date}"]').click()
                    self.assertEqual(page.url.rstrip('/'), url.rstrip('/'))
                    with page.expect_download(timeout=30000) as event:
                        host.get_by_role('button', name='确认下载').click()
                    download = event.value
                    self.assertIsNone(download.failure())
                    self.assertEqual(unquote(download.suggested_filename), filename)
                    with tempfile.TemporaryDirectory() as directory:
                        target = Path(directory) / filename
                        download.save_as(target)
                        with ZipFile(target) as archive:
                            self.assertIn('xl/workbook.xml', archive.namelist())
                        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), hashlib.sha256((ROOT / 'reports' / filename).read_bytes()).hexdigest())
                for width in [375, 320]:
                    page.set_viewport_size({'width': width, 'height': 740})
                    trigger.click()
                    box = host.locator('dialog').bounding_box()
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], width)
                    page.keyboard.press('Escape')
                    self.assertTrue(trigger.evaluate('(el) => el.getRootNode().activeElement === el'))
                trigger.click()
                page.mouse.click(2, 2)
                self.assertFalse(host.locator('dialog').is_visible())
                trigger.click()
                host.get_by_role('button', name='关闭', exact=True).click()
                trigger.click()
                host.get_by_role('button', name='取消', exact=True).click()
                self.assertFalse(any('supabase' in request.lower() for request in requests))
                self.assertEqual(errors, [])
                context.close()

    def test_calendar_boundaries_empty_and_new_reports(self):
        page = self.browser.new_page(timezone_id='Pacific/Kiritimati')
        page.goto(os.environ.get('STATIC_URL', 'http://127.0.0.1:8765/docs/index.html'))
        fixtures = ['播客监控日报_2023-12-31.xlsx', '播客监控日报_2024-02-29.xlsx', '播客监控日报_2024-03-01.xlsx', '播客监控日报_2024-02-30.xlsx', '../invalid.xlsx']
        page.evaluate('''files => {
          const old = document.querySelector('report-download');
          const next = document.createElement('report-download');
          next.setAttribute('data-reports', JSON.stringify(files)); old.replaceWith(next);
        }''', fixtures)
        host = page.locator('report-download')
        host.get_by_role('button', name='下载日报', exact=True).click()
        self.assertEqual(host.locator('[aria-pressed=true]').get_attribute('data-date'), '2024-03-01')
        host.get_by_role('button', name='上个月').click()
        self.assertEqual(host.locator('.day').count(), 29)
        self.assertTrue(host.locator('[data-date="2024-02-28"]').is_disabled())
        host.locator('[data-date="2024-02-29"]').click()
        page.keyboard.press('ArrowLeft')
        self.assertTrue(host.locator('[data-date="2024-02-29"]').evaluate('(el) => el.getRootNode().activeElement === el'))
        host.get_by_label('年份', exact=True).select_option('2023')
        self.assertEqual(host.get_by_label('月份', exact=True).input_value(), '12')
        host.get_by_role('button', name='下个月').click()
        self.assertEqual(host.get_by_label('年份', exact=True).input_value(), '2024')
        self.assertEqual(host.get_by_label('月份', exact=True).input_value(), '01')
        self.assertEqual(host.locator('.day:not(:disabled)').count(), 0)
        for _ in range(25):
            page.keyboard.press('Tab')
            self.assertTrue(host.evaluate("el => el.shadowRoot.querySelector('dialog').contains(el.shadowRoot.activeElement)"))
        page.keyboard.press('Escape')
        page.evaluate('''() => {
          const old = document.querySelector('report-download');
          const next = document.createElement('report-download'); next.setAttribute('data-reports', '[]'); old.replaceWith(next);
        }''')
        host.get_by_role('button', name='下载日报', exact=True).click()
        self.assertTrue(host.get_by_text('暂无可下载的日报').is_visible())
        self.assertTrue(host.get_by_role('button', name='确认下载').is_disabled())
        page.close()


if __name__ == '__main__':
    unittest.main()
