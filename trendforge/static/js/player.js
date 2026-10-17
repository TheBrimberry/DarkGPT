/* TrendForge in-browser video renderer.
 *
 * Turns a generated project's storyboard into a REAL, playing animated video on
 * a <canvas> — timed scenes, animated captions, brainrot split-screen, a synth
 * soundtrack — and records it to a downloadable .webm via MediaRecorder. 100%
 * client-side, so it works on the deployed site with no API keys.
 */
const TFPlayer = (function () {
  const DIMS = { '9:16': [540, 960], '16:9': [960, 540], '1:1': [720, 720], '4:5': [720, 900] };
  const PAL = {
    cinematic: ['#0f0c29', '#302b63', '#24243e'], vibrant: ['#ff0844', '#ffb199', '#ff6a00'],
    clean: ['#1a2340', '#2a3a6a', '#3a5a9a'], neon: ['#000000', '#7928ca', '#ff0080'],
    documentary: ['#232526', '#414345', '#1c1c1c'], brainrot: ['#1a0033', '#ff00d4', '#00ff88'],
  };
  const EMOJIS = ['💀', '🔥', '😭', '🤯', '🗿', '💯', '🧠', '👹', '⁉️', '✨'];

  let el = {}, canvas, ctx, W, H, scenes, style, isBR, title, brMeta;
  let raf = 0, t0 = 0, pausedAt = 0, total = 0, playing = false, recording = false;
  let rec, chunks, audio = null, rain = [];

  // ── DOM ────────────────────────────────────────────────────────────────
  function build() {
    if (el.wrap) return;
    const wrap = document.createElement('div');
    wrap.className = 'tfp-back';
    wrap.innerHTML = `
      <div class="tfp-modal">
        <div class="tfp-head"><b id="tfp-title">Preview</b><button class="tfp-x" id="tfp-x">✕</button></div>
        <div class="tfp-stage"><canvas id="tfp-canvas"></canvas>
          <button class="tfp-big" id="tfp-big">▶</button>
        </div>
        <div class="tfp-bar"><i id="tfp-fill"></i></div>
        <div class="tfp-ctrls">
          <button class="btn" id="tfp-play">▶ Play</button>
          <button class="btn ghost" id="tfp-mute">🔊</button>
          <span class="tfp-time" id="tfp-time">0:00</span>
          <span style="flex:1"></span>
          <button class="btn primary" id="tfp-dl">⬇ Download video</button>
        </div>
        <div class="tfp-note" id="tfp-note"></div>
      </div>`;
    document.body.appendChild(wrap);
    el = {
      wrap, title: wrap.querySelector('#tfp-title'), canvas: wrap.querySelector('#tfp-canvas'),
      big: wrap.querySelector('#tfp-big'), fill: wrap.querySelector('#tfp-fill'),
      play: wrap.querySelector('#tfp-play'), mute: wrap.querySelector('#tfp-mute'),
      time: wrap.querySelector('#tfp-time'), dl: wrap.querySelector('#tfp-dl'), note: wrap.querySelector('#tfp-note'),
    };
    canvas = el.canvas; ctx = canvas.getContext('2d');
    wrap.addEventListener('click', e => { if (e.target === wrap) close(); });
    el.wrap.querySelector('#tfp-x').addEventListener('click', close);
    el.play.addEventListener('click', toggle);
    el.big.addEventListener('click', toggle);
    el.mute.addEventListener('click', () => { muted = !muted; el.mute.textContent = muted ? '🔇' : '🔊'; if (audio) audio.master.gain.value = muted ? 0 : gainFor(); });
    el.dl.addEventListener('click', download);
  }

  let muted = false;
  function gainFor() { return isBR ? 0.22 : 0.14; }

  // ── open ───────────────────────────────────────────────────────────────
  async function openById(pid) {
    const p = await fetch('/api/projects/' + pid).then(r => r.json());
    open(p);
  }
  function open(project) {
    build();
    const sp = project.spec || {};
    style = sp.style || 'vibrant';
    isBR = project.kind === 'brainrot' || style === 'brainrot';
    scenes = ((sp.storyboard || {}).scenes || []).map(s => ({
      big: (s.on_screen_text || s.title || '').toString(),
      sub: (s.narration || '').toString(),
      dur: Math.max(1.6, Math.min(8, +s.duration_sec || 3.5)),
    }));
    if (!scenes.length) scenes = [{ big: project.title || 'TRENDFORGE', sub: '', dur: 4 }];
    brMeta = sp.brainrot || {};
    title = (project.title || 'trendforge-video').replace(/[^\w\-]+/g, '_').slice(0, 40);
    total = scenes.reduce((a, s) => a + s.dur, 0);
    const [w, h] = DIMS[sp.aspect] || DIMS['9:16'];
    W = canvas.width = w; H = canvas.height = h;
    canvas.style.aspectRatio = w + '/' + h;
    // deterministic emoji rain
    rain = Array.from({ length: 14 }, (_, i) => ({
      e: EMOJIS[i % EMOJIS.length], x: (i * 97) % W, sp: 60 + (i * 37) % 160,
      ph: (i * 53) % H, sz: 26 + (i * 17) % 46,
    }));
    el.title.textContent = (isBR ? '🧠 ' : '🎬 ') + (project.title || 'Preview');
    el.note.textContent = 'Real animated video, rendered in your browser. Hit Download to save it as a .webm you can watch & upload.';
    el.wrap.classList.add('show');
    seek(0); drawAt(0); setBig(true);
  }
  function close() { stop(); if (el.wrap) el.wrap.classList.remove('show'); }
  function setBig(show) { el.big.style.display = show ? '' : 'none'; }

  // ── transport ──────────────────────────────────────────────────────────
  function toggle() { playing ? pause() : play(); }
  function play() {
    if (pausedAt >= total) pausedAt = 0;
    startAudio(false);
    playing = true; setBig(false); el.play.textContent = '⏸ Pause';
    t0 = performance.now() - pausedAt * 1000;
    loop();
  }
  function pause() { playing = false; setBig(true); el.play.textContent = '▶ Play'; cancelAnimationFrame(raf); stopAudio(); }
  function stop() { playing = false; recording = false; cancelAnimationFrame(raf); stopAudio(); if (rec && rec.state !== 'inactive') try { rec.stop(); } catch (e) {} }
  function seek(sec) { pausedAt = sec; el.fill.style.width = (sec / total * 100) + '%'; el.time.textContent = fmt(sec); }

  function loop() {
    const elapsed = (performance.now() - t0) / 1000;
    if (elapsed >= total) { drawAt(total); seek(total); finishPlay(); return; }
    drawAt(elapsed); seek(elapsed);
    raf = requestAnimationFrame(loop);
  }
  function finishPlay() {
    playing = false; el.play.textContent = '↻ Replay'; setBig(true); stopAudio();
    if (recording) finishRecord();
  }

  // ── download (record) ────────────────────────────────────────────────────
  function download() {
    if (!canvas.captureStream || typeof MediaRecorder === 'undefined') {
      el.note.textContent = '⚠️ Your browser can’t record video. Try latest Chrome/Edge.'; return;
    }
    stop();
    const vstream = canvas.captureStream(30);
    let stream = vstream;
    startAudio(true);
    try { if (audio) stream = new MediaStream([...vstream.getVideoTracks(), ...audio.dest.stream.getAudioTracks()]); } catch (e) {}
    const mime = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
      .find(m => MediaRecorder.isTypeSupported(m)) || 'video/webm';
    chunks = [];
    rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
    rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = saveBlob;
    recording = true; el.dl.disabled = true; el.dl.textContent = '● Recording…';
    rec.start();
    pausedAt = 0; playing = true; setBig(false); el.play.textContent = '⏸ Pause';
    t0 = performance.now(); loop();
  }
  function finishRecord() { recording = false; try { rec.stop(); } catch (e) {} }
  function saveBlob() {
    const blob = new Blob(chunks, { type: 'video/webm' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = title + '.webm';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    el.dl.disabled = false; el.dl.textContent = '⬇ Download video';
    el.note.textContent = '✅ Saved ' + title + '.webm — open it to watch, or upload it to TikTok/Reels/Shorts.';
    stopAudio();
  }

  // ── drawing ──────────────────────────────────────────────────────────────
  function sceneAt(t) {
    let acc = 0;
    for (let i = 0; i < scenes.length; i++) { const d = scenes[i].dur; if (t < acc + d) return { s: scenes[i], local: t - acc, d, i }; acc += d; }
    const last = scenes[scenes.length - 1]; return { s: last, local: last.dur, d: last.dur, i: scenes.length - 1 };
  }
  function drawAt(t) {
    const { s, local, d, i } = sceneAt(t);
    isBR ? bgBrainrot(t) : bgGradient(t, i);
    const pop = easeOutBack(Math.min(1, local / 0.45));
    const bob = 1 + Math.sin(t * 3) * 0.02;
    caption(s.big, pop * bob, t);
    subtitle(s.sub, local / d);
    if (local < 0.12) { ctx.fillStyle = 'rgba(255,255,255,' + (0.12 - local) * 4 + ')'; ctx.fillRect(0, 0, W, H); }
    hud(i);
  }

  function bgGradient(t, i) {
    const p = PAL[style] || PAL.vibrant;
    const a = t * 0.15;
    const g = ctx.createLinearGradient(W * (0.5 + 0.5 * Math.cos(a)), 0, W * (0.5 - 0.5 * Math.cos(a)), H);
    g.addColorStop(0, p[0]); g.addColorStop(0.5, p[1]); g.addColorStop(1, p[2]);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalAlpha = 0.08; ctx.fillStyle = '#fff';
    for (let k = 0; k < 3; k++) {
      const cx = W * (0.2 + 0.3 * k) + Math.sin(t * 0.6 + k) * 60;
      const cy = H * (0.3 + 0.2 * k) + Math.cos(t * 0.5 + k) * 60;
      ctx.beginPath(); ctx.arc(cx, cy, 120 + k * 40, 0, 7); ctx.fill();
    }
    ctx.restore();
  }
  function bgBrainrot(t) {
    const mid = H / 2;
    let g = ctx.createLinearGradient(0, 0, W, mid);
    g.addColorStop(0, '#1a0033'); g.addColorStop(0.5, `hsl(${300 + Math.sin(t) * 30},100%,50%)`); g.addColorStop(1, '#7928ca');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, mid);
    g = ctx.createLinearGradient(0, mid, W, H);
    g.addColorStop(0, '#00ff88'); g.addColorStop(0.5, '#0066ff'); g.addColorStop(1, '#00ffcc');
    ctx.fillStyle = g; ctx.fillRect(0, mid, W, H - mid);
    // gameplay lanes + scrolling blocks (subway-surfers vibe)
    ctx.save(); ctx.globalAlpha = 0.25; ctx.fillStyle = '#fff';
    for (let x = 0.25; x < 1; x += 0.25) ctx.fillRect(W * x - 3, mid, 6, H - mid);
    ctx.restore();
    const lanes = [0.3, 0.5, 0.7];
    lanes.forEach((lx, k) => {
      const y = mid + ((t * (180 + k * 40) + k * 200) % (H - mid));
      ctx.fillStyle = ['#ffeb3b', '#ff5470', '#ffffff'][k];
      ctx.globalAlpha = 0.9; roundRect(W * lx - 34, y - 34, 68, 68, 12); ctx.fill(); ctx.globalAlpha = 1;
    });
    // emoji rain
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    rain.forEach(r => {
      const y = (r.ph + t * r.sp) % (H + 60) - 30;
      ctx.font = r.sz + 'px serif'; ctx.globalAlpha = 0.9; ctx.fillText(r.e, r.x, y); ctx.globalAlpha = 1;
    });
  }

  function caption(text, scale, t) {
    if (!text) return;
    const words = text.toUpperCase().split(/\s+/);
    let fs = isBR ? 74 : 62; const maxW = W * 0.86;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    let lines = wrap(words, maxW, fs);
    while (lines.length > 3 && fs > 34) { fs -= 6; lines = wrap(words, maxW, fs); }
    const lh = fs * 1.05, y0 = H * (isBR ? 0.5 : 0.46) - (lines.length - 1) * lh / 2;
    ctx.save(); ctx.translate(W / 2, y0 + (lines.length - 1) * lh / 2);
    ctx.scale(scale, scale); ctx.translate(-W / 2, -(y0 + (lines.length - 1) * lh / 2));
    ctx.font = `900 ${fs}px "Arial Black", Impact, sans-serif`;
    ctx.lineJoin = 'round'; ctx.strokeStyle = '#000'; ctx.lineWidth = isBR ? 11 : 8;
    lines.forEach((ln, i) => { const y = y0 + i * lh; ctx.strokeText(ln, W / 2, y); ctx.fillStyle = '#fff'; ctx.fillText(ln, W / 2, y); });
    ctx.restore();
  }
  function subtitle(text, prog) {
    if (!text) return;
    const words = text.split(/\s+/); const show = Math.max(1, Math.ceil(words.length * Math.min(1, prog + 0.05)));
    const line = words.slice(0, show).join(' ');
    const fs = Math.max(20, W * 0.042); ctx.font = `600 ${fs}px Inter, Arial, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    const y = H * 0.9; const w = Math.min(W * 0.9, ctx.measureText(line).width + 40);
    ctx.fillStyle = 'rgba(0,0,0,0.55)'; roundRect(W / 2 - w / 2, y - fs - 16, w, fs + 22, 12); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.fillText(line, W / 2, y);
  }
  function hud(i) {
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.font = `700 ${W * 0.03}px Inter, Arial`; ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fillText(`${i + 1}/${scenes.length}`, 18, 18);
    ctx.textAlign = 'right'; ctx.fillText('TrendForge', W - 18, 18);
  }

  // ── audio ────────────────────────────────────────────────────────────────
  function startAudio() {
    stopAudio();
    try {
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      const c = new AC(); const master = c.createGain(); master.gain.value = muted ? 0 : gainFor();
      master.connect(c.destination);
      const dest = c.createMediaStreamDestination(); master.connect(dest);
      const bpm = isBR ? 140 : 88, beat = 60 / bpm;
      if (!isBR) { // soft pad drone for non-brainrot
        [220, 277].forEach(f => { const o = c.createOscillator(), g = c.createGain(); o.type = 'sine'; o.frequency.value = f; g.gain.value = 0.08; o.connect(g).connect(master); o.start(); });
      }
      let next = c.currentTime + 0.08;
      const timer = setInterval(() => {
        if (c.state === 'suspended') c.resume();
        while (next < c.currentTime + 0.25) { kick(c, master, next); if (isBR) hat(c, master, next + beat / 2); next += beat; }
      }, 40);
      audio = { c, master, dest, timer };
      if (c.state === 'suspended') c.resume();
    } catch (e) { audio = null; }
  }
  function stopAudio() { if (audio) { try { clearInterval(audio.timer); audio.c.close(); } catch (e) {} audio = null; } }
  function kick(c, out, t) { const o = c.createOscillator(), g = c.createGain(); o.frequency.setValueAtTime(160, t); o.frequency.exponentialRampToValueAtTime(50, t + 0.12); g.gain.setValueAtTime(1, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.16); o.connect(g).connect(out); o.start(t); o.stop(t + 0.18); }
  function hat(c, out, t) { const o = c.createOscillator(), g = c.createGain(); o.type = 'square'; o.frequency.value = 8000; g.gain.setValueAtTime(0.25, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.04); o.connect(g).connect(out); o.start(t); o.stop(t + 0.05); }

  // ── util ─────────────────────────────────────────────────────────────────
  function wrap(words, maxW, fs) {
    ctx.font = `900 ${fs}px "Arial Black", sans-serif`;
    const lines = []; let cur = '';
    words.forEach(w => { const test = cur ? cur + ' ' + w : w; if (ctx.measureText(test).width > maxW && cur) { lines.push(cur); cur = w; } else cur = test; });
    if (cur) lines.push(cur); return lines;
  }
  function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  function easeOutBack(x) { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); }
  function fmt(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }

  return { open, openById };
})();
window.TFPlayer = TFPlayer;
