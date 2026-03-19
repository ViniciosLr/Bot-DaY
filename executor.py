class TradeExecutor:
    def __init__(self, browser, logger):
        self.browser = browser
        self.logger = logger

    def set_amount(self, amount: float) -> bool:
        """
        Ajuste os seletores da área de valor.
        """
        amount_selectors = [
            'input[type="number"]',
            'input[inputmode="decimal"]',
            'input[placeholder*="Amount"]',
            'input[placeholder*="Valor"]',
            'input[class*="amount"]',
        ]

        for selector in amount_selectors:
            try:
                locator = self.browser.page.locator(selector).first
                if locator.count() > 0:
                    locator.click()
                    locator.fill("")
                    locator.fill(str(amount))
                    self.logger.info(f"Valor configurado: {amount}")
                    return True
            except Exception:
                continue

        self.logger.warning("Não foi possível localizar o campo de valor.")
        return False

    def prepare_trade(self, side: str, amount: float) -> dict:
        """
        Apenas prepara e valida. Não executa sozinho.
        """
        side = side.lower().strip()
        if side not in ("buy", "sell", "call", "put"):
            return {
                "success": False,
                "message": "Lado inválido. Use buy/sell/call/put."
            }

        normalized_side = "call" if side in ("buy", "call") else "put"

        amount_ok = self.set_amount(amount)
        if not amount_ok:
            return {
                "success": False,
                "message": "Campo de valor não encontrado."
            }

        current_price = self.browser.get_quote_from_screen()

        return {
            "success": True,
            "side": normalized_side,
            "amount": amount,
            "price": current_price,
            "message": "Operação preparada com sucesso."
        }

    def confirm_trade_from_console(self, side: str, amount: float) -> bool:
        """
        Exige confirmação manual no terminal.
        """
        info = self.prepare_trade(side, amount)
        if not info["success"]:
            self.logger.warning(info["message"])
            return False

        self.logger.info(
            f"Preparado | lado={info['side']} | valor={info['amount']} | preço={info['price']}"
        )

        confirm = input(
            f"Confirmar clique MANUAL assistido para {info['side'].upper()} "
            f"com valor {amount}? Digite SIM: "
        ).strip().upper()

        if confirm != "SIM":
            self.logger.info("Operação cancelada pelo usuário.")
            return False

        return self._click_trade_button(info["side"])

    def _click_trade_button(self, side: str) -> bool:
        """
        Ainda exige sua confirmação antes de clicar.
        Ajuste os seletores reais dos botões.
        """
        if side == "call":
            button_selectors = [
                'button:has-text("CALL")',
                'button:has-text("Buy")',
                'button:has-text("Acima")',
                '.call-btn',
                '.btn-call',
            ]
        else:
            button_selectors = [
                'button:has-text("PUT")',
                'button:has-text("Sell")',
                'button:has-text("Abaixo")',
                '.put-btn',
                '.btn-put',
            ]

        for selector in button_selectors:
            try:
                locator = self.browser.page.locator(selector).first
                if locator.count() > 0:
                    locator.click()
                    self.logger.info(f"Botão {side.upper()} clicado.")
                    return True
            except Exception:
                continue

        self.logger.warning(f"Botão {side.upper()} não encontrado.")
        return False