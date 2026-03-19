import os
import sys
import queue
import signal
import sqlite3
import threading
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# ---------------------------------------------------
# Ajusta imports do projeto
# ---------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from config import DB_PATH, INITIAL_BALANCE  # noqa: E402
from database import Database  # noqa: E402


class BotDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Bot Binance - Painel de Controle")
        self.root.geometry("980x700")
        self.root.minsize(900, 650)

        self.process = None
        self.log_queue = queue.Queue()
        self.db = Database(DB_PATH)

        self._build_ui()
        self._schedule_tasks()

    # ---------------------------------------------------
    # UI
    # ---------------------------------------------------
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # Topo
        top_frame = ttk.Frame(main)
        top_frame.pack(fill="x", pady=(0, 10))

        self.status_var = tk.StringVar(value="Parado")
        self.status_color_var = tk.StringVar(value="red")

        ttk.Label(
            top_frame,
            text="Painel do Bot Binance",
            font=("Arial", 16, "bold")
        ).pack(side="left")

        status_frame = ttk.Frame(top_frame)
        status_frame.pack(side="right")

        ttk.Label(status_frame, text="Status:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 6))
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side="left")

        # Botões
        buttons_frame = ttk.Frame(main)
        buttons_frame.pack(fill="x", pady=(0, 10))

        self.start_button = ttk.Button(
            buttons_frame,
            text="Iniciar Bot",
            command=self.start_bot
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = ttk.Button(
            buttons_frame,
            text="Parar Bot",
            command=self.stop_bot,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=(0, 8))

        self.clear_button = ttk.Button(
            buttons_frame,
            text="Limpar Logs",
            command=self.clear_logs
        )
        self.clear_button.pack(side="left")

        # Cards de métricas
        metrics_frame = ttk.LabelFrame(main, text="Métricas")
        metrics_frame.pack(fill="x", pady=(0, 10))

        self.metrics = {
            "saldo_bot": tk.StringVar(value="0.00"),
            "profit_day": tk.StringVar(value="0.00"),
            "loss_day": tk.StringVar(value="0.00"),
            "profit_pct": tk.StringVar(value="0.00%"),
            "loss_pct": tk.StringVar(value="0.00%"),
            "net_result": tk.StringVar(value="0.00"),
            "net_pct": tk.StringVar(value="0.00%"),
            "wins": tk.StringVar(value="0"),
            "losses": tk.StringVar(value="0"),
            "trades": tk.StringVar(value="0"),
            "win_rate": tk.StringVar(value="0.0%"),
            "profit_factor": tk.StringVar(value="0.00"),
            "seq_win": tk.StringVar(value="0"),
            "seq_loss": tk.StringVar(value="0"),
        }

        grid = ttk.Frame(metrics_frame, padding=10)
        grid.pack(fill="x")

        items = [
            ("Saldo Bot", "saldo_bot"),
            ("Profit Dia", "profit_day"),
            ("Loss Dia", "loss_day"),
            ("Lucro % Dia", "profit_pct"),
            ("Loss % Dia", "loss_pct"),
            ("Net", "net_result"),
            ("Net %", "net_pct"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Profit Factor", "profit_factor"),
            ("Seq Win Máx", "seq_win"),
            ("Seq Loss Máx", "seq_loss"),
        ]

        for idx, (label, key) in enumerate(items):
            row = idx // 4
            col = idx % 4

            card = ttk.Frame(grid, padding=8, relief="ridge")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            ttk.Label(card, text=label, font=("Arial", 9, "bold")).pack(anchor="w")
            ttk.Label(card, textvariable=self.metrics[key], font=("Arial", 11)).pack(anchor="w", pady=(4, 0))

        for i in range(4):
            grid.columnconfigure(i, weight=1)

        # Logs
        logs_frame = ttk.LabelFrame(main, text="Logs do Bot")
        logs_frame.pack(fill="both", expand=True)

        self.log_text = ScrolledText(
            logs_frame,
            wrap="word",
            font=("Consolas", 10),
            height=20
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_text.configure(state="disabled")

    # ---------------------------------------------------
    # Bot control
    # ---------------------------------------------------
    def start_bot(self):
        if self.process and self.process.poll() is None:
            self.append_log("O bot já está rodando.\n")
            return

        python_executable = sys.executable
        main_script = os.path.join(SRC_DIR, "main.py")

        if not os.path.exists(main_script):
            self.append_log(f"Arquivo não encontrado: {main_script}\n")
            return

        try:
            self.process = subprocess.Popen(
                [python_executable, "-u", main_script],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )

            self.status_var.set("Rodando")
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.append_log("Bot iniciado com sucesso.\n")

            threading.Thread(target=self._read_process_output, daemon=True).start()

        except Exception as e:
            self.append_log(f"Erro ao iniciar bot: {e}\n")

    def stop_bot(self):
        if not self.process or self.process.poll() is not None:
            self.append_log("O bot já está parado.\n")
            self.status_var.set("Parado")
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            return

        try:
            if os.name == "nt":
                self.process.terminate()
            else:
                self.process.send_signal(signal.SIGINT)

            self.process.wait(timeout=5)
            self.append_log("Bot parado com sucesso.\n")

        except subprocess.TimeoutExpired:
            self.process.kill()
            self.append_log("Bot foi finalizado à força.\n")
        except Exception as e:
            self.append_log(f"Erro ao parar bot: {e}\n")
        finally:
            self.status_var.set("Parado")
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")

    def _read_process_output(self):
        if not self.process or not self.process.stdout:
            return

        try:
            for line in self.process.stdout:
                self.log_queue.put(line)
        except Exception as e:
            self.log_queue.put(f"Erro lendo saída do processo: {e}\n")
        finally:
            self.log_queue.put("__BOT_PROCESS_ENDED__")

    # ---------------------------------------------------
    # Logs
    # ---------------------------------------------------
    def append_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _process_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()

                if item == "__BOT_PROCESS_ENDED__":
                    if self.process and self.process.poll() is not None:
                        self.status_var.set("Parado")
                        self.start_button.config(state="normal")
                        self.stop_button.config(state="disabled")
                    continue

                self.append_log(item)
        except queue.Empty:
            pass

        self.root.after(200, self._process_log_queue)

    # ---------------------------------------------------
    # Metrics
    # ---------------------------------------------------
    def _update_metrics(self):
        try:
            state = self.db.get_bot_state()
            summary = self.db.get_performance_summary()

            saldo_bot = float(state["balance"])
            profit_day = float(state["daily_profit"])
            loss_day = float(state["daily_loss"])

            total_trades = int(summary["total_trades"])
            win_rate = float(summary["win_rate"])
            net_result = float(summary["net_result"])
            profit_factor = float(summary["profit_factor"])
            max_win_streak = int(summary["max_win_streak"])
            max_loss_streak = int(summary["max_loss_streak"])

            wins = int(state["wins"])
            losses = int(state["losses"])

            base_balance = float(INITIAL_BALANCE) if float(INITIAL_BALANCE) > 0 else 1.0

            profit_pct = (profit_day / base_balance) * 100.0
            loss_pct = (loss_day / base_balance) * 100.0
            net_pct = (net_result / base_balance) * 100.0

            self.metrics["saldo_bot"].set(f"{saldo_bot:.2f}")
            self.metrics["profit_day"].set(f"{profit_day:.2f}")
            self.metrics["loss_day"].set(f"{loss_day:.2f}")
            self.metrics["profit_pct"].set(f"{profit_pct:.2f}%")
            self.metrics["loss_pct"].set(f"{loss_pct:.2f}%")
            self.metrics["net_result"].set(f"{net_result:.2f}")
            self.metrics["net_pct"].set(f"{net_pct:.2f}%")
            self.metrics["wins"].set(str(wins))
            self.metrics["losses"].set(str(losses))
            self.metrics["trades"].set(str(total_trades))
            self.metrics["win_rate"].set(f"{win_rate:.1f}%")
            self.metrics["profit_factor"].set(f"{profit_factor:.2f}")
            self.metrics["seq_win"].set(str(max_win_streak))
            self.metrics["seq_loss"].set(str(max_loss_streak))

        except sqlite3.Error as e:
            self.append_log(f"Erro SQLite ao ler métricas: {e}\n")
        except Exception as e:
            self.append_log(f"Erro ao atualizar métricas: {e}\n")

        self.root.after(2000, self._update_metrics)

    # ---------------------------------------------------
    # Loop scheduling
    # ---------------------------------------------------
    def _schedule_tasks(self):
        self.root.after(200, self._process_log_queue)
        self.root.after(1000, self._update_metrics)

    def on_close(self):
        if self.process and self.process.poll() is None:
            self.stop_bot()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = BotDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()