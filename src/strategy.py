from typing import List, Dict, Any


class Strategy:
    def __init__(
        self,
        fast_ema_period: int = 9,
        slow_ema_period: int = 21,
        rsi_period: int = 14,
        atr_period: int = 14,
    ):
        self.fast = fast_ema_period
        self.slow = slow_ema_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period

    def ema(self, values: List[float], period: int) -> float | None:
        if len(values) < period:
            return None

        alpha = 2 / (period + 1)

        # Inicializa com SMA dos últimos candles do período
        ema_val = sum(values[:period]) / period

        for price in values[period:]:
            ema_val = alpha * price + (1 - alpha) * ema_val

        return ema_val

    def rsi(self, closes: List[float], period: int = 14) -> float | None:
        if len(closes) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(len(closes) - period, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> float | None:
        if len(closes) < period + 1:
            return None

        trs = []
        for i in range(len(closes) - period, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        return sum(trs) / period

    def generate_signal(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        min_required = max(self.slow, self.rsi_period, self.atr_period) + 5

        if len(candles) < min_required:
            return {
                "signal": "hold",
                "reason": f"Dados insuficientes ({len(candles)} < {min_required})",
                "price": None,
                "atr": None,
            }

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]

        fast_ema = self.ema(closes, self.fast)
        slow_ema = self.ema(closes, self.slow)
        rsi_val = self.rsi(closes, self.rsi_period)
        atr_val = self.atr(highs, lows, closes, self.atr_period)

        if any(x is None for x in [fast_ema, slow_ema, rsi_val, atr_val]):
            return {
                "signal": "hold",
                "reason": "Indicadores não calculados ainda",
                "price": closes[-1],
                "atr": atr_val,
            }

        current_price = closes[-1]
        prev_close = closes[-2]

        atr_filter = atr_val > 0.0005 * current_price
        bullish_trend = fast_ema > slow_ema
        bullish_momentum = current_price > fast_ema and current_price > prev_close
        rsi_ok = 50 < rsi_val < 68

        if bullish_trend and bullish_momentum and rsi_ok and atr_filter:
            return {
                "signal": "buy",
                "reason": (
                    f"BUY | EMA {fast_ema:.2f} > {slow_ema:.2f} | "
                    f"Preço {current_price:.2f} > EMA rápida | "
                    f"RSI {rsi_val:.1f} | ATR ok"
                ),
                "price": current_price,
                "atr": atr_val,
            }

        # Fecha long apenas quando a estrutura enfraquece bem
        # Mantive sua lógica base, mas um pouco mais clara
        should_close_long = (
            fast_ema < slow_ema
            or rsi_val < 35
            or rsi_val > 75
        )

        if should_close_long:
            return {
                "signal": "close_long",
                "reason": (
                    f"Fechar LONG | EMA {fast_ema:.2f} < {slow_ema:.2f} "
                    f"ou RSI {rsi_val:.1f}"
                ),
                "price": current_price,
                "atr": atr_val,
            }

        return {
            "signal": "hold",
            "reason": (
                f"HOLD | EMA {fast_ema:.2f} vs {slow_ema:.2f} | "
                f"RSI {rsi_val:.1f} | ATR {atr_val:.2f}"
            ),
            "price": current_price,
            "atr": atr_val,
        }