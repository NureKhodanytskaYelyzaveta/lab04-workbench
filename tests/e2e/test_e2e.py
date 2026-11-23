"""Просунуто: наскрізний тест Playwright для демонстраційного режиму.

Один раз: uv add --dev playwright && uv run playwright install chromium
Запуск:   uv run pytest -m e2e tests/e2e
Сервер демонстраційного режиму підіймається в самому тесті; ключ API не потрібен.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[2]
expect.set_options(timeout=120_000)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def demo_url():
    port = free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "tests/demo_app.py", "--server.port",
         str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://localhost:{port}"
    for _ in range(60):
        try:
            socket.create_connection(("localhost", port), timeout=1).close()
            break
        except OSError:
            time.sleep(1)
    yield url
    proc.terminate()


def test_ask_run_team_and_human_gate(demo_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(150000)
        page.goto(demo_url)
        # UC1: питання до бази знань
        page.get_by_placeholder("Запитайте про правила").fill("Як будувати криву страху?")
        page.keyboard.press("Enter")
        expect(page.get_by_text("Фрагменти, знайдені агентом")).to_be_visible(timeout=120000)
        # UC2: команда агентів
        page.get_by_role("tab", name="Команда агентів").click()
        page.get_by_label("Опис сцени").fill(
            "Герой заходить у покинуту дитячу лікарню, де чути дитячий сміх.")
        page.get_by_role("button", name="Запустити команду").click()
        expect(page.get_by_text("Біти і крива страху")).to_be_visible(timeout=120000)
        # UC4: людина в циклі — кнопка неактивна до підтвердження
        save = page.get_by_role("button", name="Зберегти в Obsidian (Inbox)")
        expect(save).to_be_disabled()
        page.get_by_label("Ваше ім'я").fill("Іваненко")
        page.get_by_text("Я перевірив сцену").click()
        expect(save).to_be_enabled()
        save.click()
        expect(page.get_by_text("Збережено:")).to_be_visible(timeout=120000)
        browser.close()
