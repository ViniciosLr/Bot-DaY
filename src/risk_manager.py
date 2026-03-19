from datetime import datetime


class RiskManager:
    def __init__(
        self,
        risk_per_trade: float = 0.005,
        max_daily_loss: float = 0.02,
        max_open_trades: int = 1,
        cooldown_seconds: int = 60,
        max_daily_wins: int = 5,
        max_daily_losses: int = 3,
    ):
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_open_trades = max_open_trades
        self.cooldown_seconds = cooldown_seconds
        self.max_daily_wins = max_daily_wins
        self.max_daily_losses = max_daily_losses
        self.last_trade_time = None

    def reset_day_if_needed(self, state: dict) -> dict:
        today = datetime.utcnow().date().isoformat()
        last_reset = state.get("last_reset", "")[:10]

        if last_reset != today:
            state["daily_loss"] = 0.0
            state["daily_profit"] = 0.0
            state["wins"] = 0
            state["losses"] = 0
            state["last_reset"] = datetime.utcnow().isoformat()

        return state

    def can_open_trade(self, state: dict, open_trades_count: int):
        state = self.reset_day_if_needed(state)

        balance = float(state["balance"])
        daily_loss = float(state["daily_loss"])
        wins = int(state.get("wins", 0))
        losses = int(state.get("losses", 0))

        if open_trades_count >= self.max_open_trades:
            return False, "Quantidade máxima de trades abertos atingida"

        if daily_loss >= balance * self.max_daily_loss:
            return False, "Limite de perda diária atingido"

        if wins >= self.max_daily_wins:
            return False, f"Limite diário de wins atingido ({wins}/{self.max_daily_wins})"

        if losses >= self.max_daily_losses:
            return False, f"Limite diário de losses atingido ({losses}/{self.max_daily_losses})"

        if self.last_trade_time is not None:
            elapsed = (datetime.utcnow() - self.last_trade_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False, f"Cooldown ativo ({int(self.cooldown_seconds - elapsed)}s restantes)"

        return True, "Permitido operar"

    def register_trade_open(self):
        self.last_trade_time = datetime.utcnow()

    def calculate_position_size(self, balance: float, entry_price: float, stop_loss_price: float):
        risk_amount = balance * self.risk_per_trade
        stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance <= 0:
            return 0.0

        quantity = risk_amount / stop_distance
        return round(quantity, 6)

    def calculate_sl_tp_from_atr(
        self,
        entry_price: float,
        atr_value: float,
        risk_reward: float = 2.0,
        atr_multiplier: float = 1.2,
    ):
        stop_distance = atr_value * atr_multiplier
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + (stop_distance * risk_reward)

        return round(stop_loss, 6), round(take_profit, 6)