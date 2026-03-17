#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从最新 Excel 报表生成 web/public/data.json，供 Next.js 前端读取。
"""

import os
import glob
import json
import pandas as pd
from datetime import datetime, timedelta

REPORTS_DIR = 'reports'
OUTPUT_PATH = 'web/public/data.json'
GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/Fdughost/xyz_finance-podcast-scraper/main/reports'


def get_all_excel():
    return sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')))


def load_subs_map(filepath):
    if not filepath or not os.path.exists(filepath):
        return {}
    df = pd.read_excel(filepath)
    return dict(zip(df['节目名称'], df['订阅数']))


def find_report_near_date(target_date, max_days=7):
    for offset in range(max_days + 1):
        d = target_date - timedelta(days=offset)
        path = os.path.join(REPORTS_DIR, f'播客监控日报_{d.strftime("%Y-%m-%d")}.xlsx')
        if os.path.exists(path):
            return path
    return None


def generate_data_json():
    all_files = get_all_excel()
    if not all_files:
        print("没有找到报表文件，跳过生成 data.json")
        return

    latest = all_files[-1]
    date_str = os.path.basename(latest).replace('播客监控日报_', '').replace('.xlsx', '')
    latest_date = datetime.strptime(date_str, '%Y-%m-%d')

    df = pd.read_excel(latest)

    # 历史增量
    subs_7d = load_subs_map(find_report_near_date(latest_date - timedelta(days=7)))
    subs_30d = load_subs_map(find_report_near_date(latest_date - timedelta(days=30)))

    podcasts = []
    for i, row in df.iterrows():
        name = row.get('节目名称', '')
        subs = int(row['订阅数'])
        d7 = int(subs - subs_7d[name]) if name in subs_7d else None
        d30 = int(subs - subs_30d[name]) if name in subs_30d else None
        podcasts.append({
            'rank': i + 1,
            'name': name,
            'company': str(row.get('基金公司', '') or ''),
            'subs': subs,
            'delta_7d': d7,
            'delta_30d': d30,
            'latest_episode': str(row.get('最新单集名称', '') or ''),
            'latest_date': str(row.get('最新单集上线日期', '') or ''),
            'plays': int(row.get('最新单集播放数量', 0) or 0),
            'interactions': int(row.get('互动指标(点赞+收藏)', 0) or 0),
            'duration': str(row.get('最新单集时长', '') or ''),
        })

    # 趋势数据（最近 60 天，前 10 名）
    trend_files = all_files[-60:]
    trend_dates = []
    trend_data = {}
    top_names = df['节目名称'].head(10).tolist()

    for fpath in trend_files:
        d = os.path.basename(fpath).replace('播客监控日报_', '').replace('.xlsx', '')
        trend_dates.append(d)
        tmp = load_subs_map(fpath)
        for n in top_names:
            if n not in trend_data:
                trend_data[n] = []
            trend_data[n].append(tmp.get(n, None))

    all_reports = [os.path.basename(f) for f in sorted(all_files, reverse=True)]

    result = {
        'date': date_str,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M CST'),
        'podcasts': podcasts,
        'trend': {
            'dates': trend_dates,
            'series': [{'name': n, 'data': trend_data[n]} for n in top_names],
        },
        'reports': all_reports,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'✓ 已生成 {OUTPUT_PATH}（{len(podcasts)} 个播客，{len(trend_dates)} 天趋势）')


if __name__ == '__main__':
    generate_data_json()
