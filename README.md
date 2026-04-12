# DarkGPT – TradingView → Phemex Webhook Trader

A full-stack web application that bridges TradingView strategy alerts to live / paper trading on the **Phemex** perpetual futures exchange. Includes an AI trading assistant, a code-to-PineScript v5 converter, a signal history dashboard with charts, and a fully configurable settings panel.

---

## ✨ Features

| Tab | What it does |
|-----|-------------|
| **Dashboard** | Live stats, account balance, open positions, signal log, activity charts. Auto-refreshes every 30 s. |
| **Webhook Setup** | One-click webhook URL copy, TradingView alert template, step-by-step guide, manual signal tester. |
| **Code Converter** | Paste any trading logic (Python, MQL4/5, JS, C#, plain English) → get working PineScript v5 with webhook `alert()` calls. |
| **AI Chat** | GPT-4 / Groq-powered assistant for strategy development, PineScript help, and risk management. |
| **Settings** | Configure Phemex keys, testnet mode, trading defaults, webhook secret, and LLM provider. |

### Key capabilities
- 📡 **Webhook listener** — receives TradingView alerts (JSON or plain-text) and places market / limit orders with optional SL/TP
- 🔐 **HMAC-SHA256 authentication** for Phemex API
- 🗄️ **SQLite signal log** — full history with P&L tracking
- 📊 **Chart.js analytics** — 14-day activity bar chart + status doughnut
- 📱 **Responsive UI** — mobile sidebar drawer, dark theme
- 🤖 **Multi-LLM support** — OpenAI (GPT-4o) or Groq (llama-3.3-70b, free)

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/TheBrimberry/DarkGPT.git
cd DarkGPT
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
PHEMEX_API_KEY=your-api-key
PHEMEX_API_SECRET=your-api-secret
PHEMEX_TESTNET=true          # set false for live trading
OPENAI_API_KEY=sk-...        # or use Groq (free)
GROQ_API_KEY=gsk_...
LLM_PROVIDER=openai          # openai | groq
```

> **Tip:** Start with `PHEMEX_TESTNET=true` and a testnet account at [testnet.phemex.com](https://testnet.phemex.com) to practice safely.

### 3. Run

```bash
python server.py
```

Open **http://localhost:5000** in your browser.

---

## 🐳 Docker

```bash
docker build -t darkgpt .
docker run -p 5000:5000 --env-file .env darkgpt
```

---

## 📡 TradingView Webhook Setup

### Step 1 — Expose your server

Use [ngrok](https://ngrok.com) or a VPS to get a public HTTPS URL:

```bash
ngrok http 5000
```

### Step 2 — Create a TradingView alert

1. Open your chart → click **Add Alert**
2. Set your condition
3. **Webhook URL**: `https://your-ngrok-url.ngrok.io/webhook`
4. **Message** (paste and customise):

```json
{
  "action": "buy",
  "symbol": "{{ticker}}",
  "qty": "{{strategy.order.contracts}}",
  "price": "{{close}}",
  "type": "market",
  "sl": 0,
  "tp": 0,
  "leverage": 10
}
```

### Supported actions

| `action` value | Effect |
|----------------|--------|
| `buy` / `long` | Open / add long position |
| `sell` / `short` | Open / add short position |
| `close` | Close position (reduce-only) |

### Webhook payload reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | **required** | `buy`, `sell`, or `close` |
| `symbol` | string | settings default | e.g. `BTCUSDT` |
| `qty` | float | settings default | Order quantity |
| `type` | string | `market` | `market` or `limit` |
| `price` | float | — | Required for limit orders |
| `sl` | float | — | Stop-loss price |
| `tp` | float | — | Take-profit price |
| `leverage` | int | settings default | 1–100 |
| `secret` | string | — | Must match `WEBHOOK_SECRET` if set |

### Webhook authentication (optional)

Set `WEBHOOK_SECRET` in `.env` or Settings. Then include either:
- `"secret": "your-token"` in the JSON payload, **or**
- `X-Webhook-Secret: your-token` request header

---

## 🤖 AI Assistant

The **AI Chat** tab supports:
- Developing and back-testing trading strategies
- Writing and debugging PineScript v5
- Explaining Phemex-specific behaviour
- Risk management (position sizing, SL/TP calculations)

Switch between **OpenAI** (GPT-4o) and **Groq** (llama-3.3-70b-versatile, free tier) in Settings.

---

## 🔄 Code Converter

Supported input formats:
- Python (pandas, ta-lib, vectorbt)
- MQL4 / MQL5 Expert Advisors
- JavaScript / TypeScript trading bots
- C# (cAlgo, QuantConnect)
- Plain English strategy descriptions

Output is always valid **PineScript v5** with `strategy.entry()`, `strategy.exit()`, and webhook-compatible `alert_message` parameters pre-filled.

---

## 🗂 Project Structure

```
DarkGPT/
├── server.py            # Flask application, all API routes
├── phemex_client.py     # Phemex REST API client (HMAC auth)
├── signal_manager.py    # SQLite signal/chat/conversion storage
├── requirements.txt
├── .env.example
├── Dockerfile
├── templates/
│   └── index.html       # Single-page application shell
├── static/
│   ├── css/style.css    # Dark theme styles
│   └── js/app.js        # Frontend logic (charts, polling, forms)
└── backend/             # Legacy DarkGPT RAG backend (not used by server.py)
```

---

## ⚙️ Configuration reference

All settings can be changed in-app (**Settings** tab) or via `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PHEMEX_API_KEY` | — | Phemex API key |
| `PHEMEX_API_SECRET` | — | Phemex API secret |
| `PHEMEX_TESTNET` | `true` | Use testnet endpoint |
| `DEFAULT_SYMBOL` | `BTCUSDT` | Fallback symbol |
| `DEFAULT_QTY` | `0.001` | Fallback quantity |
| `DEFAULT_LEVERAGE` | `10` | Fallback leverage |
| `WEBHOOK_SECRET` | — | Optional auth token |
| `LLM_PROVIDER` | `openai` | `openai` or `groq` |
| `OPENAI_API_KEY` | — | OpenAI key |
| `OPENAI_MODEL` | `gpt-4o` | Model name |
| `GROQ_API_KEY` | — | Groq key |
| `PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `true` | Debug mode |

---

## 🔒 Security notes

- Never commit `.env` — it is in `.gitignore`
- Use a strong random `WEBHOOK_SECRET` in production
- Use **testnet** until you have verified your strategy
- Phemex API keys should have **trade-only** permissions (no withdrawal)

---

## 📄 License

[MIT](LICENSE)
