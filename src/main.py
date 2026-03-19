import time

from config import (
    SYMBOL,
    INTERVAL,
    DB_PATH,
    INITIAL_BALANCE,
    RISK_PER_TRADE,
    MAX_DAILY_LOSS,
    MAX_OPEN_TRADES,
    RISK_REWARD,
    LOOP_SECONDS,
    USE_TESTNET_WORDING,
    BINANCE_BASE_URL,
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    LIVE_TRADING,
)
from database import Database
from logger import setup_logger
from market_data import BinanceMarketData
from paper_executor import PaperExecutor
from live_executor import LiveExecutor
from binance_client import BinanceClient
from risk_manager import RiskManager
from strategy import Strategy


def persist_state_if_reset(db: Database, state: dict):
    db.update_bot_state(
        balance=float(state["balance"]),
        daily_loss=float(state["daily_loss"]),
        daily_profit=float(state["daily_profit"]),
        wins=int(state["wins"]),
        losses=int(state["losses"]),
        last_reset=state["last_reset"],
    )


def sync_candles(db: Database, market: BinanceMarketData, symbol: str, interval: str):
    candles = market.get_klines(symbol=symbol, interval=interval, limit=200)

    for candle in candles:
        db.insert_candle(
            symbol=symbol,
            interval=interval,
            open_time=candle["open_time"],
            open_=candle["open"],
            high=candle["high"],
            low=candle["low"],
            close=candle["close"],
            volume=candle["volume"],
            close_time=candle["close_time"],
        )


def build_executor(db: Database, logger):
    if LIVE_TRADING:
        if not BINANCE_API_KEY or not BINANCE_API_SECRET:
            raise RuntimeError(
                "LIVE_TRADING=true, mas BINANCE_API_KEY ou BINANCE_API_SECRET não foram configurados."
            )

        client = BinanceClient(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_API_SECRET,
            base_url=BINANCE_BASE_URL,
        )

        logger.warning("MODO REAL ATIVADO")
        return LiveExecutor(database=db, logger=logger, client=client)

    logger.info("MODO PAPER ATIVADO")
    return PaperExecutor(database=db, logger=logger)


def safe_evaluate_open_trades(executor, current_price: float, logger):
    if hasattr(executor, "evaluate_open_trades"):
        executor.evaluate_open_trades(current_price=current_price)
    else:
        logger.warning(
            "Executor atual não possui evaluate_open_trades(). "
            "Fechamento automático não será executado neste modo."
        )


def get_wallet_info(executor, logger):
    wallet_info = ""

    if not LIVE_TRADING:
        return wallet_info

    if not hasattr(executor, "client"):
        return wallet_info

    try:
        usdt_balance = executor.client.get_asset_balance("USDT")
        btc_balance = executor.client.get_asset_balance("BTC")

        usdt_total = float(usdt_balance["total"])
        usdt_free = float(usdt_balance["free"])
        usdt_locked = float(usdt_balance["locked"])

        btc_total = float(btc_balance["total"])
        btc_free = float(btc_balance["free"])
        btc_locked = float(btc_balance["locked"])

        wallet_info = (
            f" | CarteiraBinance USDT={usdt_total:.2f} "
            f"(livre={usdt_free:.2f}, bloqueado={usdt_locked:.2f})"
            f" | BTC={btc_total:.8f} "
            f"(livre={btc_free:.8f}, bloqueado={btc_locked:.8f})"
        )
    except Exception as e:
        logger.warning(f"Não foi possível consultar saldo real da Binance: {e}")

    return wallet_info


def main():
    logger = setup_logger()
    db = Database(DB_PATH)

    market = BinanceMarketData(base_url=BINANCE_BASE_URL)
    strategy = Strategy()
    risk = RiskManager(
        risk_per_trade=RISK_PER_TRADE,
        max_daily_loss=MAX_DAILY_LOSS,
        max_open_trades=MAX_OPEN_TRADES,
        cooldown_seconds=60,
    )
    executor = build_executor(db, logger)

    if LIVE_TRADING:
        mode_label = "BINANCE LIVE TRADING"
    else:
        mode_label = "BINANCE PAPER DEMO" if USE_TESTNET_WORDING else "PAPER TRADING"

    logger.info(f"Iniciando {mode_label}...")
    logger.info(f"Símbolo={SYMBOL} | Intervalo={INTERVAL}")
    logger.info(f"Base URL inicial={BINANCE_BASE_URL}")

    last_processed_close_time = None

    while True:
        try:
            sync_candles(db, market, SYMBOL, INTERVAL)
            candles = db.get_recent_candles(SYMBOL, INTERVAL, limit=200)

            if not candles:
                logger.warning("Nenhum candle encontrado no banco após sincronização.")
                time.sleep(LOOP_SECONDS)
                continue

            current_candle = candles[-1]
            current_price = float(current_candle["close"])
            current_close_time = current_candle["close_time"]

            safe_evaluate_open_trades(executor, current_price, logger)

            if last_processed_close_time == current_close_time:
                time.sleep(LOOP_SECONDS)
                continue

            last_processed_close_time = current_close_time

            signal_data = strategy.generate_signal(candles)

            open_trades = db.get_open_trades()
            has_open_buy = any(trade["side"].lower() == "buy" for trade in open_trades)

            state = db.get_bot_state()

            old_last_reset = state["last_reset"]
            state = risk.reset_day_if_needed(state)

            if state["last_reset"] != old_last_reset:
                persist_state_if_reset(db, state)
                logger.info("Estado diário resetado.")

            allowed, reason = risk.can_open_trade(
                state=state,
                open_trades_count=len(open_trades),
            )

            logger.info(
                f"Preço={current_price:.2f} | "
                f"Sinal={signal_data['signal']} | "
                f"Motivo={signal_data['reason']} | "
                f"PodeAbrir={allowed} | "
                f"MotivoRisk={reason}"
            )

            if allowed and signal_data["signal"] == "buy" and not has_open_buy:
                atr_value = signal_data.get("atr")

                if atr_value is None or atr_value <= 0:
                    logger.warning("ATR inválido. Trade não aberto.")
                else:
                    entry_price = current_price

                    stop_loss, take_profit = risk.calculate_sl_tp_from_atr(
                        entry_price=entry_price,
                        atr_value=atr_value,
                        risk_reward=RISK_REWARD,
                        atr_multiplier=1.2,
                    )

                    quantity = risk.calculate_position_size(
                        balance=float(state["balance"]),
                        entry_price=entry_price,
                        stop_loss_price=stop_loss,
                    )

                    if quantity > 0:
                        strategy_name = (
                            "EMA_RSI_ATR_LONG_LIVE"
                            if LIVE_TRADING
                            else "EMA_RSI_ATR_LONG_PAPER"
                        )

                        executor.open_trade(
                            symbol=SYMBOL,
                            side="buy",
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            quantity=quantity,
                            strategy_name=strategy_name,
                        )
                        risk.register_trade_open()
                        logger.info("Trade BUY aberto com sucesso!")
                    else:
                        logger.warning("Quantidade calculada inválida. Trade não aberto.")

            elif allowed and signal_data["signal"] == "buy" and has_open_buy:
                logger.info("Sinal BUY ignorado: já existe trade BUY aberto.")

            elif signal_data["signal"] == "close_long":
                open_buy_trade = next(
                    (trade for trade in open_trades if trade["side"].lower() == "buy"),
                    None
                )

                if open_buy_trade:
                    logger.info(
                        f"Sinal de fechamento detectado para BUY aberto | "
                        f"TradeID={open_buy_trade['id']} | "
                        f"Fechamento será tratado pelo executor/gestão."
                    )

            else:
                logger.info(f"Sem abertura de trade | {reason}")

            state_now = db.get_bot_state()
            summary = db.get_performance_summary()
            wallet_info = get_wallet_info(executor, logger)

            logger.info(
                f"SaldoBot={state_now['balance']:.2f} | "
                f"Profit dia={state_now['daily_profit']:.2f} | "
                f"Loss dia={state_now['daily_loss']:.2f} | "
                f"Wins={state_now['wins']} | "
                f"Losses={state_now['losses']}"
                f"{wallet_info}"
            )

            logger.info(
                f"Resumo | Trades={summary['total_trades']} | "
                f"WinRate={summary['win_rate']:.1f}% | "
                f"Net={summary['net_result']:.2f} | "
                f"PF={summary['profit_factor']:.2f} | "
                f"SeqWinMax={summary['max_win_streak']} | "
                f"SeqLossMax={summary['max_loss_streak']}"
            )

            time.sleep(LOOP_SECONDS)

        except KeyboardInterrupt:
            logger.info("Bot encerrado manualmente.")
            break
        except Exception as e:
            logger.exception(f"Erro no loop principal: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()