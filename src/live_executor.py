import math
from executor import Executor
from binance_client import BinanceClient


class LiveExecutor(Executor):
    def __init__(self, database, logger, client: BinanceClient):
        super().__init__(database, logger)
        self.client = client

    def _get_symbol_filters(self, symbol: str):
        info = self.client.get_symbol_info(symbol)

        lot_size = None
        min_notional = None

        for f in info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                lot_size = f
            elif f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"):
                min_notional = f

        if not lot_size:
            raise RuntimeError(f"Filtro LOT_SIZE não encontrado para {symbol}")

        return {
            "base_asset": info["baseAsset"],
            "quote_asset": info["quoteAsset"],
            "step_size": float(lot_size["stepSize"]),
            "min_qty": float(lot_size["minQty"]),
            "max_qty": float(lot_size["maxQty"]),
            "min_notional": float(min_notional.get("minNotional", 0)) if min_notional else 0.0,
        }

    def _floor_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def _prepare_quantity(self, symbol: str, quantity: float, entry_price: float) -> float:
        filters = self._get_symbol_filters(symbol)

        adjusted_qty = self._floor_to_step(quantity, filters["step_size"])

        if adjusted_qty < filters["min_qty"]:
            raise RuntimeError(
                f"Quantidade {adjusted_qty} menor que minQty {filters['min_qty']} para {symbol}"
            )

        if adjusted_qty > filters["max_qty"]:
            raise RuntimeError(
                f"Quantidade {adjusted_qty} maior que maxQty {filters['max_qty']} para {symbol}"
            )

        notional = adjusted_qty * entry_price
        if filters["min_notional"] > 0 and notional < filters["min_notional"]:
            raise RuntimeError(
                f"Valor da ordem {notional:.8f} menor que minNotional {filters['min_notional']}"
            )

        return adjusted_qty

    def open_trade(
        self,
        symbol,
        side,
        quantity,
        entry_price,
        stop_loss,
        take_profit,
        strategy_name,
    ):
        side = side.lower()
        if side not in ("buy", "sell"):
            raise RuntimeError(f"Lado inválido para trade: {side}")

        adjusted_qty = self._prepare_quantity(symbol, quantity, entry_price)
        order_side = "BUY" if side == "buy" else "SELL"

        self.logger.info(
            f"Enviando ordem real | symbol={symbol} | side={order_side} | qty={adjusted_qty}"
        )

        order = self.client.create_market_order(
            symbol=symbol,
            side=order_side,
            quantity=adjusted_qty,
        )

        fills = order.get("fills", [])
        if fills:
            total_qty = 0.0
            total_cost = 0.0
            for fill in fills:
                fill_price = float(fill["price"])
                fill_qty = float(fill["qty"])
                total_qty += fill_qty
                total_cost += fill_price * fill_qty
            executed_price = total_cost / total_qty if total_qty > 0 else entry_price
        else:
            executed_qty = float(order.get("executedQty", 0))
            cummulative_quote_qty = float(order.get("cummulativeQuoteQty", 0))
            executed_price = (
                cummulative_quote_qty / executed_qty
                if executed_qty > 0 else entry_price
            )

        trade_id = self.db.create_trade(
            symbol=symbol,
            side=side,
            entry_price=executed_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=adjusted_qty,
            strategy=strategy_name,
        )

        self.logger.warning(
            f"ORDEM REAL ENVIADA | ID={trade_id} | {symbol} | {side.upper()} | "
            f"qty={adjusted_qty} | preço={executed_price:.8f}"
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
            symbol = trade["symbol"]
            side = str(trade["side"]).lower()
            entry_price = float(trade["entry_price"])
            stop_loss = float(trade["stop_loss"])
            take_profit = float(trade["take_profit"])
            quantity = float(trade["quantity"])

            should_close = False
            exit_price = current_price
            result = 0.0
            close_side = None

            if side == "buy":
                if current_price <= stop_loss:
                    should_close = True
                    exit_price = stop_loss
                elif current_price >= take_profit:
                    should_close = True
                    exit_price = take_profit

                if should_close:
                    close_side = "SELL"
                    result = (exit_price - entry_price) * quantity

            elif side == "sell":
                if current_price >= stop_loss:
                    should_close = True
                    exit_price = stop_loss
                elif current_price <= take_profit:
                    should_close = True
                    exit_price = take_profit

                if should_close:
                    close_side = "BUY"
                    result = (entry_price - exit_price) * quantity

            else:
                self.logger.warning(
                    f"Trade com side inválido encontrado | ID={trade_id} | side={trade['side']}"
                )
                continue

            if should_close:
                adjusted_qty = self._prepare_quantity(symbol, quantity, current_price)

                self.logger.info(
                    f"Fechando trade real | ID={trade_id} | symbol={symbol} | "
                    f"side={close_side} | qty={adjusted_qty}"
                )

                self.client.create_market_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=adjusted_qty,
                )

                self.db.close_trade(trade_id, exit_price, result)
                balance += result
                closed_any_trade = True

                if result >= 0:
                    daily_profit += result
                    wins += 1
                else:
                    daily_loss += abs(result)
                    losses += 1

                self.logger.warning(
                    f"TRADE REAL FECHADO | ID={trade_id} | {side.upper()} | "
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