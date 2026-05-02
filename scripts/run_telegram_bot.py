"""Standalone runner for the Pinta Telegram bot.

Run: ``backend/.venv/Scripts/python.exe scripts/run_telegram_bot.py``

Uses pytaskforce' built-in TelegramPoller + TelegramOutboundSender, wired
to Pinta's Maler-Agent. No webhook needed (long-polling).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ.pop("OPENAI_API_KEY", None)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    from src.telegram.runner import run_bot_forever

    print("Starting Pinta Maler-Agent Telegram bot. Ctrl-C to stop.")
    await run_bot_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped (Ctrl-C)")
