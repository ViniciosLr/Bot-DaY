from collections import deque


class Strategy:
    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 15,
        min_strength: float = 0.02
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.min_strength = min_strength

        # Guarda últimos preços
        self.prices = deque(maxlen=long_window)

    def add_price(self, price: float):
        self.prices.append(price)

    def sma(self, data, period):
        if len(data) < period:
            return None
        return sum(list(data)[-period:]) / period

    def get_signal(self):
        if len(self.prices) < self.long_window:
            return {
                "signal": "hold",
                "reason": "Poucos dados ainda"
            }

        short_sma = self.sma(self.prices, self.short_window)
        long_sma = self.sma(self.prices, self.long_window)

        last_price = self.prices[-1]

        # força da tendência (%)
        strength = abs(short_sma - long_sma) / last_price

        if strength < self.min_strength:
            return {
                "signal": "hold",
                "reason": f"Tendência fraca ({strength:.5f})"
            }

        if short_sma > long_sma:
            return {
                "signal": "buy",
                "reason": f"Alta | SMA curta {short_sma:.5f} > longa {long_sma:.5f} | força {strength:.5f}",
                "price": last_price
            }

        if short_sma < long_sma:
            return {
                "signal": "sell",
                "reason": f"Baixa | SMA curta {short_sma:.5f} < longa {long_sma:.5f} | força {strength:.5f}",
                "price": last_price
            }

        return {
            "signal": "hold",
            "reason": "Sem direção clara"
        }