from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class QuotexBrowser:
    def __init__(self, email: str, password: str, headless: bool = False):
        self.email = email
        self.password = password
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=300
        )
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_viewport_size({"width": 1440, "height": 900})

    def stop(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def open_platform(self):
        self.page.goto("https://qxbroker.com/en/sign-in/", wait_until="domcontentloaded", timeout=60000)

    def login(self):
        """
        Ajuste os seletores se a Quotex mudar o HTML.
        """
        try:
            self.page.wait_for_timeout(2000)

            email_candidates = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="Email"]',
                'input[placeholder*="email"]',
            ]

            password_candidates = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="Password"]',
                'input[placeholder*="password"]',
                'input[placeholder*="Senha"]',
            ]

            login_button_candidates = [
                'button[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Login")',
                'button:has-text("Entrar")',
                'button:has-text("Log in")',
            ]

            email_ok = False
            for selector in email_candidates:
                locator = self.page.locator(selector).first
                if locator.count() > 0:
                    locator.fill(self.email)
                    email_ok = True
                    break

            if not email_ok:
                raise RuntimeError("Campo de email não encontrado.")

            password_ok = False
            for selector in password_candidates:
                locator = self.page.locator(selector).first
                if locator.count() > 0:
                    locator.fill(self.password)
                    password_ok = True
                    break

            if not password_ok:
                raise RuntimeError("Campo de senha não encontrado.")

            clicked = False
            for selector in login_button_candidates:
                locator = self.page.locator(selector).first
                if locator.count() > 0:
                    locator.click()
                    clicked = True
                    break

            if not clicked:
                raise RuntimeError("Botão de login não encontrado.")

            self.page.wait_for_timeout(5000)

        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"Timeout no login: {e}") from e

    def switch_to_demo_if_available(self):
        """
        Método opcional.
        Ajuste conforme a interface real da conta demo.
        """
        candidates = [
            'text="Demo"',
            'text="Conta demo"',
            'text="Practice"',
            'text="Practice account"',
        ]

        for selector in candidates:
            locator = self.page.locator(selector).first
            if locator.count() > 0:
                try:
                    locator.click()
                    self.page.wait_for_timeout(2000)
                    return True
                except Exception:
                    pass
        return False

    def get_current_url(self) -> str:
        return self.page.url if self.page else ""

    def get_page_title(self) -> str:
        return self.page.title() if self.page else ""

    def screenshot(self, path: str = "quotex.png"):
        if self.page:
            self.page.screenshot(path=path, full_page=True)

    def get_visible_text(self) -> str:
        if not self.page:
            return ""
        try:
            return self.page.locator("body").inner_text(timeout=10000)
        except Exception:
            return ""

    def get_quote_from_screen(self) -> float | None:
        """
        Leitura simples da tela.
        Você vai precisar ajustar os seletores reais da Quotex.
        """
        price_selectors = [
            '[data-testid="price"]',
            '.price',
            '.asset-price',
            '.current-price',
            'span[class*="price"]',
            'div[class*="price"]',
        ]

        for selector in price_selectors:
            try:
                locator = self.page.locator(selector).first
                if locator.count() > 0:
                    text = locator.inner_text().strip()
                    value = self._extract_number(text)
                    if value is not None:
                        return value
            except Exception:
                continue

        return None

    def _extract_number(self, text: str) -> float | None:
        cleaned = (
            text.replace(",", ".")
            .replace("R$", "")
            .replace("$", "")
            .strip()
        )

        allowed = "0123456789.-"
        result = "".join(ch for ch in cleaned if ch in allowed)

        if not result:
            return None

        try:
            return float(result)
        except ValueError:
            return None

    def wait_seconds(self, seconds: int):
        self.page.wait_for_timeout(seconds * 1000)