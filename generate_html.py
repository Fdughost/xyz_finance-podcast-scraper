#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从最新 Excel 报表生成 GitHub Pages 用的 index.html
"""

import os
import glob
import pandas as pd
from datetime import datetime
from urllib.parse import quote

REPORTS_DIR = 'reports'
DOCS_DIR = 'docs'
GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/Fdughost/xyz_finance-podcast-scraper/main/reports'


def get_latest_excel():
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')))
    return files[-1] if files else None


def get_all_reports():
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')), reverse=True)
    return [os.path.basename(f) for f in files]


def generate_html():
    os.makedirs(DOCS_DIR, exist_ok=True)

    latest = get_latest_excel()
    if not latest:
        print("没有找到报表文件")
        return

    df = pd.read_excel(latest)
    date_str = os.path.basename(latest).replace('播客监控日报_', '').replace('.xlsx', '')
    all_reports = get_all_reports()
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M UTC')

    # 生成表格行
    rows_html = ''
    for i, row in df.iterrows():
        bg = '#f9f9f9' if i % 2 == 0 else '#ffffff'
        rows_html += f'''<tr style="background:{bg}">
            <td>{i + 1}</td>
            <td style="font-weight:500">{row.get("节目名称", "")}</td>
            <td>{row.get("基金公司", "")}</td>
            <td style="text-align:right">{int(row["订阅数"]):,}</td>
            <td style="max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{row.get("最新单集名称", "")}">{row.get("最新单集名称", "")}</td>
            <td>{row.get("最新单集上线日期", "")}</td>
            <td style="text-align:right">{row.get("最新单集播放数量", "")}</td>
            <td style="text-align:right">{row.get("互动指标(点赞+收藏)", "")}</td>
        </tr>'''

    # 生成历史报表下载列表
    archive_html = ''
    for fname in all_reports:
        d = fname.replace('播客监控日报_', '').replace('.xlsx', '')
        encoded = quote(fname)
        archive_html += f'<li><a href="{GITHUB_RAW_BASE}/{encoded}">📥 {d} 报表</a></li>\n'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>公募基金播客监控日报</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f6f9; color: #333; }}
  header {{ background: #1a3a5c; color: #fff; padding: 24px 32px; }}
  header h1 {{ font-size: 22px; font-weight: 600; }}
  header p {{ font-size: 13px; opacity: 0.75; margin-top: 4px; }}
  .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; color: #1a3a5c; margin-bottom: 14px; border-left: 3px solid #1a3a5c; padding-left: 8px; }}
  .download-btn {{ display: inline-block; background: #1a7a4a; color: #fff; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-size: 14px; }}
  .download-btn:hover {{ background: #155e3a; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1a3a5c; color: #fff; padding: 10px 12px; text-align: left; white-space: nowrap; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #eee; vertical-align: middle; }}
  tr:hover td {{ background: #eef3fb !important; }}
  .archive-list {{ list-style: none; display: flex; flex-wrap: wrap; gap: 10px; }}
  .archive-list a {{ color: #1a3a5c; text-decoration: none; font-size: 13px; padding: 5px 10px; border: 1px solid #c8d6e5; border-radius: 4px; }}
  .archive-list a:hover {{ background: #eef3fb; }}
  footer {{ text-align: center; font-size: 12px; color: #999; padding: 20px; }}
</style>
</head>
<body>
<header>
  <h1>公募基金播客监控日报</h1>
  <p>数据日期：{date_str} &nbsp;|&nbsp; 页面生成：{generated_at} &nbsp;|&nbsp; 共 {len(df)} 个播客</p>
</header>
<div class="container">
  <div class="card">
    <h2>最新报表（{date_str}）</h2>
    <a class="download-btn" href="{GITHUB_RAW_BASE}/{quote('播客监控日报_' + date_str + '.xlsx')}">⬇ 下载 Excel 报表</a>
  </div>

  <div class="card">
    <h2>播客数据总览</h2>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>#</th><th>节目名称</th><th>基金公司</th><th>订阅数</th>
        <th>最新单集</th><th>上线日期</th><th>播放量</th><th>互动（点赞+收藏）</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
  </div>

  <div class="card">
    <h2>历史报表下载</h2>
    <ul class="archive-list">{archive_html}</ul>
  </div>
</div>
<footer>数据来源：小宇宙 FM &nbsp;|&nbsp; 自动更新，每日北京时间 10:00</footer>
</body>
</html>'''

    output_path = os.path.join(DOCS_DIR, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML 已生成：{output_path}")


if __name__ == '__main__':
    generate_html()
