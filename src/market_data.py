import requests


class BinanceMarketData:
    def __init__(self, base_url: str = "https://data-api.binance.vision"):
        primary = base_url.rstrip("/")

        self.base_urls = [
            primary,
            "https://data-api.binance.vision",
            "https://api1.binance.com",
            "https://api2.binance.com",
            "https://api3.binance.com",
            "https://api4.binance.com",
            "https://api.binance.com",
        ]

        # remove duplicadas mantendo ordem
        seen = set()
        self.base_urls = [url for url in self.base_urls if not (url in seen or seen.add(url))]

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })

    def _request(self, endpoint: str, params: dict):
        last_error = None

        for base_url in self.base_urls:
            url = f"{base_url}{endpoint}"

            try:
                response = self.session.get(url, params=params, timeout=20)

                if response.status_code == 451:
                    last_error = Exception(f"451 bloqueado em {base_url}")
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                last_error = e
                continue

        raise RuntimeError(
            f"Não foi possível acessar os endpoints da Binance. Último erro: {last_error}"
        )

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 200):
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        raw = self._request("/api/v3/klines", params)
        candles = []

        for item in raw:
            candles.append({
                "open_time": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "close_time": int(item[6]),
            })

        return candles

    def get_last_price(self, symbol: str):
        params = {"symbol": symbol.upper()}
        data = self._request("/api/v3/ticker/price", params)
        return float(data["price"])