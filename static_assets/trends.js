(() => {
  const root = document.getElementById('trendExplorer');
  const raw = JSON.parse(document.getElementById('trendData').textContent);
  const get = id => root.querySelector('#' + id);
  const fmt = n => n == null ? '—' : n.toLocaleString('zh-CN');
  const signed = n => n == null ? '—' : `${n > 0 ? '+' : ''}${fmt(n)}`;
  const percent = n => n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
  let view = 'overview', chart = null;
  const selected = new Set();
  const categories = [...new Set(raw.series.map(s => s.category))];
  categories.forEach(c => get('trendCategory').add(new Option(c, c)));
  get('trendTotal').textContent = `全部 ${raw.series.length} 个节目`;
  function entries() {
    const length = Number(get('trendRange').value);
    const start = Math.max(0, raw.dates.length - length);
    return raw.series.map((series, index) => {
      const values = series.data.slice(start);
      const present = values.map((value, i) => ({ value, i })).filter(p => Number.isFinite(p.value));
      const first = present[0], last = present.at(-1);
      const change = present.length >= 2 ? last.value - first.value : null;
      const rate = change != null && first.value > 0 ? change / first.value * 100 : null;
      return { ...series, index, values, present, change, rate, latest: last?.value ?? null, firstDate: first ? raw.dates[start + first.i] : null, lastDate: last ? raw.dates[start + last.i] : null, dates: raw.dates.slice(start) };
    });
  }
  function filtered(items) {
    const query = get('trendSearch').value.trim().toLocaleLowerCase();
    const category = get('trendCategory').value;
    const key = get('trendSort').value;
    return items.filter(s => (!category || s.category === category) && `${s.name} ${s.institution}`.toLocaleLowerCase().includes(query))
      .sort((a, b) => (b[key] ?? -Infinity) - (a[key] ?? -Infinity) || a.index - b.index);
  }
  function sparkline(item) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 300 58'); svg.setAttribute('preserveAspectRatio', 'none'); svg.classList.add('trend-spark');
    svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', `${item.name}订阅趋势，${item.present.length}个有效数据点`);
    if (!item.present.length) return svg;
    const values = item.present.map(p => p.value), low = Math.min(...values), high = Math.max(...values);
    const coords = item.values.map((v, i) => Number.isFinite(v) ? [i / Math.max(1, item.values.length - 1) * 300, high === low ? 29 : 50 - (v - low) / (high - low) * 42] : null);
    let path = '', connected = false;
    coords.forEach(point => { if (!point) { connected = false; return; } path += `${connected ? 'L' : 'M'}${point[0]},${point[1]} `; connected = true; });
    const line = document.createElementNS(ns, 'path'); line.setAttribute('d', path); line.setAttribute('fill', 'none'); line.setAttribute('stroke', item.change < 0 ? '#be514e' : '#167e91'); line.setAttribute('stroke-width', '2'); line.setAttribute('vector-effect', 'non-scaling-stroke'); svg.append(line);
    // Keep isolated observations visible without bridging missing days.
    coords.forEach((point, i) => { if (!point || (coords[i - 1] && coords[i + 1])) return; const dot = document.createElementNS(ns, 'circle');dot.setAttribute('cx', point[0]);dot.setAttribute('cy', point[1]);dot.setAttribute('r', '2');dot.setAttribute('fill', '#167e91');svg.append(dot); });
    return svg;
  }
  function card(item) {
    const el = document.createElement('article'); el.className = `trend-mini${selected.has(item.podcast_id) ? ' selected' : ''}`;
    el.innerHTML = '<div class="trend-mini-head"><div><h3></h3><p class="category"></p></div><label><input type="checkbox">对比</label></div><div class="trend-metrics"><strong class="trend-number"></strong><span class="trend-change"></span></div><div class="spark-slot"></div><div class="trend-foot"><span></span><span></span></div>';
    el.querySelector('h3').textContent = item.name;
    el.querySelector('.category').textContent = item.category;
    el.querySelector('.trend-number').textContent = fmt(item.latest);
    const delta = el.querySelector('.trend-change'); delta.textContent = `${signed(item.change)} · ${percent(item.rate)}`; delta.classList.add(item.change < 0 ? 'down' : 'up');
    el.querySelector('.spark-slot').append(sparkline(item));
    el.querySelector('.trend-foot span').textContent = item.firstDate ? `${item.firstDate.slice(5)} — ${item.lastDate.slice(5)}` : '暂无数据';
    el.querySelector('.trend-foot span:last-child').textContent = `${item.present.length}/${item.dates.length} 天有数据`;
    const checkbox = el.querySelector('input'); checkbox.checked = selected.has(item.podcast_id); checkbox.setAttribute('aria-label', `对比${item.name}`);
    checkbox.addEventListener('change', () => { if (checkbox.checked) selected.add(item.podcast_id); else selected.delete(item.podcast_id); el.classList.toggle('selected', checkbox.checked); updateCount(); });
    return el;
  }
  function updateCount() { get('trendCompareTab').textContent = `对比已选（${selected.size}）`; }
  function renderCompare(items) {
    const chosen = items.filter(s => selected.has(s.podcast_id));
    const relative = get('trendMetric').value === 'rate';
    get('trendCompareEmpty').hidden = chosen.length > 0;
    get('trendPlot').hidden = !chosen.length;
    get('trendLegend').replaceChildren();
    if (chart) { chart.destroy(); chart = null; }
    if (!chosen.length) return;
    const colors = chosen.map((_, i) => `hsl(${(i * 137.5 + 200) % 360} 60% 40%)`);
    chosen.forEach((s, i) => { const entry = document.createElement('span'), dot = document.createElement('i');dot.style.background = colors[i];entry.append(dot, document.createTextNode(s.name));get('trendLegend').append(entry); });
    const datasets = chosen.map((s, i) => ({ label: s.name, data: s.values.map(v => relative ? (Number.isFinite(v) && s.present[0]?.value > 0 ? (v / s.present[0].value - 1) * 100 : null) : v), borderColor: colors[i], borderWidth: 2, pointRadius: s.present.length === 1 ? 3 : 0, pointHoverRadius: 4, spanGaps: false, tension: 0 }));
    if (typeof Chart === 'undefined') { get('trendCompareEmpty').hidden = false; get('trendCompareEmpty').textContent = '对比图暂未加载，请刷新页面；仍可在全部总览中查看各节目趋势。'; return; }
    chart = new Chart(get('trendCompareCanvas'), { type: 'line', data: { labels: chosen[0].dates, datasets }, options: { responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.dataset.label}：${relative ? percent(c.parsed.y) : fmt(c.parsed.y)}` } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6, callback: function(value) { return this.getLabelForValue(value).slice(5); } } }, y: { title: { display: true, text: relative ? '相对各自首个有效值的变化（%）' : '订阅人数' }, ticks: { callback: v => relative ? `${v.toFixed(1)}%` : fmt(v) } } } } });
  }
  function render() {
    const items = filtered(entries());
    get('trendStatus').textContent = `显示 ${items.length} / ${raw.series.length} 个节目 · ${raw.dates.slice(-Number(get('trendRange').value))[0] || '—'} 至 ${raw.dates.at(-1) || '—'}`;
    get('trendOverview').hidden = view !== 'overview';get('trendComparison').hidden = view !== 'compare';
    get('trendOverviewTab').setAttribute('aria-pressed', String(view === 'overview'));get('trendCompareTab').setAttribute('aria-pressed', String(view === 'compare'));updateCount();
    const grid = get('trendOverview');grid.replaceChildren(...items.map(card));
    if (!items.length) { const empty = document.createElement('p');empty.className = 'trend-empty';empty.textContent = '没有匹配的节目，请调整搜索或分类。';grid.append(empty); }
    get('trendBatch').disabled = !items.length;
    if (view === 'compare') renderCompare(items);
  }
  get('trendSearch').addEventListener('input', render);
  for (const id of ['trendCategory', 'trendRange', 'trendSort', 'trendMetric']) get(id).addEventListener('change', render);
  get('trendOverviewTab').onclick = () => { view = 'overview';render(); };
  get('trendCompareTab').onclick = () => { view = 'compare';render(); };
  get('trendClear').onclick = () => { selected.clear();render(); };
  get('trendReset').onclick = () => { get('trendSearch').value = '';get('trendCategory').value = '';render(); };
  function choose(key, count) { const items = filtered(entries()).sort((a, b) => (b[key] ?? -Infinity) - (a[key] ?? -Infinity)).filter(s => s[key] != null).slice(0, count);selected.clear();items.forEach(s => selected.add(s.podcast_id));view = 'compare';render(); }
  get('trendGrowth').onclick = () => choose('rate', 5);
  get('trendLargest').onclick = () => choose('latest', 5);
  get('trendBatch').onclick = () => { selected.clear();filtered(entries()).forEach(s => selected.add(s.podcast_id));view = 'compare';render(); };
  render();
})();
