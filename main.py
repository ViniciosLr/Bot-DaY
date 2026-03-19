import os
from dotenv import load_dotenv

from browser import QuotexBrowser
from logger import setup_logger


def main():
    load_dotenv(".env")
    logger = setup_logger()

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        raise RuntimeError("QUOTEX_EMAIL e QUOTEX_PASSWORD não encontrados no config/.env")

    browser = QuotexBrowser(email=email, password=password, headless=True)

    try:
        browser.start()
        browser.open_platform()
        browser.login()

        logger.info(f"Página atual: {browser.get_current_url()}")
        logger.info(f"Título: {browser.get_page_title()}")

        switched = browser.switch_to_demo_if_available()
        if switched:
            logger.info("Conta demo selecionada.")
        else:
            logger.warning("Não consegui confirmar a troca para conta demo.")

        price = browser.get_quote_from_screen()
        logger.info(f"Preço encontrado na tela: {price}")

        browser.wait_seconds(10)

    finally:
        browser.stop()


if __name__ == "__main__":
    main()