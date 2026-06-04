/* TrendForge front-end controller */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = (p, opts) => fetch('/api' + p, opts).then(r => r.json());

let STATUS = null;
let currentMode = 'prompt';

const toast = (msg) => {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2600);
};

const heatColor = (h) => h >= 75 ? 'var(--bad)' : h >= 50 ? 'var(--warn)' : 'var(--accent)';
const esc = (s) => (s ?? '').toString().replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const num = (n) => (n ?? 0).toLocaleString();

/* ── boot ─────────────────────────────────────────────── */
async function boot() {
  STATUS = await api('/status');
  renderPills();
  fillCategorySelects();
  fillVoices();
  loadTrends();
  wireTabs();
  wireStudio();
  wirePostModal();
  $('#f-length').addEventListener('input', e => $('#len-val').textContent = e.target.value);
}

function renderPills() {
  const p = STATUS.providers;
  $('#provider-pills').innerHTML = Object.entries(p).map(([k, v]) => {
    const mock = v === 'mock';
    return `<span class="pill ${mock ? 'mock' : 'live'}">${k}: ${v}</span>`;
  }).join('');
}

function fillCategorySelects() {
  const cats = ['all', ...STATUS.categories];
  const opts = cats.map(c => `<option value="${c}">${c[0].toUpperCase() + c.slice(1)}</option>`).join('');
  $('#trend-category').innerHTML = opts;
  $('#forecast-category').innerHTML = opts;
}

function fillVoices() {
  $('#f-voice').innerHTML = '<option value="">No voiceover</option>' +
    STATUS.voices.map(v => `<option value="${v.id}">${v.name} — ${v.style}</option>`).join('');
  $('#f-voice').value = 'creator_hype';
}

/* ── tabs ─────────────────────────────────────────────── */
function wireTabs() {
  $$('.tab').forEach(t => t.addEventListener('click', () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    $$('.panel').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('#tab-' + t.dataset.tab).classList.add('active');
    if (t.dataset.tab === 'forecast') loadForecast();
    if (t.dataset.tab === 'gallery') loadGallery();
  }));
  $('#trend-refresh').addEventListener('click', loadTrends);
  $('#trend-category').addEventListener('change', loadTrends);
  $('#forecast-refresh').addEventListener('click', loadForecast);
  $('#forecast-category').addEventListener('change', loadForecast);
  $('#forecast-weeks').addEventListener('change', loadForecast);
  $('#gallery-refresh').addEventListener('click', loadGallery);
}

/* ── trends ───────────────────────────────────────────── */
async function loadTrends() {
  const cat = $('#trend-category').value;
  $('#trend-grid').innerHTML = loader('Scanning the social web…');
  const d = await api('/trends?category=' + cat + '&limit=15');
  const s = d.summary;
  $('#trend-summary').innerHTML = `
    <div class="stat"><div class="n">${s.tracked}</div><div class="l">topics tracked</div></div>
    <div class="stat"><div class="n">${s.avg_heat}</div><div class="l">avg heat</div></div>
    <div class="stat"><div class="n">${s.exploding_now.length}</div><div class="l">exploding now</div></div>
    <div class="stat"><div class="n" style="font-size:13px;line-height:1.4">${s.exploding_now.slice(0, 3).map(esc).join('<br>') || '—'}</div><div class="l">top movers</div></div>`;
  $('#trend-grid').innerHTML = d.items.map(trendCard).join('');
  $$('#trend-grid .use-topic').forEach(b => b.addEventListener('click', () => {
    switchTab('studio'); setMode('prompt'); $('#main-input').value = b.dataset.topic; toast('Loaded into Studio');
  }));
}

function trendCard(it) {
  return `<div class="card">
    <div class="topic">${esc(it.topic)}</div>
    <div class="meta">
      <span class="badge ${it.momentum}">${it.momentum}</span>
      <span class="tagchip">${esc(it.category)}</span>
      ${it.velocity_pct != null ? `<span class="tagchip">${it.velocity_pct > 0 ? '▲' : '▼'} ${Math.abs(it.velocity_pct)}%</span>` : ''}
    </div>
    <div class="heat-bar"><i style="width:${it.heat_score || 50}%;"></i></div>
    <div class="meta" style="font-size:12px;color:var(--muted)">
      <span>🔥 ${it.heat_score ?? '—'}</span>
      <span>👥 ${num(it.creators_posting || it.contributors)}</span>
      <span>💬 ${num(it.interactions_24h)}</span>
    </div>
    ${it.platforms ? `<div class="meta">${it.platforms.map(p => `<span class="tagchip">${esc(p)}</span>`).join('')}</div>` : ''}
    <div class="card-actions">
      <button class="btn primary use-topic" data-topic="${esc(it.topic)}">🎬 Make video</button>
    </div>
  </div>`;
}

/* ── forecast ─────────────────────────────────────────── */
async function loadForecast() {
  const cat = $('#forecast-category').value;
  const weeks = $('#forecast-weeks').value;
  $('#forecast-grid').innerHTML = loader('Projecting momentum…');
  const d = await api(`/forecast?category=${cat}&weeks=${weeks}&limit=12`);
  $('#forecast-method').textContent = 'Model: ' + d.method + (d._mock ? ' · (mock data — add LUNARCRUSH_API_KEY for live signals)' : '');
  if (!d.predictions.length) { $('#forecast-grid').innerHTML = '<p class="hint">No climbing topics found for this slice — try another category.</p>'; return; }
  $('#forecast-grid').className = 'grid cards';
  $('#forecast-grid').innerHTML = d.predictions.map(forecastCard).join('');
  $$('#forecast-grid .use-topic').forEach(b => b.addEventListener('click', () => {
    switchTab('studio'); setMode('prompt'); $('#main-input').value = b.dataset.topic; toast('Loaded into Studio');
  }));
}

function forecastCard(p) {
  return `<div class="card">
    <div class="meta">
      <span class="badge ${p.trajectory}">${p.trajectory}</span>
      ${p.first_mover ? '<span class="badge first">🚀 first-mover</span>' : ''}
    </div>
    <div class="topic">${esc(p.topic)}</div>
    <div class="meta" style="font-size:12px;color:var(--muted)"><span>${esc(p.category)}</span><span>peak ≈ ${p.peak_window}</span></div>
    <div style="display:flex;align-items:center;gap:8px;margin:8px 0;font-size:13px;">
      <span>${p.current_heat}</span>
      <div class="heat-bar" style="flex:1"><i style="width:${p.projected_heat}%"></i></div>
      <span style="font-weight:800;color:var(--accent)">${p.projected_heat}</span>
    </div>
    <div class="meta" style="font-size:12px;color:var(--muted)">
      <span class="tagchip">+${p.lift} lift</span>
      <span class="tagchip">${Math.round(p.confidence * 100)}% conf</span>
      <span class="tagchip">${p.weeks_out}w out</span>
    </div>
    <p class="hint" style="margin:8px 0">${esc(p.why)}. ${esc(p.content_angle)}</p>
    <div class="card-actions"><button class="btn primary use-topic" data-topic="${esc(p.topic)}">🎬 Get ahead of it</button></div>
  </div>`;
}

/* ── studio ───────────────────────────────────────────── */
function wireStudio() {
  $$('.mode').forEach(m => m.addEventListener('click', () => setMode(m.dataset.mode)));
  setMode('prompt');
  $('#studio-form').addEventListener('submit', e => { e.preventDefault(); generate(); });
}

const MODE_CFG = {
  prompt: { label: 'Describe your video in a few words', ph: 'e.g. why everyone is obsessed with matcha', btn: '⚡ Generate Trendable Video' },
  remake: { label: 'Paste a video link to remake/remix', ph: 'https://www.tiktok.com/@user/video/123…', btn: '♻️ Remake This Video' },
  article: { label: 'Paste an article / news / info link', ph: 'https://example.com/breaking-story', btn: '📰 Turn Article into Video' },
  music: { label: 'What should the song be about?', ph: 'e.g. chasing dreams in the city at night', btn: '🎵 Generate Music Video' },
  educational: { label: 'What should we teach?', ph: 'e.g. how compound interest works', btn: '🎓 Generate Lesson Video' },
};

function setMode(mode) {
  currentMode = mode;
  $$('.mode').forEach(m => m.classList.toggle('active', m.dataset.mode === mode));
  const cfg = MODE_CFG[mode];
  $('#main-input-label').textContent = cfg.label;
  $('#main-input').placeholder = cfg.ph;
  $('#generate-btn').textContent = cfg.btn;
  $$('.field[data-for]').forEach(f => f.classList.toggle('show', f.dataset.for.includes(mode)));
}

async function generate() {
  const val = $('#main-input').value.trim();
  if (!val) { toast('Enter something first'); return; }
  const btn = $('#generate-btn'); btn.disabled = true;
  const res = $('#studio-result');
  res.innerHTML = loader('Forging your video… storyboard · voice · music · trend score');

  const common = {
    aspect: $('#f-aspect').value, platform: $('#f-platform').value,
    target_sec: +$('#f-length').value, style: $('#f-style').value, voice: $('#f-voice').value,
  };
  let endpoint, body;
  if (currentMode === 'prompt') { endpoint = '/generate'; body = { prompt: val, ...common, want_music: true }; }
  else if (currentMode === 'remake') { endpoint = '/remake'; body = { url: val, ...common }; }
  else if (currentMode === 'article') { endpoint = '/from-article'; body = { url: val, ...common }; }
  else if (currentMode === 'music') { endpoint = '/music-video'; body = { topic: val, genre: $('#f-genre').value, ...common }; }
  else if (currentMode === 'educational') { endpoint = '/educational'; body = { topic: val, level: $('#f-level').value, ...common }; }

  try {
    const project = await api(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (project.error) { res.innerHTML = `<div class="empty-state">⚠️ ${esc(project.error)}</div>`; }
    else { renderProject(project, res); toast('Video project created ✓'); }
  } catch (e) {
    res.innerHTML = `<div class="empty-state">⚠️ ${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
}

function renderProject(project, mount) {
  const sp = project.spec || {};
  const trend = sp.trend || {};
  const board = sp.storyboard || {};
  const pkg = sp.publish || board.package || {};
  const poster = sp.poster_url;
  const scenes = board.scenes || [];
  const music = sp.music;
  const song = sp.song || (music && music.lyrics ? music : null);

  mount.innerHTML = `<div class="result-card">
    <div class="result-top">
      <div class="poster">${poster ? `<img src="${poster}" alt="poster"/>` : '<div style="display:grid;place-items:center;height:100%;color:var(--muted)">🎬</div>'}</div>
      <div>
        <div class="score-ring">
          <div class="ring" style="--val:${trend.trend_score || 0}"><b>${trend.trend_score ?? '—'}</b></div>
          <div class="score-meta">
            <div class="grade">Trend score · Grade ${trend.grade || '—'}</div>
            <div class="verdict">${esc(trend.verdict || '')}</div>
          </div>
        </div>
        <div class="meta">
          <span class="tagchip">${esc(project.kind)}</span>
          <span class="tagchip">${esc(sp.aspect || '')}</span>
          <span class="tagchip">${esc(sp.platform || '')}</span>
          <span class="tagchip">${esc(sp.style || '')}</span>
        </div>
        <h3 style="margin:10px 0 4px">${esc(project.title)}</h3>
        ${pkg.caption ? `<p class="hint">${esc(pkg.caption)}</p>` : ''}
        <div class="card-actions">
          <button class="btn primary" onclick="openPost('${project.id}')">🚀 Post / Schedule</button>
          <button class="btn ghost" onclick="regenerate('${esc(project.prompt || project.title)}')">🔄 Remix</button>
          <button class="btn ghost" onclick="copyScript(this)" data-script="${esc(board.script || '')}">📋 Copy script</button>
        </div>
      </div>
    </div>
    ${sp.mock_notice ? `<div class="mock-note">⚠️ Preview generated with smart mocks. Add provider API keys in .env for full MP4 / audio renders.</div>` : ''}

    ${trend.factors ? scoreBlock(trend) : ''}
    ${scenes.length ? sceneBlock(scenes) : ''}
    ${song ? songBlock(song) : ''}
    ${sp.lesson_outline ? lessonBlock(sp.lesson_outline) : ''}
    ${pkg.hashtags ? publishBlock(pkg) : ''}
    ${sp.voiceover ? voiceBlock(sp.voiceover) : ''}
  </div>`;
}

function scoreBlock(t) {
  const f = t.factors;
  return `<div class="section-block"><h4>Why this score</h4>
    <div class="factors">${Object.entries(f).map(([k, v]) => `
      <div class="factor"><span>${k.replace('_', ' ')}</span>
        <div class="fbar"><i style="width:${v.score}%"></i></div><span>${v.score}</span></div>`).join('')}
    </div>
    ${t.top_fixes && t.top_fixes.length ? `<h4>Boost it</h4><ul class="fixes">${t.top_fixes.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
  </div>`;
}

function sceneBlock(scenes) {
  return `<div class="section-block"><h4>Storyboard · ${scenes.length} scenes</h4>
    ${scenes.map(s => `<div class="scene">
      <div class="idx">${s.index ?? ''}</div>
      <div style="flex:1">
        <div class="stitle">${esc(s.title || '')} <span class="sdur">· ${s.duration_sec || 4}s</span></div>
        <div class="snarr">${esc(s.narration || '')}</div>
        ${s.on_screen_text ? `<div class="sost">📝 ${esc(s.on_screen_text)}</div>` : ''}
      </div></div>`).join('')}
  </div>`;
}

function songBlock(song) {
  const L = song.lyrics || {};
  const lines = Object.entries(L).map(([sec, v]) =>
    `[${sec.replace('_', ' ').toUpperCase()}]\n${Array.isArray(v) ? v.join('\n') : v}`).join('\n\n');
  return `<div class="section-block"><h4>🎵 ${esc(song.title || 'Track')}</h4>
    <div class="meta"><span class="tagchip">${esc(song.genre)}</span><span class="tagchip">${esc(song.mood)}</span>
      <span class="tagchip">${song.bpm} BPM</span><span class="tagchip">${esc(song.key)}</span></div>
    <div class="lyrics">${esc(lines)}</div></div>`;
}

function lessonBlock(o) {
  return `<div class="section-block"><h4>🎓 Lesson outline</h4>
    <div class="stitle" style="margin-bottom:8px">${esc(o.title || '')}</div>
    ${(o.sections || []).map(s => `<div class="scene"><div style="flex:1">
      <div class="stitle">${esc(s.heading)}</div>
      <div class="snarr">${(s.points || []).map(esc).join(' · ')}</div></div></div>`).join('')}
  </div>`;
}

function publishBlock(pkg) {
  return `<div class="section-block"><h4>Publish package</h4>
    ${pkg.best_post_time ? `<p class="hint">⏰ Best post time: <b>${esc(pkg.best_post_time)}</b></p>` : ''}
    <div class="kv" style="margin-top:8px">${(pkg.hashtags || []).map(h =>
    `<span class="tagchip copy" onclick="copyText('${esc(h)}')">${esc(h)}</span>`).join('')}</div>
    ${pkg.hooks ? `<h4>Alt hooks</h4>${pkg.hooks.map(h => `<div class="scene"><div class="snarr">${esc(h)}</div></div>`).join('')}` : ''}
  </div>`;
}

function voiceBlock(v) {
  return `<div class="section-block"><h4>🎙️ Voiceover</h4>
    <div class="meta"><span class="tagchip">${esc(v.voice)}</span>
      ${v.estimated_seconds ? `<span class="tagchip">~${v.estimated_seconds}s</span>` : ''}
      ${v.word_count ? `<span class="tagchip">${v.word_count} words</span>` : ''}
      <span class="tagchip">${esc(v.provider || v.source)}</span></div></div>`;
}

window.regenerate = (prompt) => { switchTab('studio'); setMode('prompt'); $('#main-input').value = prompt; generate(); };
window.copyScript = (el) => { copyText(el.dataset.script); };
window.copyText = (t) => { navigator.clipboard.writeText(t).then(() => toast('Copied')); };

/* ── gallery ──────────────────────────────────────────── */
async function loadGallery() {
  $('#gallery-grid').innerHTML = loader('Loading your videos…');
  const d = await api('/projects?limit=60');
  if (!d.projects.length) { $('#gallery-grid').innerHTML = '<div class="empty-state"><div class="big-emoji">🖼️</div><p>No videos yet — head to the Video Studio to make your first one.</p></div>'; return; }
  $('#gallery-grid').innerHTML = d.projects.map(galleryCard).join('');
  $$('#gallery-grid .open').forEach(b => b.addEventListener('click', async () => {
    const p = await api('/projects/' + b.dataset.id);
    switchTab('studio'); renderProject(p, $('#studio-result')); window.scrollTo({ top: 0, behavior: 'smooth' });
  }));
  $$('#gallery-grid .del').forEach(b => b.addEventListener('click', async () => {
    await api('/projects/' + b.dataset.id, { method: 'DELETE' }); toast('Deleted'); loadGallery();
  }));
  $$('#gallery-grid .post').forEach(b => b.addEventListener('click', () => openPost(b.dataset.id)));
}

function galleryCard(p) {
  const poster = (p.spec || {}).poster_url;
  return `<div class="card">
    <div class="poster" style="aspect-ratio:9/16;margin-bottom:10px">${poster ? `<img src="${poster}"/>` : '<div style="display:grid;place-items:center;height:100%">🎬</div>'}</div>
    <div class="topic">${esc(p.title)}</div>
    <div class="meta"><span class="tagchip">${esc(p.kind)}</span><span class="badge first">${p.trend_score}</span></div>
    <div class="card-actions">
      <button class="btn primary open" data-id="${p.id}">Open</button>
      <button class="btn ghost post" data-id="${p.id}" title="Post / Schedule">🚀</button>
      <button class="btn ghost del" data-id="${p.id}">🗑️</button>
    </div>
  </div>`;
}

/* ── post / schedule modal ────────────────────────────── */
let POST_PID = null;
let POST_WHEN = 'now';

function wirePostModal() {
  $('#post-close').addEventListener('click', closePost);
  $('#post-modal').addEventListener('click', e => { if (e.target.id === 'post-modal') closePost(); });
  $$('#post-when .seg-btn').forEach(b => b.addEventListener('click', () => {
    $$('#post-when .seg-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); POST_WHEN = b.dataset.when;
    $('#post-datetime').style.display = POST_WHEN === 'custom' ? 'block' : 'none';
  }));
  $('#post-submit').addEventListener('click', submitPost);
}

async function openPost(pid) {
  POST_PID = pid; POST_WHEN = 'now';
  const project = await api('/projects/' + pid);
  $('#post-project-name').textContent = '🎬 ' + (project.title || pid);
  // platforms — preselect the project's target platform
  const target = (project.spec || {}).platform;
  $('#post-platforms').innerHTML = STATUS.platforms.map(p => `
    <div class="pchip ${p === target ? 'on' : ''}" data-p="${p}"><span class="dot"></span>${p}</div>`).join('');
  $$('#post-platforms .pchip').forEach(c => c.addEventListener('click', () => c.classList.toggle('on')));
  // caption preview (caption + hashtags)
  const pkg = (project.spec || {}).publish || ((project.spec || {}).storyboard || {}).package || {};
  const cap = [pkg.caption || project.title, (pkg.hashtags || []).join(' ')].filter(Boolean).join('\n\n');
  $('#post-caption').value = cap;
  $$('#post-when .seg-btn').forEach((x, i) => x.classList.toggle('active', i === 0));
  $('#post-datetime').style.display = 'none';
  $('#post-result').innerHTML = '';
  $('#post-submit').disabled = false; $('#post-submit').textContent = '🚀 Publish';
  $('#post-modal').classList.add('show');
}
function closePost() { $('#post-modal').classList.remove('show'); }

async function submitPost() {
  const platforms = $$('#post-platforms .pchip.on').map(c => c.dataset.p);
  if (!platforms.length) { toast('Pick at least one platform'); return; }
  let when = POST_WHEN;
  if (POST_WHEN === 'custom') {
    const dt = $('#post-datetime').value;
    if (!dt) { toast('Pick a date & time'); return; }
    when = new Date(dt).toISOString();
  }
  const btn = $('#post-submit'); btn.disabled = true; btn.textContent = 'Publishing…';
  const out = await api(`/projects/${POST_PID}/post`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platforms, when, caption: $('#post-caption').value }),
  });
  if (out.error) { $('#post-result').innerHTML = `<p class="hint">⚠️ ${esc(out.error)}</p>`; btn.disabled = false; return; }
  const res = out.result || {};
  const lines = (Array.isArray(res.results) ? res.results : platforms.map(p => ({ platform: p, status: res.status }))).map(r => `
    <div class="post-line"><span>${esc(r.platform)}</span>
      <span class="${out.scheduled ? 'sch' : 'ok'}">${out.scheduled ? '🕒 scheduled' : '✓ ' + (r.status || 'published')}</span>
      ${r.permalink ? `<a href="${r.permalink}" target="_blank">view ↗</a>` : ''}</div>`).join('');
  $('#post-result').innerHTML = `<div class="post-results">${lines}</div>
    ${out.scheduled ? `<p class="hint">📅 Scheduled for ${esc(res.schedule_time || when)}</p>` : ''}
    ${out.mock ? `<p class="hint">⚠️ Mock publish — add AYRSHARE_API_KEY in .env to post for real.</p>` : ''}`;
  btn.textContent = out.scheduled ? '✓ Scheduled' : '✓ Published';
  toast(out.scheduled ? 'Scheduled ✓' : 'Posted ✓');
}
window.openPost = openPost;

/* ── helpers ──────────────────────────────────────────── */
function switchTab(name) {
  $$('.tab').forEach(x => x.classList.toggle('active', x.dataset.tab === name));
  $$('.panel').forEach(x => x.classList.toggle('active', x.id === 'tab-' + name));
}
const loader = (msg) => `<div class="loader"><div class="spinner"></div><span>${msg}</span></div>`;

boot();
