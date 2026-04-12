/* ── Tab Navigation ─────────────────────────────────────────────── */
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        const tab = link.dataset.tab;

        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById(`tab-${tab}`).classList.add('active');

        // Close sidebar on mobile when a link is clicked
        closeSidebar();

        if (tab === 'dashboard') refreshDashboard();
        if (tab === 'webhook') loadWebhookInfo();
        if (tab === 'settings') loadSettings();
    });
});

/* ── Sidebar toggle (mobile) ───────────────────────────────────── */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const isOpen = sidebar.classList.toggle('open');
    overlay.classList.toggle('open', isOpen);
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('open');
}

/* ── Auto-refresh ──────────────────────────────────────────────── */
let refreshTimer = null;
let refreshCountdownValue = 30;

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshCountdownValue = 30;
    updateCountdownDisplay();
    refreshTimer = setInterval(() => {
        refreshCountdownValue--;
        if (refreshCountdownValue <= 0) {
            refreshCountdownValue = 30;
            refreshDashboard();
        }
        updateCountdownDisplay();
    }, 1000);
}

function updateCountdownDisplay() {
    const el = document.getElementById('refreshCountdown');
    if (el) el.textContent = refreshCountdownValue;
}

/* ── Charts ────────────────────────────────────────────────────── */
let activityChart = null;
let statusChart = null;

function initCharts() {
    const chartDefaults = {
        color: '#94a3b8',
        borderColor: 'rgba(42,53,80,0.7)',
    };

    // Bar chart – daily signal activity
    const actCtx = document.getElementById('activityChart').getContext('2d');
    activityChart = new Chart(actCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Executed',
                    data: [],
                    backgroundColor: 'rgba(16,185,129,0.75)',
                    borderColor: 'rgba(16,185,129,1)',
                    borderWidth: 1,
                },
                {
                    label: 'Failed',
                    data: [],
                    backgroundColor: 'rgba(239,68,68,0.75)',
                    borderColor: 'rgba(239,68,68,1)',
                    borderWidth: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    stacked: true,
                    grid: { color: 'rgba(42,53,80,0.5)' },
                    ticks: { color: '#94a3b8', font: { size: 11 } },
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: 'rgba(42,53,80,0.5)' },
                    ticks: { color: '#94a3b8', font: { size: 11 }, stepSize: 1 },
                },
            },
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { size: 12 }, boxWidth: 14 } },
            },
        },
    });

    // Doughnut chart – status breakdown
    const statCtx = document.getElementById('statusChart').getContext('2d');
    statusChart = new Chart(statCtx, {
        type: 'doughnut',
        data: {
            labels: ['Executed', 'Failed', 'Pending'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    'rgba(16,185,129,0.85)',
                    'rgba(239,68,68,0.85)',
                    'rgba(59,130,246,0.85)',
                ],
                borderColor: '#0a0e17',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { size: 12 }, boxWidth: 14, padding: 16 },
                },
            },
        },
    });
}

async function updateCharts(stats) {
    // Doughnut – totals from stats
    if (statusChart) {
        // 'received' is the pending/unprocessed status; anything that isn't executed or failed counts as pending
        const pending = Math.max(0, (stats.total_signals || 0) - (stats.executed || 0) - (stats.failed || 0));
        statusChart.data.datasets[0].data = [stats.executed || 0, stats.failed || 0, pending];
        statusChart.update('none');
    }

    // Bar chart – daily breakdown from /api/signals/chart
    try {
        const res = await fetch('/api/signals/chart');
        const data = await res.json();
        if (activityChart && data.labels) {
            activityChart.data.labels = data.labels;
            activityChart.data.datasets[0].data = data.executed;
            activityChart.data.datasets[1].data = data.failed;
            activityChart.update('none');
        }
    } catch (err) {
        console.error('Chart update error:', err);
    }
}

/* ── Dashboard ─────────────────────────────────────────────────── */
async function refreshDashboard() {
    // Reset auto-refresh countdown
    refreshCountdownValue = 30;
    updateCountdownDisplay();

    try {
        const [sigRes, posRes] = await Promise.all([
            fetch('/api/signals').then(r => r.json()),
            fetch('/api/positions').then(r => r.json()).catch(() => null),
        ]);

        // Stats
        const stats = sigRes.stats || {};
        document.getElementById('statTotal').textContent = stats.total_signals || 0;
        document.getElementById('statExecuted').textContent = stats.executed || 0;
        document.getElementById('statFailed').textContent = stats.failed || 0;
        const pnl = stats.total_pnl || 0;
        const pnlEl = document.getElementById('statPnl');
        pnlEl.textContent = `$${pnl.toFixed(2)}`;
        pnlEl.style.color = pnl >= 0 ? 'var(--success)' : 'var(--danger)';

        // Balance
        if (posRes && posRes.balance && !posRes.balance.error) {
            const b = posRes.balance;
            const balCard = document.getElementById('balanceCard');
            balCard.style.display = 'block';
            document.getElementById('balanceGrid').innerHTML = `
                <div class="balance-item"><div class="label">Total Balance</div><div class="value">$${parseFloat(b.accountBalanceRv || 0).toFixed(2)}</div></div>
                <div class="balance-item"><div class="label">Available</div><div class="value">$${parseFloat(b.availBalanceRv || 0).toFixed(2)}</div></div>
                <div class="balance-item"><div class="label">In Use</div><div class="value">$${parseFloat(b.totalUsedBalanceRv || 0).toFixed(2)}</div></div>
                <div class="balance-item"><div class="label">Unrealized P&L</div><div class="value" style="color:${parseFloat(b.totalPnlRv || 0) >= 0 ? 'var(--success)' : 'var(--danger)'}">$${parseFloat(b.totalPnlRv || 0).toFixed(2)}</div></div>
            `;

            // Update connection status
            setConnectionStatus('online', 'Connected');
        }

        // Positions
        if (posRes && posRes.positions && posRes.positions.length > 0) {
            const posCard = document.getElementById('positionsCard');
            posCard.style.display = 'block';
            document.getElementById('positionsList').innerHTML = posRes.positions.map(p => `
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border);">
                    <span><strong>${p.symbol}</strong> <span class="badge ${p.side === 'Buy' ? 'badge-buy' : 'badge-sell'}">${p.side}</span></span>
                    <span>Size: ${p.size} | Entry: ${p.avgEntryPriceRp || 'N/A'} | uPnL: ${p.unrealisedPnlRv || '0'}</span>
                </div>
            `).join('');
        }

        // Signal table
        const signals = sigRes.signals || [];
        const tbody = document.getElementById('signalTableBody');
        if (signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No signals yet. Configure your webhook to get started.</td></tr>';
        } else {
            tbody.innerHTML = signals.map(s => {
                const time = new Date(s.timestamp).toLocaleString();
                const action = s.action || '';
                const actionClass = ['buy', 'long'].includes(action.toLowerCase()) ? 'badge-buy' : 'badge-sell';
                const statusClass = `badge-${s.status}`;
                return `<tr>
                    <td>${time}</td>
                    <td><strong>${s.symbol}</strong></td>
                    <td><span class="badge ${actionClass}">${action}</span></td>
                    <td>${s.order_type || 'market'}</td>
                    <td>${s.qty || '-'}</td>
                    <td>${s.price || '-'}</td>
                    <td>${s.stop_loss || '-'}</td>
                    <td>${s.take_profit || '-'}</td>
                    <td><span class="badge ${statusClass}">${s.status}</span></td>
                </tr>`;
            }).join('');
        }

        // Update charts
        await updateCharts(stats);
    } catch (err) {
        console.error('Dashboard refresh error:', err);
    }
}

async function clearSignals() {
    if (!confirm('Clear all signal history?')) return;
    await fetch('/api/signals/clear', { method: 'POST' });
    refreshDashboard();
}

/* ── Connection Status ─────────────────────────────────────────── */
function setConnectionStatus(state, text) {
    const el = document.getElementById('connectionStatus');
    el.innerHTML = `<span class="status-dot ${state}"></span><span class="status-text">${text}</span>`;
}

/* ── Webhook Setup ─────────────────────────────────────────────── */
async function loadWebhookInfo() {
    try {
        const res = await fetch('/api/webhook-info');
        const data = await res.json();
        document.getElementById('webhookUrl').textContent = data.webhook_url;
        document.getElementById('alertTemplate').textContent = JSON.stringify(data.example_payload, null, 2);
    } catch (err) {
        console.error('Webhook info error:', err);
    }
}

function copyWebhookUrl() {
    const text = document.getElementById('webhookUrl').textContent;
    navigator.clipboard.writeText(text);
    showToast('Webhook URL copied!');
}

function copyAlertTemplate() {
    const text = document.getElementById('alertTemplate').textContent;
    navigator.clipboard.writeText(text);
    showToast('Alert template copied!');
}

/* ── Test Signal ───────────────────────────────────────────────── */
async function sendTestSignal() {
    const payload = {
        action: document.getElementById('testAction').value,
        symbol: document.getElementById('testSymbol').value,
        qty: parseFloat(document.getElementById('testQty').value),
        type: document.getElementById('testType').value,
        leverage: parseInt(document.getElementById('testLeverage').value),
    };

    const price = document.getElementById('testPrice').value;
    if (price) payload.price = parseFloat(price);

    const sl = document.getElementById('testSl').value;
    if (sl) payload.sl = parseFloat(sl);

    const tp = document.getElementById('testTp').value;
    if (tp) payload.tp = parseFloat(tp);

    const resultEl = document.getElementById('testResult');
    resultEl.style.display = 'block';
    resultEl.className = 'result-box info';
    resultEl.textContent = 'Sending signal...';

    try {
        const res = await fetch('/webhook', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
            resultEl.className = 'result-box success';
            resultEl.textContent = JSON.stringify(data, null, 2);
        } else {
            resultEl.className = 'result-box error';
            resultEl.textContent = JSON.stringify(data, null, 2);
        }
        refreshDashboard();
    } catch (err) {
        resultEl.className = 'result-box error';
        resultEl.textContent = 'Error: ' + err.message;
    }
}

/* ── Code Converter ────────────────────────────────────────────── */
async function convertCode() {
    const inputCode = document.getElementById('inputCode').value.trim();
    if (!inputCode) {
        showToast('Please paste some code or describe a strategy first.');
        return;
    }

    const language = document.getElementById('inputLanguage').value;
    const btn = document.getElementById('convertBtn');
    const outputEl = document.getElementById('outputCode');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Converting...';
    outputEl.value = 'Converting your code to PineScript v5...\nThis may take a moment...';

    try {
        const res = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: inputCode, language }),
        });
        const data = await res.json();
        if (data.pinescript) {
            outputEl.value = data.pinescript;
        } else {
            outputEl.value = 'Error: ' + (data.error || 'Unknown error');
        }
    } catch (err) {
        outputEl.value = 'Error: ' + err.message;
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg> Convert`;
    }
}

function copyPinescript() {
    const text = document.getElementById('outputCode').value;
    if (text) {
        navigator.clipboard.writeText(text);
        showToast('PineScript copied!');
    }
}

/* ── AI Chat ───────────────────────────────────────────────────── */
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');

chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChat();
    }
});

async function sendChat() {
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    const sendBtn = document.getElementById('chatSendBtn');
    sendBtn.disabled = true;

    // Show typing indicator
    const typingId = appendMessage('assistant', '<span class="spinner"></span> Thinking...');

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        const data = await res.json();

        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (data.reply) {
            appendMessage('assistant', formatMarkdown(data.reply));
        } else {
            appendMessage('assistant', `<span style="color:var(--danger)">Error: ${data.error}</span>`);
        }
    } catch (err) {
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        appendMessage('assistant', `<span style="color:var(--danger)">Error: ${err.message}</span>`);
    } finally {
        sendBtn.disabled = false;
    }
}

function appendMessage(role, html) {
    const id = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.id = id;
    div.innerHTML = `<div class="message-content">${html}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

async function clearChat() {
    if (!confirm('Clear chat history?')) return;
    await fetch('/api/chat/clear', { method: 'POST' });
    chatMessages.innerHTML = `
        <div class="chat-message assistant">
            <div class="message-content">
                <p>Chat cleared. How can I help you?</p>
            </div>
        </div>
    `;
}

function formatMarkdown(text) {
    // Code blocks
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
    });
    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Italic
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    // Line breaks to paragraphs
    text = text.replace(/\n\n/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');
    // Wrap in paragraph
    if (!text.startsWith('<')) text = '<p>' + text + '</p>';
    return text;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* ── Settings ──────────────────────────────────────────────────── */
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const s = await res.json();
        document.getElementById('settPhemexKey').value = s.phemex_api_key || '';
        document.getElementById('settPhemexSecret').value = s.phemex_api_secret || '';
        document.getElementById('settTestnet').checked = s.phemex_testnet !== false;
        document.getElementById('settSymbol').value = s.default_symbol || 'BTCUSDT';
        document.getElementById('settQty').value = s.default_qty || 0.001;
        document.getElementById('settLeverage').value = s.default_leverage || 10;
        document.getElementById('settWebhookSecret').value = s.webhook_secret || '';
        document.getElementById('settLlmProvider').value = s.llm_provider || 'openai';
        document.getElementById('settModel').value = s.openai_model || 'gpt-4o';
        document.getElementById('settOpenaiKey').value = s.openai_api_key || '';
        document.getElementById('settGroqKey').value = s.groq_api_key || '';
    } catch (err) {
        console.error('Settings load error:', err);
    }
}

async function saveSettings() {
    const settings = {
        phemex_api_key: document.getElementById('settPhemexKey').value,
        phemex_api_secret: document.getElementById('settPhemexSecret').value,
        phemex_testnet: document.getElementById('settTestnet').checked,
        default_symbol: document.getElementById('settSymbol').value,
        default_qty: parseFloat(document.getElementById('settQty').value),
        default_leverage: parseInt(document.getElementById('settLeverage').value),
        webhook_secret: document.getElementById('settWebhookSecret').value,
        llm_provider: document.getElementById('settLlmProvider').value,
        openai_model: document.getElementById('settModel').value,
        openai_api_key: document.getElementById('settOpenaiKey').value,
        groq_api_key: document.getElementById('settGroqKey').value,
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        const data = await res.json();
        const el = document.getElementById('saveResult');
        el.style.color = 'var(--success)';
        el.textContent = 'Settings saved!';
        setTimeout(() => el.textContent = '', 3000);
    } catch (err) {
        const el = document.getElementById('saveResult');
        el.style.color = 'var(--danger)';
        el.textContent = 'Error saving: ' + err.message;
    }
}

async function testConnection() {
    const resultEl = document.getElementById('connectionResult');
    resultEl.style.color = 'var(--text-muted)';
    resultEl.textContent = 'Testing...';

    // Save settings first
    await saveSettings();

    try {
        const res = await fetch('/api/test-connection', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'connected') {
            resultEl.style.color = 'var(--success)';
            resultEl.textContent = `Connected! Balance: $${parseFloat(data.balance?.availBalanceRv || 0).toFixed(2)}`;
            setConnectionStatus('online', 'Connected');
        } else {
            resultEl.style.color = 'var(--danger)';
            resultEl.textContent = 'Failed: ' + (data.message || 'Unknown error');
            setConnectionStatus('error', 'Error');
        }
    } catch (err) {
        resultEl.style.color = 'var(--danger)';
        resultEl.textContent = 'Error: ' + err.message;
        setConnectionStatus('error', 'Error');
    }
}

/* ── Toast Notifications ───────────────────────────────────────── */
function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 9999;
        background: var(--bg-card); border: 1px solid var(--accent);
        border-radius: var(--radius); padding: 12px 20px;
        color: var(--text-primary); font-size: 13px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        animation: fadeIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

/* ── Auto-resize chat input ────────────────────────────────────── */
chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

/* ── Init ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    refreshDashboard();
    loadWebhookInfo();
    startAutoRefresh();
});
