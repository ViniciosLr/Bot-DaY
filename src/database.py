import sqlite3
from contextlib import contextmanager
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "paper_bot.db"):
        self.db_path = db_path
        self._initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    close_time INTEGER NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    quantity REAL NOT NULL,
                    status TEXT NOT NULL,
                    result REAL DEFAULT 0,
                    strategy TEXT,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    balance REAL NOT NULL DEFAULT 1000.0,
                    daily_loss REAL NOT NULL DEFAULT 0.0,
                    daily_profit REAL NOT NULL DEFAULT 0.0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    last_reset TEXT
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO bot_state (
                    id, balance, daily_loss, daily_profit, wins, losses, last_reset
                ) VALUES (
                    1, 1000.0, 0.0, 0.0, 0, 0, ?
                )
            """, (datetime.utcnow().isoformat(),))

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_open_time
                ON candles(symbol, interval, open_time)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_status
                ON trades(status)
            """)

    def clear_candles(self, symbol: str, interval: str):
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM candles WHERE symbol = ? AND interval = ?",
                (symbol, interval),
            )

    def insert_candle(
        self,
        symbol: str,
        interval: str,
        open_time: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        close_time: int,
    ):
        with self.connect() as conn:
            exists = conn.execute("""
                SELECT 1 FROM candles
                WHERE symbol = ? AND interval = ? AND open_time = ?
            """, (symbol, interval, open_time)).fetchone()

            if exists:
                conn.execute("""
                    UPDATE candles
                    SET open = ?, high = ?, low = ?, close = ?, volume = ?, close_time = ?
                    WHERE symbol = ? AND interval = ? AND open_time = ?
                """, (
                    open_, high, low, close, volume, close_time,
                    symbol, interval, open_time
                ))
            else:
                conn.execute("""
                    INSERT INTO candles (
                        symbol, interval, open_time, open, high, low, close, volume, close_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, interval, open_time, open_, high, low, close, volume, close_time
                ))

    def get_recent_candles(self, symbol: str, interval: str, limit: int = 200):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT open_time, open, high, low, close, volume, close_time
                FROM candles
                WHERE symbol = ? AND interval = ?
                ORDER BY open_time DESC
                LIMIT ?
            """, (symbol, interval, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def create_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float,
        strategy: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute("""
                INSERT INTO trades (
                    symbol, side, entry_price, stop_loss, take_profit,
                    quantity, status, result, strategy, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', 0, ?, ?)
            """, (
                symbol,
                side,
                side and entry_price,
                stop_loss,
                take_profit,
                quantity,
                strategy,
                datetime.utcnow().isoformat(),
            ))
            return cursor.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, result: float):
        with self.connect() as conn:
            conn.execute("""
                UPDATE trades
                SET exit_price = ?, result = ?, status = 'closed', closed_at = ?
                WHERE id = ? AND status = 'open'
            """, (exit_price, result, datetime.utcnow().isoformat(), trade_id))

    def close_all_open_trades(self, exit_price: float | None = None, result: float = 0.0):
        with self.connect() as conn:
            conn.execute("""
                UPDATE trades
                SET exit_price = COALESCE(?, exit_price),
                    result = ?,
                    status = 'closed',
                    closed_at = ?
                WHERE status = 'open'
            """, (exit_price, result, datetime.utcnow().isoformat()))

    def delete_all_trades(self):
        with self.connect() as conn:
            conn.execute("DELETE FROM trades")

    def get_open_trades(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM trades
                WHERE status = 'open'
                ORDER BY id ASC
            """).fetchall()
        return [dict(row) for row in rows]

    def get_closed_trades(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM trades
                WHERE status = 'closed'
                ORDER BY id ASC
            """).fetchall()
        return [dict(row) for row in rows]

    def get_bot_state(self):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
        return dict(row)

    def update_bot_state(
        self,
        balance: float,
        daily_loss: float,
        daily_profit: float,
        wins: int,
        losses: int,
        last_reset: str,
    ):
        with self.connect() as conn:
            conn.execute("""
                UPDATE bot_state
                SET balance = ?,
                    daily_loss = ?,
                    daily_profit = ?,
                    wins = ?,
                    losses = ?,
                    last_reset = ?
                WHERE id = 1
            """, (balance, daily_loss, daily_profit, wins, losses, last_reset))

    def reset_bot_state(self, balance: float = 1000.0, close_open_trades: bool = False):
        with self.connect() as conn:
            if close_open_trades:
                conn.execute("""
                    UPDATE trades
                    SET status = 'closed',
                        closed_at = ?
                    WHERE status = 'open'
                """, (datetime.utcnow().isoformat(),))

            conn.execute("""
                UPDATE bot_state
                SET balance = ?,
                    daily_loss = 0.0,
                    daily_profit = 0.0,
                    wins = 0,
                    losses = 0,
                    last_reset = ?
                WHERE id = 1
            """, (balance, datetime.utcnow().isoformat()))

    def get_performance_summary(self):
        trades = self.get_closed_trades()

        total = len(trades)
        if total == 0:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "net_result": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "avg_result": 0.0,
                "max_win_streak": 0,
                "max_loss_streak": 0,
            }

        wins = sum(1 for t in trades if float(t["result"]) > 0)
        losses = sum(1 for t in trades if float(t["result"]) < 0)

        gross_profit = sum(float(t["result"]) for t in trades if float(t["result"]) > 0)
        gross_loss = abs(sum(float(t["result"]) for t in trades if float(t["result"]) < 0))
        net_result = sum(float(t["result"]) for t in trades)
        avg_result = net_result / total
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        for trade in trades:
            result = float(trade["result"])

            if result > 0:
                current_win_streak += 1
                current_loss_streak = 0
            elif result < 0:
                current_loss_streak += 1
                current_win_streak = 0
            else:
                current_win_streak = 0
                current_loss_streak = 0

            max_win_streak = max(max_win_streak, current_win_streak)
            max_loss_streak = max(max_loss_streak, current_loss_streak)

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_result": net_result,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "avg_result": avg_result,
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
        }