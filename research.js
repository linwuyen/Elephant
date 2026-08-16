const Research = (() => {
  const q = (s) => document.querySelector(s);
  const state = { reports: [], filtered: [], status: null, db: null, ready: false };

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

  function unique(values) { return [...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-Hant')); }

  function fillSelect(el, values, label) {
    if (!el) return;
    el.innerHTML = `<option value="">${label}</option>` + values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
  }

  function renderStats() {
    const reports = state.reports;
    const counts = Object.fromEntries(['McKinsey','BCG','Deloitte','PwC'].map(c => [c, reports.filter(r => r.company === c).length]));
    const latest = reports.reduce((m,r) => r.date > m ? r.date : m, '');
    const cards = [
      ['研究筆數', reports.length.toLocaleString()],
      ['最新研究', latest || '—'],
      ['McKinsey', counts.McKinsey || 0],
      ['BCG', counts.BCG || 0],
      ['Deloitte', counts.Deloitte || 0],
      ['PwC', counts.PwC || 0],
    ];
    q('#researchStats').innerHTML = cards.map(([k,v]) => `<div class="research-stat"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
    const st = state.status;
    if (!st) {
      q('#researchMeta').textContent = '來源 Consultant_System';
      return;
    }
    const health = String(st.upstream_health || st.status || 'unknown').toUpperCase();
    const companyHealth = Object.entries(st.company_health || {})
      .map(([company, row]) => `${company}:${String(row?.ingestion_status || 'unknown').toUpperCase()}`)
      .join(' · ');
    q('#researchMeta').textContent = `來源 Consultant_System · 上游 ${health} · ${companyHealth || '無公司健康資訊'} · Snapshot ${st.upstream_snapshot_id || '—'} · 上游更新 ${st.source_updated_at || '—'} · Elephant 同步 ${st.synced_at || '—'}`;
  }

  function applyFilters() {
    const keyword = (q('#researchKeyword')?.value || '').trim().toLowerCase();
    const company = q('#researchCompany')?.value || '';
    const topic = q('#researchTopic')?.value || '';
    const year = q('#researchYear')?.value || '';
    const sort = q('#researchSort')?.value || 'date-desc';

    let rows = state.reports.filter(r => {
      const text = `${r.title || ''} ${r.description || ''} ${(r.topics || []).join(' ')}`.toLowerCase();
      return (!keyword || text.includes(keyword))
        && (!company || r.company === company)
        && (!topic || (r.topics || []).includes(topic))
        && (!year || String(r.date || '').startsWith(year));
    });

    rows.sort((a,b) => {
      if (sort === 'date-asc') return String(a.date).localeCompare(String(b.date));
      if (sort === 'company') return String(a.company).localeCompare(String(b.company)) || String(b.date).localeCompare(String(a.date));
      return String(b.date).localeCompare(String(a.date));
    });
    state.filtered = rows;
    renderRows();
  }

  function renderRows() {
    const rows = state.filtered;
    q('#researchCount').textContent = `${rows.length.toLocaleString()} 筆`;
    q('#researchRows').innerHTML = rows.slice(0, 300).map(r => `
      <article class="research-item">
        <div class="research-item-meta"><span class="research-company">${esc(r.company)}</span><span>${esc(r.date || '—')}</span><span>${esc(r.source_name || '')}</span></div>
        <h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></h3>
        <p>${esc(r.description || '')}</p>
        <div class="research-tags">${(r.topics || []).map(t => `<span>${esc(t)}</span>`).join('')}</div>
      </article>`).join('') || '<div class="notice">沒有符合條件的研究。</div>';
  }

  async function loadSqlite() {
    const out = q('#sqlOutput');
    if (!window.initSqlJs) {
      out.textContent = 'sql.js 尚未載入；研究清單仍可正常使用。';
      return;
    }
    out.textContent = '載入 consultant.db…';
    const SQL = await window.initSqlJs({ locateFile: file => `https://cdn.jsdelivr.net/npm/sql.js@1.13.0/dist/${file}` });
    const bytes = new Uint8Array(await fetch(`data/consultant/consultant.db?v=${Date.now()}`, {cache:'no-store'}).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.arrayBuffer();
    }));
    state.db = new SQL.Database(bytes);
    out.textContent = 'SQLite ready. 可直接執行唯讀 SELECT / WITH / PRAGMA 查詢。';
  }

  function runSql() {
    const out = q('#sqlOutput');
    if (!state.db) { out.textContent = 'SQLite 尚未載入。'; return; }
    const sql = (q('#sqlInput').value || '').trim();
    if (!/^(select|with|pragma)\b/i.test(sql)) { out.textContent = '安全限制：只允許 SELECT / WITH / PRAGMA。'; return; }
    try {
      const result = state.db.exec(sql);
      if (!result.length) { out.textContent = '查詢完成，沒有資料列。'; return; }
      out.innerHTML = result.map(block => {
        const head = `<tr>${block.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr>`;
        const body = block.values.map(row => `<tr>${row.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('');
        return `<div class="table-wrap sql-table"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
      }).join('');
    } catch (error) {
      out.textContent = `SQL error: ${error.message || error}`;
    }
  }

  async function init() {
    if (state.ready) return;
    const [payload, status] = await Promise.all([
      fetch(`data/consultant/reports.json?v=${Date.now()}`, {cache:'no-store'}).then(r => r.ok ? r.json() : Promise.reject(new Error(`reports HTTP ${r.status}`))),
      fetch(`data/consultant/status.json?v=${Date.now()}`, {cache:'no-store'}).then(r => r.ok ? r.json() : null).catch(() => null),
    ]);
    state.reports = payload.reports || [];
    state.status = status;
    state.filtered = [...state.reports];

    fillSelect(q('#researchCompany'), unique(state.reports.map(r => r.company)), '全部公司');
    fillSelect(q('#researchTopic'), unique(state.reports.flatMap(r => r.topics || [])), '全部主題');
    fillSelect(q('#researchYear'), unique(state.reports.map(r => String(r.date || '').slice(0,4))).reverse(), '全部年份');
    ['#researchKeyword','#researchCompany','#researchTopic','#researchYear','#researchSort'].forEach(sel => {
      const el = q(sel); if (!el) return; el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', applyFilters);
    });
    q('#sqlRun')?.addEventListener('click', runSql);
    q('#sqlExample')?.addEventListener('click', () => {
      q('#sqlInput').value = "SELECT company, COUNT(*) AS reports, MAX(published_at) AS latest FROM reports GROUP BY company ORDER BY reports DESC;";
      runSql();
    });

    renderStats();
    applyFilters();
    state.ready = true;
    loadSqlite().catch(err => { q('#sqlOutput').textContent = `SQLite 載入失敗：${err.message || err}`; });
  }

  return { init };
})();

document.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-tab="research"]');
  if (button) Research.init().catch(err => {
    const box = document.querySelector('#researchRows');
    if (box) box.innerHTML = `<div class="notice">顧問研究資料載入失敗：${String(err)}</div>`;
  });
});
