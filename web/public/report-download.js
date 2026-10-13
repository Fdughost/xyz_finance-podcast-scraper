/* Shared by the generated static page and Next.js. No account or API required. */
(() => {
  if (customElements.get('report-download')) return;
  const base = 'https://raw.githubusercontent.com/Fdughost/xyz_finance-podcast-scraper/main/reports/';
  const key = (y, m, d) => `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  class ReportDownload extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const root = this.attachShadow({ mode: 'open' });
      this.files = new Map();
      let files = [];
      try { files = JSON.parse(this.getAttribute('data-reports') || '[]'); } catch { /* Empty state for invalid data. */ }
      if (!Array.isArray(files)) files = [];
      for (const file of files) {
        if (typeof file !== 'string') continue;
        const match = /^播客监控日报_(\d{4})-(\d{2})-(\d{2})\.xlsx$/.exec(file);
        if (!match) continue;
        const [, y, m, d] = match.map(Number);
        const date = new Date(y, m - 1, d);
        if (y >= 1000 && date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d) {
          this.files.set(key(y, m - 1, d), file);
        }
      }
      this.dates = [...this.files.keys()].sort();
      root.innerHTML = `
        <style>
          :host{display:inline-block;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#24364b}
          *{box-sizing:border-box}button,select{font:inherit}button{cursor:pointer}button:disabled{cursor:default;opacity:.4}
          button:focus-visible,select:focus-visible{outline:3px solid #60a5fa;outline-offset:2px}
          .trigger,.confirm{background:#1a3a5c;color:white;border:1px solid #58738f;border-radius:8px;padding:9px 16px;white-space:nowrap}
          dialog{margin:auto;border:0;border-radius:16px;padding:24px;width:min(400px,calc(100vw - 32px));max-height:calc(100dvh - 32px);overflow:auto;box-shadow:0 20px 70px #0004;color:#24364b;background:white}
          dialog::backdrop{background:#10243c99}h2{margin:0;font-size:20px}.heading,.toolbar,.actions{display:flex;align-items:center;justify-content:space-between;gap:8px}
          .close,.nav,.cancel{border:1px solid #dbe3eb;border-radius:6px;background:white;padding:7px 10px;color:#24364b}
          .hint{color:#64748b;font-size:13px;line-height:1.6}.toolbar{margin:18px 0 12px}select{min-width:0;border:1px solid #dbe3eb;background:white;padding:7px 3px;border-radius:6px;color:#24364b}
          .calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}.weekday{text-align:center;font-size:12px;color:#64748b;padding:6px 0}
          .day{width:100%;aspect-ratio:1;border:0;border-radius:7px;background:#eef4fb;color:#1a3a5c;padding:0}.day:disabled{background:transparent;color:#94a3b8;opacity:1}.day[aria-pressed=true]{background:#1a3a5c;color:white}.day:not(:disabled):hover{box-shadow:inset 0 0 0 2px #60a5fa}
          .selection{margin:18px 0;min-height:22px}.actions{justify-content:flex-end}.empty{grid-column:1/-1;padding:24px 0;text-align:center}
          @media(max-width:360px){dialog{padding:16px}.toolbar{gap:4px}.nav{padding:7px}}
        </style>
        <button class="trigger" type="button" aria-haspopup="dialog">下载日报</button>
        <dialog aria-labelledby="title" aria-describedby="hint">
          <div class="heading"><h2 id="title">下载日报</h2><button class="close" type="button" aria-label="关闭">×</button></div>
          <p class="hint" id="hint">仅可选择已有日报的日期</p>
          <div class="toolbar"><button class="nav previous" type="button" aria-label="上个月">‹</button><select class="year" aria-label="年份"></select><select class="month" aria-label="月份"></select><button class="nav next" type="button" aria-label="下个月">›</button></div>
          <div class="calendar" aria-label="日报日期"></div>
          <p class="selection" aria-live="polite"></p>
          <div class="actions"><button class="cancel" type="button">取消</button><button class="confirm" type="button">确认下载</button></div>
        </dialog>`;
      this.dialog = root.querySelector('dialog');
      const trigger = root.querySelector('.trigger');
      trigger.addEventListener('click', () => {
        this.selected = this.dates.at(-1) || '';
        this.view = this.selected.slice(0, 7);
        this.render();
        this.dialog.showModal();
      });
      for (const selector of ['.close', '.cancel']) root.querySelector(selector).addEventListener('click', () => this.dialog.close());
      this.dialog.addEventListener('close', () => trigger.focus());
      this.dialog.addEventListener('keydown', e => {
        if (e.key !== 'Tab') return;
        const focusable = [...this.dialog.querySelectorAll('button:not(:disabled), select:not(:disabled)')].filter(el => el.getClientRects().length);
        const index = focusable.indexOf(root.activeElement);
        if (e.shiftKey && index <= 0) { e.preventDefault(); focusable.at(-1)?.focus(); }
        else if (!e.shiftKey && (index === focusable.length - 1 || index < 0)) { e.preventDefault(); focusable[0]?.focus(); }
      });
      this.dialog.addEventListener('click', e => {
        if (e.target !== this.dialog) return;
        const r = this.dialog.getBoundingClientRect();
        if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) this.dialog.close();
      });
      root.querySelector('.previous').addEventListener('click', () => this.moveMonth(-1));
      root.querySelector('.next').addEventListener('click', () => this.moveMonth(1));
      for (const selector of ['.year', '.month']) root.querySelector(selector).addEventListener('change', () => {
        this.view = `${root.querySelector('.year').value}-${root.querySelector('.month').value}`;
        this.render();
      });
      root.querySelector('.confirm').addEventListener('click', () => {
        const file = this.files.get(this.selected);
        if (!file) return;
        // Navigate directly in the click handler; no popup, credentials, or fetch/CORS dependency.
        window.location.assign(base + encodeURIComponent(file));
        this.dialog.close();
      });
      root.querySelector('.calendar').addEventListener('keydown', e => {
        const buttons = [...root.querySelectorAll('.day:not(:disabled)')];
        const current = buttons.indexOf(root.activeElement);
        if (current < 0) return;
        let next = current;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next++;
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next--;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = buttons.length - 1;
        else return;
        e.preventDefault();
        buttons[Math.max(0, Math.min(next, buttons.length - 1))]?.focus();
      });
    }
    moveMonth(offset) {
      const [y, m] = this.view.split('-').map(Number);
      const date = new Date(y, m - 1 + offset, 1);
      this.view = key(date.getFullYear(), date.getMonth(), 1).slice(0, 7);
      this.render();
    }
    render() {
      const root = this.shadowRoot;
      const calendar = root.querySelector('.calendar');
      calendar.replaceChildren();
      const empty = !this.dates.length;
      root.querySelector('.toolbar').hidden = empty;
      // Explicit display handles the toolbar's flex styling.
      root.querySelector('.toolbar').style.display = empty ? 'none' : 'flex';
      root.querySelector('.confirm').disabled = !this.files.has(this.selected);
      root.querySelector('.selection').textContent = empty ? '' : `已选择：${this.selected.replace(/^(\d+)-(\d+)-(\d+)$/, '$1年$2月$3日')}`;
      if (empty) {
        const message = document.createElement('p'); message.className = 'empty'; message.textContent = '暂无可下载的日报'; calendar.append(message); return;
      }
      const first = this.dates[0].slice(0, 7), last = this.dates.at(-1).slice(0, 7);
      this.view = this.view < first ? first : this.view > last ? last : this.view;
      const [year, month] = this.view.split('-').map(Number);
      const yearSelect = root.querySelector('.year'), monthSelect = root.querySelector('.month');
      yearSelect.replaceChildren(); monthSelect.replaceChildren();
      for (let y = Number(first.slice(0, 4)); y <= Number(last.slice(0, 4)); y++) yearSelect.add(new Option(`${y}年`, String(y), false, y === year));
      for (let m = 1; m <= 12; m++) {
        const value = String(m).padStart(2, '0'); const option = new Option(`${m}月`, value, false, m === month);
        option.disabled = `${year}-${value}` < first || `${year}-${value}` > last; monthSelect.add(option);
      }
      root.querySelector('.previous').disabled = this.view === first;
      root.querySelector('.next').disabled = this.view === last;
      for (const text of ['一','二','三','四','五','六','日']) { const cell = document.createElement('span'); cell.className = 'weekday'; cell.textContent = text; calendar.append(cell); }
      const offset = (new Date(year, month - 1, 1).getDay() + 6) % 7;
      for (let i = 0; i < offset; i++) calendar.append(document.createElement('span'));
      const days = new Date(year, month, 0).getDate();
      for (let d = 1; d <= days; d++) {
        const date = key(year, month - 1, d); const button = document.createElement('button');
        button.type = 'button'; button.className = 'day'; button.textContent = String(d);
        button.disabled = !this.files.has(date); button.dataset.date = date;
        button.setAttribute('aria-label', `${year}年${month}月${d}日${button.disabled ? '，无日报' : ''}`);
        button.setAttribute('aria-pressed', String(date === this.selected));
        button.addEventListener('click', () => {
          this.selected = date; this.render(); root.querySelector(`[data-date="${date}"]`).focus();
        });
        calendar.append(button);
      }
    }
  }
  customElements.define('report-download', ReportDownload);
})();
