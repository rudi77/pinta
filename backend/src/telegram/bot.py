"""Telegram bot entry point for Pinta Maler-Agent.

Startet als long-running asyncio-Task innerhalb des FastAPI-Prozesses
(eingehängt via lifespan in src/main.py). Für Production später auf
Webhook-Modus umschalten, sobald eine öffentliche URL (nginx/traefik)
bereitsteht — Long-Polling ist nur fürs lokale Dev-Setup.

Handler-Kontrakt:
  /start <token>   bindet telegram_chat_id an einen Pinta-User (Deep-Link
                   aus dem React-Dashboard: t.me/PintaBot?start=<token>).
  /neu             resettet den aktiven Draft (Session-Wipe).
  /status          zeigt, was der Agent bisher gesammelt hat.
  <text>           → agent.run()
  <voice>          → Whisper-Transkript → agent.run()
  <photo>          → visual_estimate-Tool → Zusammenfassung → agent.run()
"""
import logging

# TODO: python-telegram-bot v21+ in requirements.txt aufnehmen, dann einkommentieren.
# from telegram import Update
# from telegram.ext import (
#     Application, CommandHandler, MessageHandler, filters, ContextTypes,
# )

from src.core.settings import settings
from src.agents.factory import create_maler_agent
from src.telegram.state import get_session_for_chat, reset_session_for_chat

logger = logging.getLogger(__name__)


# --- Handlers -------------------------------------------------------------

async def start_handler(update, context) -> None:
    """``/start <linking_token>`` — bindet Chat an Pinta-User."""
    # TODO: token aus context.args[0] lesen, gegen DB-Tabelle telegram_link_tokens
    # prüfen, bei Erfolg TelegramLink-Row anlegen, Session mit user_id befüllen.
    raise NotImplementedError


async def neu_handler(update, context) -> None:
    """``/neu`` — startet einen frischen Angebotsentwurf."""
    chat_id = update.effective_chat.id
    reset_session_for_chat(chat_id)
    await update.message.reply_text(
        "Alles klar — neuer Kostenvoranschlag. Leg los, was soll ich notieren?"
    )


async def status_handler(update, context) -> None:
    """``/status`` — zeigt aktuellen Draft-Zustand."""
    raise NotImplementedError


async def text_handler(update, context) -> None:
    """Freitext → frischer Agent pro Mission → execute_stream → reply.

    WICHTIG: neuer Agent pro Message, ``await agent.close()`` im finally.
    LeanAgent-Instanzen sind nicht für parallele Missions geeignet — teilen
    würde den Message-Context zwischen Chats stompen.
    """
    chat_id = update.effective_chat.id
    session = get_session_for_chat(chat_id)
    if session.user_id is None:
        await update.message.reply_text(
            "Bitte zuerst im Dashboard verknüpfen (Profil → Telegram verbinden)."
        )
        return

    agent = await create_maler_agent()
    try:
        async for event in agent.execute_stream(
            mission=update.message.text,
            session_id=str(chat_id),
        ):
            logger.debug("agent event: %s", event)
            # TODO: event-Typen differenzieren (tool_call, assistant_delta,
            # final_message) und per Telegram senden. Aggregieren statt
            # pro-Event feuern — Telegram Rate-Limit: 30 msg/s pro Bot,
            # 1 msg/s pro Chat.
    finally:
        await agent.close()
    raise NotImplementedError("Event-Handling + Reply-Aggregation noch offen.")


async def voice_handler(update, context) -> None:
    """Sprachnachricht herunterladen → Whisper → wie text_handler."""
    # TODO: voice = await update.message.voice.get_file()
    #       bytes = await voice.download_as_bytearray()
    #       transcript = await whisper_transcribe(bytes)  # Azure oder OpenAI
    #       → text_handler-Logik mit transcript
    raise NotImplementedError


async def photo_handler(update, context) -> None:
    """Foto herunterladen → visual_estimate → Summary in History einhängen."""
    # TODO: photo = await update.message.photo[-1].get_file()
    #       bytes = await photo.download_as_bytearray()
    #       → src.agents.tools.visual_estimate → summary
    #       → text_handler-Logik mit "(Foto analysiert: {summary})"
    raise NotImplementedError


# --- Application builder --------------------------------------------------

def build_application():
    """Construct python-telegram-bot ``Application``. Aus main.py lifespan aufrufen.

    Gibt ``None`` zurück, wenn kein Bot-Token gesetzt ist — damit läuft das
    Backend weiter, auch ohne Telegram (für reine Dashboard-Sessions).
    """
    token = getattr(settings, "telegram_bot_token", "") or ""
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return None

    raise NotImplementedError(
        "pip install python-telegram-bot>=21, dann:\n"
        "    app = Application.builder().token(token).build()\n"
        "    app.add_handler(CommandHandler('start',  start_handler))\n"
        "    app.add_handler(CommandHandler('neu',    neu_handler))\n"
        "    app.add_handler(CommandHandler('status', status_handler))\n"
        "    app.add_handler(MessageHandler(filters.VOICE,           voice_handler))\n"
        "    app.add_handler(MessageHandler(filters.PHOTO,           photo_handler))\n"
        "    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))\n"
        "    return app"
    )
