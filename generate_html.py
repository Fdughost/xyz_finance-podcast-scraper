#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从最新 Excel 报表生成 GitHub Pages 用的 index.html
"""

import os
import glob
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
from html import escape
from pathlib import Path

REPORTS_DIR = 'reports'
DOCS_DIR = 'docs'


def get_latest_excel():
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')))
    return files[-1] if files else None


def get_all_reports():
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')), reverse=True)
    return [os.path.basename(f) for f in files]


def find_report_near_date(target_date, max_days_offset=5):
    """找最接近 target_date 的报表，往前最多找 max_days_offset 天"""
    for offset in range(max_days_offset + 1):
        d = target_date - timedelta(days=offset)
        path = os.path.join(REPORTS_DIR, f'播客监控日报_{d.strftime("%Y-%m-%d")}.xlsx')
        if os.path.exists(path):
            return path
    return None


def load_subs_map(filepath):
    """从报表文件读取 {节目名称: 订阅数} 映射"""
    if not filepath:
        return {}
    df = pd.read_excel(filepath)
    return dict(zip(df['节目名称'], df['订阅数']))


def fmt_delta(delta):
    """格式化增量显示"""
    if delta is None:
        return '—', ''
    if delta > 0:
        return f'+{delta:,}', 'delta-up'
    elif delta < 0:
        return f'{delta:,}', 'delta-down'
    else:
        return '0', ''


def generate_html():
    os.makedirs(DOCS_DIR, exist_ok=True)

    latest = get_latest_excel()
    if not latest:
        print("没有找到报表文件")
        return

    df = pd.read_excel(latest)
    date_str = os.path.basename(latest).replace('播客监控日报_', '').replace('.xlsx', '')
    latest_date = datetime.strptime(date_str, '%Y-%m-%d')
    all_reports = get_all_reports()
    generated_at = datetime.now(tz=BEIJING_TZ).strftime('%Y-%m-%d %H:%M CST')

    # 加载历史数据用于增量计算
    subs_7d = load_subs_map(find_report_near_date(latest_date - timedelta(days=7)))
    subs_30d = load_subs_map(find_report_near_date(latest_date - timedelta(days=30)))

    # 加载最近 60 天所有报表用于趋势图（最多取 60 个）
    all_files = sorted(glob.glob(os.path.join(REPORTS_DIR, '播客监控日报_*.xlsx')))[-60:]
    trend_dates = []
    trend_data = {}  # {节目名称: [订阅数, ...]}
    top_names = df['节目名称'].head(10).tolist()  # 只展示前10名的趋势

    for fpath in all_files:
        d = os.path.basename(fpath).replace('播客监控日报_', '').replace('.xlsx', '')
        trend_dates.append(d)
        tmp = load_subs_map(fpath)
        for name in top_names:
            if name not in trend_data:
                trend_data[name] = []
            trend_data[name].append(tmp.get(name, None))

    trend_json = json.dumps({
        'dates': trend_dates,
        'series': [{'name': n, 'data': trend_data[n]} for n in top_names]
    }, ensure_ascii=False)

    # 生成表格行
    rows_html = ''
    for i, row in df.iterrows():
        bg = '#f9f9f9' if i % 2 == 0 else '#ffffff'
        name = row.get('节目名称', '')
        subs = int(row['订阅数'])

        d7 = (subs - subs_7d[name]) if name in subs_7d else None
        d30 = (subs - subs_30d[name]) if name in subs_30d else None
        d7_txt, d7_cls = fmt_delta(d7)
        d30_txt, d30_cls = fmt_delta(d30)

        rows_html += f'''<tr style="background:{bg}">
            <td>{i + 1}</td>
            <td class="cell-trunc col-name" style="font-weight:500" data-tip="{name}">{name}</td>
            <td>{row.get("分类", "")}</td>
            <td class="cell-trunc col-inst" data-tip="{row.get('机构名称', '')}">{row.get("机构名称", "")}</td>
            <td style="text-align:right">{subs:,}</td>
            <td class="delta {d7_cls}" style="text-align:right">{d7_txt}</td>
            <td class="delta {d30_cls}" style="text-align:right">{d30_txt}</td>
            <td class="cell-trunc col-ep" data-tip="{row.get('最新单集名称', '')}">{row.get("最新单集名称", "")}</td>
            <td>{row.get("最新单集上线日期", "")}</td>
            <td style="text-align:right">{row.get("最新单集播放数量", "")}</td>
            <td style="text-align:right">{row.get("互动指标(点赞+收藏)", "")}</td>
        </tr>'''

    # 生成移动端卡片
    cards_html = ''
    for i, row in df.iterrows():
        name = row.get('节目名称', '')
        subs = int(row['订阅数'])
        d7 = (subs - subs_7d[name]) if name in subs_7d else None
        d30 = (subs - subs_30d[name]) if name in subs_30d else None
        d7_txt, d7_cls = fmt_delta(d7)
        d30_txt, d30_cls = fmt_delta(d30)
        episode = row.get('最新单集名称', '')
        cards_html += f'''<div class="pod-card">
  <div class="pod-card-header">
    <span class="pod-rank">{i + 1}</span>
    <div>
      <div class="pod-name">{name}</div>
      <div class="pod-company">{row.get("分类", "")} · {row.get("机构名称", "")}</div>
    </div>
  </div>
  <div class="pod-stats">
    <div class="pod-stat"><div class="pod-stat-val">{subs:,}</div><div class="pod-stat-label">订阅数</div></div>
    <div class="pod-stat"><div class="pod-stat-val delta {d7_cls}">{d7_txt}</div><div class="pod-stat-label">7日增量</div></div>
    <div class="pod-stat"><div class="pod-stat-val delta {d30_cls}">{d30_txt}</div><div class="pod-stat-label">30日增量</div></div>
    <div class="pod-stat"><div class="pod-stat-val">{row.get("最新单集播放数量", "")}</div><div class="pod-stat-label">播放量</div></div>
  </div>
  <div class="pod-episode" title="{episode}">📻 {episode}</div>
  <div class="pod-meta">{row.get("最新单集上线日期", "")} &nbsp;·&nbsp; 互动 {row.get("互动指标(点赞+收藏)", "")}</div>
</div>'''

    # Both frontends use the same calendar component and actual report inventory.
    reports_attribute = escape(json.dumps(all_reports, ensure_ascii=False), quote=True)
    download_script = (Path(__file__).parent / 'web/public/report-download.js').read_text(encoding='utf-8')
    js_code = """
// 图表
(function() {
  const raw = __TREND_JSON__;
  if (!raw.dates || raw.dates.length === 0) return;

  const colors = [
    '#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6',
    '#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'
  ];

  // 横向条形图：最新订阅数
  const latestSubs = raw.series.map(s => {
    const vals = s.data.filter(v => v != null);
    return vals[vals.length - 1] || 0;
  });
  new Chart(document.getElementById('barChart'), {
    type: 'bar',
    data: {
      labels: raw.series.map(s => s.name),
      datasets: [{ data: latestSubs, backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ' ' + ctx.raw.toLocaleString() } }
      },
      scales: {
        x: { grid: { color: '#f5f5f5' }, ticks: { callback: v => v >= 10000 ? (v/10000).toFixed(0)+'w' : v, font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 12 } } }
      }
    }
  });

  // 趋势折线图：多选 pill 切换
  if (raw.dates.length < 2) return;

  const activeSet = new Set(raw.series.map((_, i) => i)); // 默认全选

  const datasets = raw.series.map((s, i) => ({
    label: s.name, data: s.data, spanGaps: true,
    borderColor: colors[i], backgroundColor: colors[i] + '18',
    borderWidth: 2, pointRadius: 3, pointHoverRadius: 5,
    tension: 0.4, fill: false,
  }));

  const trendChart = new Chart(document.getElementById('trendChart'), {
    type: 'line',
    data: { labels: raw.dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#fff', borderColor: '#e2e8f0', borderWidth: 1,
          titleColor: '#333', bodyColor: '#555',
          filter: item => activeSet.has(item.datasetIndex),
          callbacks: { label: ctx => ' ' + ctx.dataset.label + ': ' + (ctx.raw != null ? ctx.raw.toLocaleString() : '—') }
        }
      },
      scales: {
        y: { grid: { color: '#f5f5f5' }, ticks: { callback: v => v >= 10000 ? (v/10000).toFixed(1)+'w' : v.toLocaleString(), font: { size: 11 } } },
        x: { grid: { display: false }, ticks: { font: { size: 11 }, maxTicksLimit: 8 } }
      }
    }
  });

  // 生成 pill 按钮
  const pillList = document.getElementById('trendPills');
  raw.series.forEach((s, i) => {
    const btn = document.createElement('button');
    btn.className = 'pill active';
    btn.style.background = colors[i];
    btn.textContent = s.name;
    btn.onclick = () => {
      const isActive = activeSet.has(i);
      if (isActive && activeSet.size === 1) return; // 至少保留一条
      if (isActive) {
        activeSet.delete(i);
        btn.classList.remove('active');
        btn.style.background = '';
        btn.style.color = '';
      } else {
        activeSet.add(i);
        btn.classList.add('active');
        btn.style.background = colors[i];
        btn.style.color = '#fff';
      }
      trendChart.data.datasets.forEach((ds, j) => {
        ds.hidden = !activeSet.has(j);
      });
      trendChart.update('active');
    };
    pillList.appendChild(btn);
  });
})();
""".replace('__TREND_JSON__', trend_json)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>公募基金播客监控日报</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f6f9; color: #333; }}
  header {{ background: #1a3a5c; color: #fff; padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
  .header-left h1 {{ font-size: 22px; font-weight: 600; }}
  .header-left p {{ font-size: 13px; opacity: 0.75; margin-top: 4px; }}
  .header-right {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; }}
  .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; color: #1a3a5c; margin-bottom: 14px; border-left: 3px solid #1a3a5c; padding-left: 8px; }}
  .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }}
  th {{ background: #1a3a5c; color: #fff; padding: 10px 12px; text-align: left; white-space: nowrap; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #eee; vertical-align: middle; white-space: nowrap; }}
  .col-name {{ width: 120px; }}
  .col-inst {{ width: 96px; }}
  .col-ep {{ width: 200px; }}
  .cell-trunc {{ overflow: hidden; text-overflow: ellipsis; cursor: default; }}
  #tip {{ position:fixed; background:#1a3a5c; color:#fff; padding:7px 11px; border-radius:7px; font-size:12px; max-width:320px; line-height:1.6; pointer-events:none; white-space:normal; word-break:break-all; z-index:9999; display:none; box-shadow:0 3px 10px rgba(0,0,0,.25); }}
  tr:hover td {{ background: #eef3fb !important; }}
  .delta {{ font-weight: 500; }}
  .delta-up {{ color: #e74c3c; }}
  .delta-down {{ color: #27ae60; }}
  .chart-container {{ position: relative; height: 320px; }}
  .pill-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
  .pill {{ padding: 5px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; border: 1.5px solid #e2e8f0; color: #64748b; background: #f8fafc; transition: .15s; user-select: none; }}
  .pill.active {{ color: #fff; border-color: transparent; }}
  footer {{ text-align: center; font-size: 12px; color: #999; padding: 20px; }}
  /* 播客卡片（移动端） */
  .pod-card {{ border: 1px solid #e8edf2; border-radius: 8px; padding: 14px; margin-bottom: 10px; }}
  .pod-card-header {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }}
  .pod-rank {{ background: #1a3a5c; color: #fff; border-radius: 4px; font-size: 11px; font-weight: 600; padding: 2px 6px; flex-shrink: 0; margin-top: 2px; }}
  .pod-name {{ font-weight: 600; font-size: 15px; color: #1a3a5c; }}
  .pod-company {{ font-size: 12px; color: #999; margin-top: 2px; }}
  .pod-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 10px; }}
  .pod-stat {{ text-align: center; background: #f7f9fc; border-radius: 6px; padding: 6px 4px; }}
  .pod-stat-val {{ font-size: 14px; font-weight: 600; color: #333; }}
  .pod-stat-label {{ font-size: 11px; color: #999; margin-top: 2px; }}
  .pod-episode {{ font-size: 12px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }}
  .pod-meta {{ font-size: 11px; color: #aaa; }}
  /* 桌面显示表格，隐藏卡片；移动端反之 */
  .mobile-cards {{ display: none; }}
  @media (max-width: 640px) {{
    header {{ padding: 14px 16px; }}
    .header-left h1 {{ font-size: 17px; }}
    .container {{ margin: 10px auto; padding: 0 10px; }}
    .card {{ padding: 14px; }}
    .desktop-table {{ display: none; }}
    .mobile-cards {{ display: block; }}
    .chart-container {{ height: 220px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <h1>公募基金播客监控日报</h1>
    <p>数据日期：{date_str} &nbsp;|&nbsp; 页面生成：{generated_at} &nbsp;|&nbsp; 共 {len(df)} 个播客</p>
  </div>
  <div class="header-right">
    <report-download data-reports="{reports_attribute}"></report-download>
  </div>
</header>

<div class="container">
  <div class="card">
    <h2>播客数据总览</h2>
    <div class="desktop-table table-wrap">
    <table>
      <thead><tr>
        <th>#</th><th class="col-name">节目名称</th><th>分类</th><th class="col-inst">机构名称</th><th>订阅数</th>
        <th>7日增量</th><th>30日增量</th>
        <th>最新单集</th><th>上线日期</th><th>播放量</th><th>互动</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    <div class="mobile-cards">{cards_html}</div>
  </div>

  <div class="card">
    <h2>订阅数排行</h2>
    <div class="chart-container">
      <canvas id="barChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>订阅数趋势</h2>
    <div id="trendPills" class="pill-list"></div>
    <div class="chart-container">
      <canvas id="trendChart"></canvas>
    </div>
  </div>


</div>

<footer>数据来源：小宇宙 FM &nbsp;|&nbsp; 自动更新，每日北京时间 10:00</footer>

<script>{download_script}</script>

<div id="tip"></div>
<script>
{js_code}
</script>
<script>
(function() {{
  var tip = document.getElementById('tip');
  document.addEventListener('mouseover', function(e) {{
    var el = e.target.closest('[data-tip]');
    if (!el || el.scrollWidth <= el.clientWidth) {{ tip.style.display = 'none'; return; }}
    tip.textContent = el.dataset.tip;
    tip.style.display = 'block';
  }});
  document.addEventListener('mousemove', function(e) {{
    if (tip.style.display === 'none') return;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + tip.offsetWidth > window.innerWidth) x = e.clientX - tip.offsetWidth - 8;
    if (y + tip.offsetHeight > window.innerHeight) y = e.clientY - tip.offsetHeight - 8;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }});
  document.addEventListener('mouseout', function(e) {{
    if (e.target.closest('[data-tip]') && !e.relatedTarget?.closest('[data-tip]')) tip.style.display = 'none';
  }});
}})();
</script>
</body>
</html>'''

    output_path = os.path.join(DOCS_DIR, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML 已生成：{output_path}")


if __name__ == '__main__':
    generate_html()
