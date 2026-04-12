"""
TradingView -> Phemex Webhook Trading Server
Main Flask application with:
  - /webhook          : Receives TradingView alerts, executes trades on Phemex
  - /api/chat         : AI-powered chat for trading strategy assistance
  - /api/convert      : Converts any code into PineScript v5 strategy
  - /api/signals      : Signal history
  - /api/settings     : Read/save settings
  - /api/test-connection : Test Phemex API connectivity
"""

import json
import os
import traceback
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from openai import OpenAI

from phemex_client import PhemexClient
from signal_manager import SignalManager

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
signals = SignalManager()


# ── Settings Management ──────────────────────────────────────────────

def default_settings() -> dict:
    return {
        "phemex_api_key": os.getenv("PHEMEX_API_KEY", ""),
        "phemex_api_secret": os.getenv("PHEMEX_API_SECRET", ""),
        "phemex_testnet": os.getenv("PHEMEX_TESTNET", "true").lower() == "true",
        "webhook_secret": os.getenv("WEBHOOK_SECRET", ""),
        "default_symbol": os.getenv("DEFAULT_SYMBOL", "BTCUSDT"),
        "default_qty": float(os.getenv("DEFAULT_QTY", "0.001")),
        "default_leverage": int(os.getenv("DEFAULT_LEVERAGE", "10")),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
    }


def load_settings() -> dict:
    settings = default_settings()
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
            settings.update(saved)
    return settings


def save_settings(data: dict):
    settings = load_settings()
    settings.update(data)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def get_phemex_client() -> PhemexClient:
    s = load_settings()
    return PhemexClient(
        api_key=s["phemex_api_key"],
        api_secret=s["phemex_api_secret"],
        testnet=s["phemex_testnet"],
    )


def get_llm_client():
    s = load_settings()
    provider = s.get("llm_provider", "openai")
    if provider == "groq" and s.get("groq_api_key"):
        return OpenAI(
            api_key=s["groq_api_key"],
            base_url="https://api.groq.com/openai/v1",
        ), s.get("openai_model", "llama-3.3-70b-versatile")
    elif s.get("openai_api_key"):
        return OpenAI(api_key=s["openai_api_key"]), s.get("openai_model", "gpt-4o")
    return None, None


# ── Webhook Authentication ───────────────────────────────────────────

def verify_webhook(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        s = load_settings()
        secret = s.get("webhook_secret", "")
        if secret:
            token = request.headers.get("X-Webhook-Secret", "")
            payload_secret = None
            if request.is_json:
                payload_secret = request.json.get("secret", "")
            if token != secret and payload_secret != secret:
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Webhook Endpoint ─────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
@verify_webhook
def webhook():
    """
    Receives TradingView webhook alerts and executes trades on Phemex.

    Expected JSON payload:
    {
        "action": "buy" | "sell" | "close",
        "symbol": "BTCUSDT",        (optional, uses default)
        "type": "market" | "limit",  (optional, default: market)
        "qty": 0.001,               (optional, uses default)
        "price": 50000,             (optional, required for limit)
        "sl": 49000,                (optional, stop loss)
        "tp": 52000,                (optional, take profit)
        "leverage": 10,             (optional)
        "secret": "your-secret"     (optional, for auth)
    }
    """
    try:
        if request.content_type and "json" in request.content_type:
            payload = request.json
        else:
            raw = request.data.decode("utf-8").strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = parse_plaintext_alert(raw)

        if not payload or "action" not in payload:
            return jsonify({"error": "Missing 'action' in payload"}), 400

        s = load_settings()
        payload.setdefault("symbol", s["default_symbol"])
        payload.setdefault("qty", s["default_qty"])
        payload.setdefault("type", "market")

        signal_id = signals.record_signal(payload)

        client = get_phemex_client()
        action = payload["action"].lower()
        symbol = payload["symbol"].upper()
        qty = float(payload["qty"])
        order_type = payload.get("type", "market")
        price = float(payload["price"]) if payload.get("price") else None
        sl = float(payload["sl"]) if payload.get("sl") else None
        tp = float(payload["tp"]) if payload.get("tp") else None
        leverage = int(payload["leverage"]) if payload.get("leverage") else s.get("default_leverage")

        if action in ("buy", "long"):
            result = client.place_order(
                symbol=symbol, side="Buy", order_type=order_type,
                qty=qty, price=price, stop_loss=sl, take_profit=tp,
                leverage=leverage,
            )
        elif action in ("sell", "short"):
            result = client.place_order(
                symbol=symbol, side="Sell", order_type=order_type,
                qty=qty, price=price, stop_loss=sl, take_profit=tp,
                leverage=leverage,
            )
        elif action == "close":
            side = payload.get("side", "buy")
            result = client.close_position(symbol, side, qty)
        else:
            signals.update_signal(signal_id, "failed", error=f"Unknown action: {action}")
            return jsonify({"error": f"Unknown action: {action}"}), 400

        if result.get("code") == 0:
            signals.update_signal(signal_id, "executed", exchange_response=json.dumps(result))
            return jsonify({"status": "executed", "signal_id": signal_id, "result": result})
        else:
            err_msg = result.get("msg", json.dumps(result))
            signals.update_signal(signal_id, "failed", exchange_response=json.dumps(result), error=err_msg)
            return jsonify({"status": "failed", "signal_id": signal_id, "error": err_msg}), 400

    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error(f"Webhook error: {tb}")
        return jsonify({"error": str(e), "traceback": tb}), 500


def parse_plaintext_alert(text: str) -> dict:
    """Parse a simple plaintext TradingView alert like 'buy BTCUSDT 0.001'."""
    parts = text.strip().split()
    payload = {}
    if len(parts) >= 1:
        payload["action"] = parts[0].lower()
    if len(parts) >= 2:
        payload["symbol"] = parts[1].upper()
    if len(parts) >= 3:
        try:
            payload["qty"] = float(parts[2])
        except ValueError:
            pass
    return payload


# ── AI Chat Endpoint ─────────────────────────────────────────────────

SYSTEM_PROMPT_CHAT = """You are a professional crypto trading assistant integrated into a TradingView-to-Phemex webhook trading system. You help with:

1. **Trading Strategy** - Developing, analyzing, and optimizing trading strategies
2. **PineScript** - Writing, debugging, and explaining TradingView PineScript code
3. **Webhook Setup** - Configuring TradingView alerts to work with this webhook system
4. **Phemex Trading** - Exchange-specific questions about Phemex perpetual contracts
5. **Risk Management** - Position sizing, stop losses, take profits, leverage

When helping with webhook JSON, use this format:
{
    "action": "buy",
    "symbol": "BTCUSDT",
    "qty": 0.001,
    "type": "market",
    "sl": 0,
    "tp": 0,
    "leverage": 10
}

When writing PineScript, always use v5 syntax and include alertcondition() or alert() calls for webhook integration. Be precise, concise, and actionable."""


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    signals.save_chat_message("user", user_message)

    client, model = get_llm_client()
    if client is None:
        return jsonify({"error": "No LLM API key configured. Add your OpenAI or Groq API key in Settings."}), 400

    history = signals.get_chat_history(limit=20)
    messages = [{"role": "system", "content": SYSTEM_PROMPT_CHAT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        signals.save_chat_message("assistant", reply)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Code-to-PineScript Converter ────────────────────────────────────

SYSTEM_PROMPT_CONVERTER = """You are an expert PineScript v5 code converter. Your job is to take ANY trading strategy code (Python, JavaScript, MQL4/5, C#, pseudocode, plain English description, or any other language) and convert it into a fully working TradingView PineScript v5 strategy.

RULES:
1. ALWAYS output valid PineScript v5 code (starts with //@version=5 and strategy())
2. Include proper strategy() declaration with overlay=true
3. Convert all trading logic faithfully - preserve the exact entry/exit conditions
4. Add strategy.entry() and strategy.exit() calls
5. Add alert_message parameters in strategy calls for webhook JSON integration
6. Use proper PineScript v5 syntax (var, :=, ta.*, math.*, etc.)
7. Add clear comments explaining each section
8. Include webhook-compatible alert messages in this JSON format:
   {"action": "buy", "symbol": "{{ticker}}", "qty": "{{strategy.order.contracts}}", "price": "{{close}}", "type": "market"}
9. Handle edge cases and add input() parameters for configurability
10. If the input is a description in plain English, create a complete strategy from it
11. NEVER output anything other than the PineScript code - no explanations before or after
12. The code must compile without errors on TradingView

OUTPUT FORMAT: Only the PineScript v5 code, nothing else."""


@app.route("/api/convert", methods=["POST"])
def convert():
    data = request.json
    input_code = data.get("code", "").strip()
    language = data.get("language", "auto")

    if not input_code:
        return jsonify({"error": "No code provided"}), 400

    client, model = get_llm_client()
    if client is None:
        return jsonify({"error": "No LLM API key configured. Add your OpenAI or Groq API key in Settings."}), 400

    prompt = f"Convert the following {language} code/strategy into a PineScript v5 strategy:\n\n```\n{input_code}\n```"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_CONVERTER},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8192,
            temperature=0.3,
        )
        pinescript = response.choices[0].message.content

        # Strip markdown code fences if present
        if pinescript.startswith("```"):
            lines = pinescript.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            pinescript = "\n".join(lines)

        signals.save_conversion(input_code, language, pinescript)
        return jsonify({"pinescript": pinescript})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Signal History ───────────────────────────────────────────────────

@app.route("/api/signals", methods=["GET"])
def get_signals():
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    return jsonify({
        "signals": signals.get_signals(limit, offset),
        "stats": signals.get_stats(),
    })


@app.route("/api/signals/clear", methods=["POST"])
def clear_signals():
    signals.clear_signals()
    return jsonify({"status": "cleared"})


# ── Settings Endpoints ───────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    s = load_settings()
    # Mask secrets for display
    safe = dict(s)
    for key in ("phemex_api_secret", "openai_api_key", "groq_api_key"):
        if safe.get(key):
            safe[key] = safe[key][:4] + "****" + safe[key][-4:] if len(safe[key]) > 8 else "****"
    return jsonify(safe)


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json
    # Don't overwrite secrets with masked values
    current = load_settings()
    for key in ("phemex_api_secret", "openai_api_key", "groq_api_key"):
        if data.get(key, "").endswith("****"):
            data[key] = current[key]
    save_settings(data)
    return jsonify({"status": "saved"})


# ── Phemex Endpoints ────────────────────────────────────────────────

@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    try:
        client = get_phemex_client()
        result = client.test_connection()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/positions", methods=["GET"])
def get_positions():
    try:
        client = get_phemex_client()
        positions = client.get_positions()
        balance = client.get_balance()
        return jsonify({"positions": positions, "balance": balance})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/clear", methods=["POST"])
def clear_chat():
    signals.clear_chat_history()
    return jsonify({"status": "cleared"})


# ── Webhook URL Helper ──────────────────────────────────────────────

@app.route("/api/webhook-info", methods=["GET"])
def webhook_info():
    host = request.host_url.rstrip("/")
    s = load_settings()
    example_payload = {
        "action": "buy",
        "symbol": s.get("default_symbol", "BTCUSDT"),
        "qty": s.get("default_qty", 0.001),
        "type": "market",
        "sl": 0,
        "tp": 0,
        "leverage": s.get("default_leverage", 10),
    }
    if s.get("webhook_secret"):
        example_payload["secret"] = "your-webhook-secret"

    return jsonify({
        "webhook_url": f"{host}/webhook",
        "method": "POST",
        "content_type": "application/json",
        "example_payload": example_payload,
    })


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
