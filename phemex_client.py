"""
Phemex Exchange API Client
Handles authentication, order placement, position management, and account queries.
Supports both mainnet and testnet.
"""

import hashlib
import hmac
import json
import time
import requests
from urllib.parse import urlencode


class PhemexClient:
    MAINNET_URL = "https://api.phemex.com"
    TESTNET_URL = "https://testnet-api.phemex.com"

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = self.TESTNET_URL if testnet else self.MAINNET_URL
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _get_expiry(self) -> str:
        return str(int(time.time()) + 60)

    def _sign(self, url_path: str, query_string: str, expiry: str, body: str = "") -> str:
        message = url_path + query_string + expiry + body
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _auth_headers(self, url_path: str, query_string: str = "", body: str = "") -> dict:
        expiry = self._get_expiry()
        signature = self._sign(url_path, query_string, expiry, body)
        return {
            "x-phemex-access-token": self.api_key,
            "x-phemex-request-expiry": expiry,
            "x-phemex-request-signature": signature,
        }

    def _get(self, path: str, params: dict = None) -> dict:
        query_string = ""
        if params:
            query_string = urlencode(params)
        headers = self._auth_headers(path, query_string)
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"
        resp = self.session.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        body = json.dumps(data, separators=(",", ":"))
        headers = self._auth_headers(path, body=body)
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, headers=headers, data=body, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str, params: dict = None) -> dict:
        query_string = ""
        if params:
            query_string = urlencode(params)
        headers = self._auth_headers(path, query_string)
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"
        resp = self.session.delete(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Account & Positions ──────────────────────────────────────────

    def get_account_positions(self, currency: str = "USDT") -> dict:
        return self._get("/g-accounts/accountPositions", {"currency": currency})

    def get_balance(self, currency: str = "USDT") -> dict:
        result = self.get_account_positions(currency)
        if result.get("code") == 0:
            account = result.get("data", {}).get("account", {})
            return {
                "currency": currency,
                "accountBalanceRv": account.get("accountBalanceRv", "0"),
                "totalUsedBalanceRv": account.get("totalUsedBalanceRv", "0"),
                "availBalanceRv": account.get("availBalanceRv", "0"),
                "totalPnlRv": account.get("totalPnlRv", "0"),
            }
        return {"error": result.get("msg", "Unknown error")}

    def get_positions(self, currency: str = "USDT") -> list:
        result = self.get_account_positions(currency)
        if result.get("code") == 0:
            positions = result.get("data", {}).get("positions", [])
            return [p for p in positions if float(p.get("size", 0)) != 0]
        return []

    # ── Order Placement ──────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "Market",
        qty: float = 0,
        price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        leverage: int = None,
        reduce_only: bool = False,
        pos_side: str = None,
        time_in_force: str = "GoodTillCancel",
        text: str = "tv-webhook",
    ) -> dict:
        side = side.capitalize()
        if side not in ("Buy", "Sell"):
            return {"error": f"Invalid side: {side}. Must be 'Buy' or 'Sell'."}

        order_type_map = {
            "market": "Market",
            "limit": "Limit",
            "stop": "Stop",
            "stoplimit": "StopLimit",
            "marketiftouched": "MarketIfTouched",
            "limitiftouched": "LimitIfTouched",
        }
        order_type = order_type_map.get(order_type.lower(), order_type)

        if leverage is not None and self.api_key:
            try:
                self.set_leverage(symbol, leverage)
            except Exception:
                pass  # Non-critical: proceed with order even if leverage set fails

        body = {
            "symbol": symbol.upper(),
            "side": side,
            "orderType": order_type,
            "orderQty": str(qty),
            "timeInForce": time_in_force,
            "text": text,
        }

        if pos_side:
            body["posSide"] = pos_side.capitalize()

        if reduce_only:
            body["reduceOnly"] = True

        if price is not None and order_type != "Market":
            body["priceRp"] = str(price)

        if stop_loss is not None:
            body["stopLossRp"] = str(stop_loss)

        if take_profit is not None:
            body["takeProfitRp"] = str(take_profit)

        return self._post("/g-orders/create", body)

    def place_market_buy(self, symbol: str, qty: float, **kwargs) -> dict:
        return self.place_order(symbol, "Buy", "Market", qty, **kwargs)

    def place_market_sell(self, symbol: str, qty: float, **kwargs) -> dict:
        return self.place_order(symbol, "Sell", "Market", qty, **kwargs)

    def place_limit_buy(self, symbol: str, qty: float, price: float, **kwargs) -> dict:
        return self.place_order(symbol, "Buy", "Limit", qty, price=price, **kwargs)

    def place_limit_sell(self, symbol: str, qty: float, price: float, **kwargs) -> dict:
        return self.place_order(symbol, "Sell", "Limit", qty, price=price, **kwargs)

    def close_position(self, symbol: str, side: str, qty: float) -> dict:
        close_side = "Sell" if side.lower() == "buy" else "Buy"
        return self.place_order(symbol, close_side, "Market", qty, reduce_only=True)

    # ── Order Management ─────────────────────────────────────────────

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        return self._delete("/g-orders/cancel", {"symbol": symbol, "orderID": order_id})

    def cancel_all_orders(self, symbol: str) -> dict:
        return self._delete("/g-orders/all", {"symbol": symbol})

    def get_open_orders(self, symbol: str) -> dict:
        return self._get("/g-orders/activeList", {"symbol": symbol})

    # ── Leverage ─────────────────────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        return self._post("/g-positions/leverage", {
            "symbol": symbol.upper(),
            "leverageRr": str(leverage),
        })

    # ── Market Data (public, no auth needed) ─────────────────────────

    def get_ticker(self, symbol: str) -> dict:
        url = f"{self.base_url}/md/v2/ticker/24hr"
        resp = self.session.get(url, params={"symbol": symbol.upper()}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_orderbook(self, symbol: str) -> dict:
        url = f"{self.base_url}/md/v2/orderbook"
        resp = self.session.get(url, params={"symbol": symbol.upper()}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Validation & Helpers ─────────────────────────────────────────

    def test_connection(self) -> dict:
        try:
            balance = self.get_balance()
            if "error" not in balance:
                return {"status": "connected", "balance": balance}
            return {"status": "error", "message": balance["error"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
