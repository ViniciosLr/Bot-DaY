class Executor:
    def __init__(self, database, logger):
        self.db = database
        self.logger = logger

    def open_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float,
        strategy_name: str,
    ) -> int:
        trade_id = self.db.create_trade(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            strategy=strategy_name,
        )

        self.logger.info(
            f"TRADE ABERTO | ID={trade_id} | {side.upper()} | "
            f"Entrada={entry_price:.8f} | SL={stop_loss:.8f} | "
            f"TP={take_profit:.8f} | QTD={quantity:.8f}"
        )
        return trade_id

    def evaluate_open_trades(self, current_price: float):
        open_trades = self.db.get_open_trades()
        if not open_trades:
            return

        state = self.db.get_bot_state()

        balance = float(state["balance"])
        daily_loss = float(state["daily_loss"])
        daily_profit = float(state["daily_profit"])
        wins = int(state["wins"])
        losses = int(state["losses"])
        last_reset = state["last_reset"]

        closed_any_trade = False

        for trade in open_trades:
            trade_id = trade["id"]
            side = str(trade["side"]).lower()
            entry_price = float(trade["entry_price"])
            stop_loss = float(trade["stop_loss"])
            take_profit = float(trade["take_profit"])
            quantity = float(trade["quantity"])

            should_close = False
            exit_price = current_price
            result = 0.0

            if side == "buy":
                if current_price <= stop_loss:
                    should_close = True
                    exit_price = stop_loss
                elif current_price >= take_profit:
                    should_close = True
                    exit_price = take_profit

                if should_close:
                    result = (exit_price - entry_price) * quantity

            elif side == "sell":
                if current_price >= stop_loss:
                    should_close = True
                    exit_price = stop_loss
                elif current_price <= take_profit:
                    should_close = True
                    exit_price = take_profit

                if should_close:
                    result = (entry_price - exit_price) * quantity

            else:
                self.logger.warning(
                    f"Trade com side inválido encontrado | ID={trade_id} | side={trade['side']}"
                )
                continue

            if should_close:
                self.db.close_trade(trade_id, exit_price, result)
                balance += result
                closed_any_trade = True

                if result >= 0:
                    daily_profit += result
                    wins += 1
                else:
                    daily_loss += abs(result)
                    losses += 1

                self.logger.info(
                    f"TRADE FECHADO | ID={trade_id} | {side.upper()} | "
                    f"Entrada={entry_price:.8f} | Saída={exit_price:.8f} | "
                    f"Resultado={result:.2f}"
                )

        if closed_any_trade:
            self.db.update_bot_state(
                balance=balance,
                daily_loss=daily_loss,
                daily_profit=daily_profit,
                wins=wins,
                losses=losses,
                last_reset=last_reset,
            )