import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode


class BinanceClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.binance.com",
    ):
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-MBX-APIKEY": self.api_key,
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
        )

    def _sign_params(self, params: dict) -> str:
        query_string = urlencode(params, doseq=True)
        signature = hmac.new(
            self.api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _public_request(self, method: str, path: str, params: dict | None = None):
        params = params or {}
        url = f"{self.base_url}{path}"

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def _signed_request(self, method: str, path: str, params: dict | None = None):
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000

        signed_query = self._sign_params(params)
        url = f"{self.base_url}{path}?{signed_query}"

        response = self.session.request(
            method=method,
            url=url,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def ping(self):
        return self._public_request("GET", "/api/v3/ping")

    def get_server_time(self):
        return self._public_request("GET", "/api/v3/time")

    def get_exchange_info(self, symbol: str | None = None):
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._public_request("GET", "/api/v3/exchangeInfo", params)

    def get_symbol_info(self, symbol: str):
        data = self.get_exchange_info(symbol)
        symbols = data.get("symbols", [])
        if not symbols:
            raise RuntimeError(f"Símbolo não encontrado na Binance: {symbol}")
        return symbols[0]

    def get_account_info(self):
        return self._signed_request("GET", "/api/v3/account")

    def get_asset_balance(self, asset: str):
        account = self.get_account_info()

        for balance in account.get("balances", []):
            if balance["asset"] == asset.upper():
                free_amount = float(balance["free"])
                locked_amount = float(balance["locked"])

                return {
                    "asset": balance["asset"],
                    "free": free_amount,
                    "locked": locked_amount,
                    "total": free_amount + locked_amount,
                }

        return {
            "asset": asset.upper(),
            "free": 0.0,
            "locked": 0.0,
            "total": 0.0,
        }

    def get_total_asset_balance(self, asset: str) -> float:
        balance = self.get_asset_balance(asset)
        return float(balance["total"])

    def get_usdt_balance(self):
        return self.get_asset_balance("USDT")

    def get_total_usdt_balance(self) -> float:
        return self.get_total_asset_balance("USDT")

    def get_last_price(self, symbol: str):
        data = self._public_request(
            "GET",
            "/api/v3/ticker/price",
            {"symbol": symbol.upper()},
        )
        return float(data["price"])

    def create_market_order(self, symbol: str, side: str, quantity: float):
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": self._normalize_number(quantity),
        }
        return self._signed_request("POST", "/api/v3/order", params)

    def create_market_sell_all(self, symbol: str, base_asset: str):
        balance = self.get_asset_balance(base_asset)
        free_qty = float(balance["free"])

        if free_qty <= 0:
            raise RuntimeError(f"Saldo insuficiente de {base_asset} para venda.")

        return self.create_market_order(
            symbol=symbol,
            side="SELL",
            quantity=free_qty,
        )

    def _normalize_number(self, value: float) -> str:
        text = f"{value:.12f}".rstrip("0").rstrip(".")
        return text if text else "0"