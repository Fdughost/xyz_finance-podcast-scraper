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
SUPABASE_URL = 'https://iidpfslucpeiheoodxyw.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlpZHBmc2x1Y3BlaWhlb29keHl3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1ODA1ODEsImV4cCI6MjA4OTE1NjU4MX0.UHu7rnXvGj8rOC1itVknxTIKh5pw3KVNt9br7YnIYOQ'


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

    # JS auth 逻辑（单独定义避免 f-string 转义问题）
    js_code = """
const { createClient } = supabase;
const sb = createClient('__SUPABASE_URL__', '__SUPABASE_ANON_KEY__');

sb.auth.onAuthStateChange((_event, session) => {
  updateUI(session);
});

sb.auth.getSession().then(({ data: { session } }) => {
  updateUI(session);
});

function updateUI(session) {
  const loggedIn = !!session;
  document.getElementById('user-info').style.display = loggedIn ? 'flex' : 'none';
  document.getElementById('login-btn-header').style.display = loggedIn ? 'none' : 'inline-block';
  if (loggedIn) {
    document.getElementById('user-email-display').textContent = session.user.email;
  }
  document.querySelectorAll('.download-section').forEach(el => {
    el.style.display = loggedIn ? 'block' : 'none';
  });
  document.querySelectorAll('.locked-section').forEach(el => {
    el.style.display = loggedIn ? 'none' : 'flex';
  });
}

function openModal(tab) {
  document.getElementById('auth-modal').style.display = 'flex';
  switchTab(tab || 'login');
}

function closeModal() {
  document.getElementById('auth-modal').style.display = 'none';
  document.getElementById('auth-msg').textContent = '';
}

function switchTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('tab-login').classList.toggle('active', isLogin);
  document.getElementById('tab-register').classList.toggle('active', !isLogin);
  document.getElementById('form-login').style.display = isLogin ? 'block' : 'none';
  document.getElementById('form-register').style.display = isLogin ? 'none' : 'block';
  document.getElementById('auth-msg').textContent = '';
  document.getElementById('auth-msg').style.color = '#e74c3c';
}

async function handleLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  if (!email || !password) return;
  document.getElementById('auth-msg').style.color = '#666';
  document.getElementById('auth-msg').textContent = '登录中...';
  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) {
    document.getElementById('auth-msg').style.color = '#e74c3c';
    document.getElementById('auth-msg').textContent = '登录失败：' + (error.message.includes('Invalid') ? '邮箱或密码错误' : error.message);
  } else {
    closeModal();
  }
}

async function handleRegister() {
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  if (!email || !password) return;
  if (password.length < 6) {
    document.getElementById('auth-msg').style.color = '#e74c3c';
    document.getElementById('auth-msg').textContent = '密码至少 6 位';
    return;
  }
  document.getElementById('auth-msg').style.color = '#666';
  document.getElementById('auth-msg').textContent = '注册中...';
  const { error } = await sb.auth.signUp({ email, password });
  if (error) {
    document.getElementById('auth-msg').style.color = '#e74c3c';
    document.getElementById('auth-msg').textContent = '注册失败：' + error.message;
  } else {
    document.getElementById('auth-msg').style.color = '#27ae60';
    document.getElementById('auth-msg').textContent = '注册成功！请查收验证邮件后再登录。';
  }
}

async function handleLogout() {
  await sb.auth.signOut();
}

document.getElementById('auth-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
""".replace('__SUPABASE_URL__', SUPABASE_URL).replace('__SUPABASE_ANON_KEY__', SUPABASE_ANON_KEY)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>公募基金播客监控日报</title>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f6f9; color: #333; }}
  header {{ background: #1a3a5c; color: #fff; padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
  .header-left h1 {{ font-size: 22px; font-weight: 600; }}
  .header-left p {{ font-size: 13px; opacity: 0.75; margin-top: 4px; }}
  .header-right {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; }}
  #user-info {{ display: none; align-items: center; gap: 10px; }}
  #user-email-display {{ font-size: 13px; opacity: 0.85; }}
  .btn-header {{ background: rgba(255,255,255,0.15); color: #fff; border: 1px solid rgba(255,255,255,0.4); padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }}
  .btn-header:hover {{ background: rgba(255,255,255,0.25); }}
  .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; color: #1a3a5c; margin-bottom: 14px; border-left: 3px solid #1a3a5c; padding-left: 8px; }}
  .download-btn {{ display: inline-block; background: #1a7a4a; color: #fff; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-size: 14px; }}
  .download-btn:hover {{ background: #155e3a; }}
  .locked-section {{ display: none; align-items: center; gap: 12px; color: #888; font-size: 14px; }}
  .btn-login-inline {{ background: #1a3a5c; color: #fff; border: none; padding: 6px 14px; border-radius: 5px; cursor: pointer; font-size: 13px; }}
  .btn-login-inline:hover {{ background: #0f2540; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1a3a5c; color: #fff; padding: 10px 12px; text-align: left; white-space: nowrap; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #eee; vertical-align: middle; }}
  tr:hover td {{ background: #eef3fb !important; }}
  .archive-list {{ list-style: none; display: flex; flex-wrap: wrap; gap: 10px; }}
  .archive-list a {{ color: #1a3a5c; text-decoration: none; font-size: 13px; padding: 5px 10px; border: 1px solid #c8d6e5; border-radius: 4px; }}
  .archive-list a:hover {{ background: #eef3fb; }}
  footer {{ text-align: center; font-size: 12px; color: #999; padding: 20px; }}
  /* Modal */
  .modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }}
  .modal-box {{ background: #fff; border-radius: 12px; padding: 32px; width: 100%; max-width: 400px; position: relative; margin: 16px; }}
  .modal-title {{ font-size: 18px; font-weight: 600; color: #1a3a5c; margin-bottom: 20px; }}
  .modal-close {{ position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 20px; cursor: pointer; color: #999; line-height: 1; }}
  .tabs {{ display: flex; border-bottom: 2px solid #eee; margin-bottom: 20px; }}
  .tab {{ padding: 8px 20px; cursor: pointer; font-size: 14px; color: #999; border-bottom: 2px solid transparent; margin-bottom: -2px; }}
  .tab.active {{ color: #1a3a5c; border-bottom-color: #1a3a5c; font-weight: 600; }}
  .form-group {{ margin-bottom: 14px; }}
  .form-group label {{ display: block; font-size: 13px; color: #555; margin-bottom: 5px; }}
  .form-group input {{ width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; outline: none; }}
  .form-group input:focus {{ border-color: #1a3a5c; }}
  .btn-submit {{ width: 100%; background: #1a3a5c; color: #fff; border: none; padding: 11px; border-radius: 6px; font-size: 15px; cursor: pointer; margin-top: 4px; }}
  .btn-submit:hover {{ background: #0f2540; }}
  #auth-msg {{ font-size: 13px; margin-top: 12px; min-height: 18px; color: #e74c3c; text-align: center; }}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <h1>公募基金播客监控日报</h1>
    <p>数据日期：{date_str} &nbsp;|&nbsp; 页面生成：{generated_at} &nbsp;|&nbsp; 共 {len(df)} 个播客</p>
  </div>
  <div class="header-right">
    <div id="user-info">
      <span id="user-email-display"></span>
      <button class="btn-header" onclick="handleLogout()">退出登录</button>
    </div>
    <button id="login-btn-header" class="btn-header" onclick="openModal('login')">登录 / 注册</button>
  </div>
</header>

<div class="container">
  <div class="card">
    <h2>最新报表（{date_str}）</h2>
    <div class="download-section" style="display:none">
      <a class="download-btn" href="{GITHUB_RAW_BASE}/{quote('播客监控日报_' + date_str + '.xlsx')}">⬇ 下载 Excel 报表</a>
    </div>
    <div class="locked-section">
      <span>🔒 登录后可下载 Excel 报表</span>
      <button class="btn-login-inline" onclick="openModal('login')">立即登录</button>
    </div>
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
    <div class="download-section" style="display:none">
      <ul class="archive-list">{archive_html}</ul>
    </div>
    <div class="locked-section">
      <span>🔒 登录后可查看历史报表</span>
      <button class="btn-login-inline" onclick="openModal('login')">立即登录</button>
    </div>
  </div>
</div>

<footer>数据来源：小宇宙 FM &nbsp;|&nbsp; 自动更新，每日北京时间 10:00</footer>

<!-- 登录/注册弹窗 -->
<div id="auth-modal" class="modal-overlay">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">账号登录</div>
    <div class="tabs">
      <div id="tab-login" class="tab active" onclick="switchTab('login')">登录</div>
      <div id="tab-register" class="tab" onclick="switchTab('register')">注册</div>
    </div>
    <div id="form-login">
      <div class="form-group">
        <label>邮箱</label>
        <input id="login-email" type="email" placeholder="your@email.com" />
      </div>
      <div class="form-group">
        <label>密码</label>
        <input id="login-password" type="password" placeholder="输入密码" onkeydown="if(event.key==='Enter')handleLogin()" />
      </div>
      <button class="btn-submit" onclick="handleLogin()">登录</button>
    </div>
    <div id="form-register" style="display:none">
      <div class="form-group">
        <label>邮箱</label>
        <input id="reg-email" type="email" placeholder="your@email.com" />
      </div>
      <div class="form-group">
        <label>密码（至少 6 位）</label>
        <input id="reg-password" type="password" placeholder="设置密码" onkeydown="if(event.key==='Enter')handleRegister()" />
      </div>
      <button class="btn-submit" onclick="handleRegister()">注册</button>
    </div>
    <div id="auth-msg"></div>
  </div>
</div>

<script>
{js_code}
</script>
</body>
</html>'''

    output_path = os.path.join(DOCS_DIR, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML 已生成：{output_path}")


if __name__ == '__main__':
    generate_html()
