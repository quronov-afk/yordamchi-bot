"""Gemini orqali: guruh xabari (matn yoki ovoz) — kimga, nima, qachongacha."""
import base64
import json
import logging

import requests

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _prompt(team_names):
    return (
        "Sen Telegram ish guruhidagi yozishmalarni o'qib, kimga qanday topshiriq "
        "berilganini aniqlaydigan yordamchisan.\n\n"
        "Jamoada shu odamlar bor: " + ", ".join(team_names) + ".\n\n"
        "Agar xabar (matn yoki ovoz) ANIQ bir kishiga ish/vazifa/topshiriq berish "
        "bo'lsa, FAQAT shu JSON'ni qaytar (boshqa hech narsa yozma, izoh yozma):\n"
        '{"is_task": true, '
        '"assignee": "<jamoadagi ismlardan ENG YAQIN mos keladigani, aynan ro\'yxatdagidek>", '
        '"task": "<qisqa, buyruq shaklidagi topshiriq matni, o\'zbek tilida>", '
        '"due": "<agar muddat aytilgan bo\'lsa oddiy so\'z bilan: bugun, ertaga, juma, '
        '3 kunda, 15-sentabr va h.k, aytilmagan bo\'lsa null>"}\n\n'
        "Agar bu shunchaki suhbat, savol, salomlashish, hazil, umumiy fikr yoki "
        "ANIQ bir kishiga qaratilmagan bo'lsa, FAQAT shu JSON'ni qaytar:\n"
        '{"is_task": false}\n\n'
        "Qat'iy qoida: \"assignee\" maydoni albatta jamoadagi ismlardan BIRIGA mos "
        "kelishi shart. Mos kishi topilmasa is_task=false qaytar."
    )


def _call(parts, team_names):
    if not GEMINI_API_KEY or not team_names:
        return None

    body = {
        "contents": [{"parts": [{"text": _prompt(team_names)}] + parts}],
        "generationConfig": {"temperature": 0, "response_mime_type": "application/json"},
    }
    url = API_URL.format(model=GEMINI_MODEL)

    try:
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=25)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except Exception as e:
        logger.warning("Gemini xato: %s", e)
        return None

    if not isinstance(data, dict) or not data.get("is_task"):
        return None
    if not data.get("assignee") or not data.get("task"):
        return None
    return data


def from_text(text, team_names):
    text = (text or "").strip()
    if len(text) < 6:
        return None
    return _call([{"text": text}], team_names)


def from_audio(audio_bytes, mime_type, team_names):
    b64 = base64.b64encode(audio_bytes).decode()
    return _call([{"inline_data": {"mime_type": mime_type, "data": b64}}], team_names)
