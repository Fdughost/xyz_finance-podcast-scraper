(() => {
  const root = document.getElementById('rankingExplorer');
  const raw = JSON.parse(document.getElementById('trendData').textContent);
  const get = id => root.querySelector('#' + id);
  const fmt = n => Number.isFinite(n) ? n.toLocaleString('zh-CN') : '—';
  const programs = raw.series.map((s, index) => ({ ...s, index, value: Number.isFinite(s.data.at(-1)) ? s.data.at(-1) : null }))
    .sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity) || a.index - b.index);
  programs.forEach((s, i) => { s.rank = s.value == null ? null : i > 0 && s.value === programs[i - 1].value ? programs[i - 1].rank : i + 1; });
  [...new Set(programs.map(s => s.category))].forEach(category => get('rankingCategory').add(new Option(category, category)));
  get('rankingTotal').textContent = `全部 ${programs.length} 个节目`;
  let limit = 0;
  function render() {
    const query = get('rankingSearch').value.trim().toLocaleLowerCase();
    const category = get('rankingCategory').value;
    const filtered = programs.filter(s => (!category || s.category === category) && `${s.name} ${s.institution}`.toLocaleLowerCase().includes(query));
    const ranked = filtered.filter(s => s.value != null);
    const maximum = ranked[0]?.value ?? 0;
    const summary = get('rankingSummary');summary.replaceChildren();
    const leaders = ranked.filter(s => s.value === maximum);
    for (const [label, value, cls] of [['筛选范围内节目', `${filtered.length} 个`, ''], ['订阅人次合计', ranked.length ? fmt(ranked.reduce((sum, s) => sum + s.value, 0)) : '—', ''], ['筛选范围内榜首', leaders.length > 1 ? `${leaders[0].name} 等 ${leaders.length} 个（并列）` : leaders[0]?.name ?? '—', 'leader']]) {
      const box = document.createElement('div'), title = document.createElement('span'), number = document.createElement('strong');title.textContent = label;number.textContent = value;number.className = cls;box.append(title, number);summary.append(box);
    }
    // Top-N always selects the largest N in the filtered set, regardless of display direction.
    const shown = filtered.slice(0, limit || filtered.length);
    if (get('rankingSort').value === 'asc') shown.sort((a, b) => (a.value ?? Infinity) - (b.value ?? Infinity) || a.index - b.index);
    const logarithmic = get('rankingScale').value === 'log';
    get('rankingStatus').textContent = `显示 ${shown.length} / ${filtered.length} 个匹配节目 · 共 ${programs.length} 个 · 数据日期 ${raw.dates.at(-1) || '—'}${limit ? ` · 当前筛选范围内订阅数前 ${limit} 个` : ''}`;
    get('rankingScaleNote').textContent = logarithmic ? '对数比例：条长按 log(订阅数 + 1) 展示，便于查看小规模节目；条长不代表人数倍数，右侧数字为真实订阅数。' : '标准比例：当前筛选范围的最高订阅数为满条，其余按真实人数等比例显示。';
    root.querySelectorAll('[data-ranking-limit]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.rankingLimit) === limit)));
    const list = get('rankingList');list.replaceChildren();
    for (const s of shown) {
      const row = document.createElement('li');row.className = 'ranking-row';row.dataset.rank = s.rank ?? '';row.dataset.value = s.value ?? '';row.dataset.name = s.name;
      const place = document.createElement('span');place.className = `ranking-place${s.rank != null && s.rank <= 3 ? ' podium' : ''}`;place.textContent = s.rank == null ? '—' : String(s.rank);place.setAttribute('aria-label', s.rank == null ? '暂无名次' : `全局第${s.rank}名`);
      const info = document.createElement('div'), name = document.createElement('div'), meta = document.createElement('div');name.className = 'ranking-name';name.textContent = s.name;meta.className = 'ranking-meta';meta.textContent = [s.category, s.institution].filter(Boolean).join(' · ');info.append(name, meta);
      const track = document.createElement('div'), fill = document.createElement('div');track.className = 'ranking-track';track.setAttribute('aria-hidden', 'true');fill.className = 'ranking-fill';const numerator = logarithmic ? Math.log1p(Math.max(0, s.value ?? 0)) : Math.max(0, s.value ?? 0);const denominator = logarithmic ? Math.log1p(maximum) : maximum;fill.style.width = `${denominator > 0 ? numerator / denominator * 100 : 0}%`;track.append(fill);
      const value = document.createElement('div'), unit = document.createElement('small');value.className = 'ranking-value';value.append(document.createTextNode(fmt(s.value)));unit.textContent = s.value == null ? '暂无数据' : '订阅人次';value.append(unit);
      row.append(place, info, track, value);list.append(row);
    }
    if (!shown.length) { const empty = document.createElement('li');empty.className = 'trend-empty';empty.textContent = '没有匹配的节目，请调整搜索或分类。';list.append(empty); }
  }
  get('rankingSearch').addEventListener('input', render);
  for (const id of ['rankingCategory','rankingSort','rankingScale']) get(id).addEventListener('change', render);
  root.querySelectorAll('[data-ranking-limit]').forEach(button => button.addEventListener('click', () => { limit = Number(button.dataset.rankingLimit);render(); }));
  get('rankingReset').onclick = () => { limit = 0;get('rankingSearch').value = '';get('rankingCategory').value = '';get('rankingSort').value = 'desc';get('rankingScale').value = 'linear';render(); };
  render();
})();
