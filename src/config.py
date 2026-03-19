import os
from dotenv import load_dotenv

load_dotenv()

SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
INTERVAL = os.getenv("INTERVAL", "1m")
DB_PATH = os.getenv("DB_PATH", "paper_bot.db")

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "1000"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.005"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.02"))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "1"))
RISK_REWARD = float(os.getenv("RISK_REWARD", "2.0"))
STOP_PERCENT = float(os.getenv("STOP_PERCENT", "0.003"))
LOOP_SECONDS = int(os.getenv("LOOP_SECONDS", "5"))
USE_TESTNET_WORDING = os.getenv("USE_TESTNET_WORDING", "true").lower() == "true"

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"