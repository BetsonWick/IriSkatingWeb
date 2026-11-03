"""Уведомление владельцу о новой заявке через Telegram Bot API."""

from __future__ import annotations

import html
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROGRAM_LABELS = {
    "individual": "Individual online lesson",
    "group": "Group online class",
    "video": "Video analysis & feedback",
    "fitness": "SkateFit weight loss program",
}

TIME_LABELS = {
    "morning": "morning",
    "afternoon": "afternoon",
    "evening": "evening",
    "any": "any time",
}

METHOD_LABELS = {
    "telegram": "Telegram",
    "instagram": "Instagram",
    "whatsapp": "WhatsApp",
    "email": "Email",
}


def build_booking_message(booking: dict[str, Any]) -> str:
    """HTML-сообщение для админ-чата. Пользовательские поля экранируются."""
    method = booking.get("contact_method", "")
    program = booking.get("program", "")
    time_pref = booking.get("preferred_time", "")
    comment = str(booking.get("comment") or "—")

    lines = [
        "🆕 <b>New booking request</b>",
        f"👤 {html.escape(str(booking.get('name', '')))}",
        f"📱 {METHOD_LABELS.get(method, method)}: "
        f"{html.escape(str(booking.get('contact', '')))}",
        f"🎯 {PROGRAM_LABELS.get(program, program)}",
        f"📅 {html.escape(str(booking.get('preferred_date', '')))} · "
        f"{html.escape(TIME_LABELS.get(time_pref, time_pref))}",
        f"💬 {html.escape(comment)}",
    ]
    return "\n".join(lines)


async def send_message(token: str, chat_id: str, text: str) -> bool:
    """Отправка в Telegram. Ошибки не прерывают приём заявки — только лог."""
    if not token or not chat_id:
        logger.warning(
            "TELEGRAM_BOT_TOKEN/TELEGRAM_ADMIN_CHAT_ID не заданы — уведомление пропущено"
        )
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception:  # noqa: BLE001 — сеть не должна ломать приём заявки
        logger.warning("Telegram sendMessage недоступен", exc_info=True)
        return False
    if response.status_code != 200:
        logger.warning(
            "Telegram sendMessage: HTTP %d — %s",
            response.status_code,
            response.text[:200],
        )
        return False
    return True
