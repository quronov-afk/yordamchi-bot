"""Topshiriq matnidan muddatni ajratib olish (AI'siz, oddiy so'zlar bo'yicha)."""
import re
from datetime import datetime, timedelta

from config import TZ

WEEKDAYS = {
    "dushanba": 0, "seshanba": 1, "chorshanba": 2, "payshanba": 3,
    "juma": 4, "shanba": 5, "yakshanba": 6,
}

MONTHS = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9, "oktabr": 10,
    "oktyabr": 10, "noyabr": 11, "dekabr": 12,
}

_MONTHS_RE = "|".join(MONTHS)
_WEEKDAYS_RE = "|".join(WEEKDAYS)

PATTERNS = [
    # "15-sentabrgacha", "15 sentabr"
    (rf"\b(\d{{1,2}})[-\s]?({_MONTHS_RE})\w*", "monthday"),
    # "15.09", "15/09", "20.09 ga"
    (r"\b(\d{1,2})[./](\d{1,2})(?![./]?\d)(?:\s*(?:ga|gacha|kuni))?", "numeric"),
    # "3 kunda", "3 kun ichida", "3 kundan keyin"
    (r"\b(\d{1,2})\s*kun\w*(?:\s*(?:ichida|keyin))?", "days"),
    # "dushanbagacha", "juma kuni"
    (rf"\b({_WEEKDAYS_RE})\w*", "weekday"),
    (r"\bbugun\w*", "today"),
    (r"\bertaga\w*", "tomorrow"),
    (r"\bindin\w*", "aftertomorrow"),
]


def _today():
    return datetime.now(TZ).date()


def parse_due(text: str):
    """Matndan muddatni topadi.

    Qaytaradi: (muddat 'YYYY-MM-DD' yoki None, muddat so'zi olib tashlangan matn)
    """
    if not text:
        return None, text

    today = _today()
    low = text.lower()

    for pattern, kind in PATTERNS:
        m = re.search(pattern, low)
        if not m:
            continue

        due = None
        try:
            if kind == "today":
                due = today
            elif kind == "tomorrow":
                due = today + timedelta(days=1)
            elif kind == "aftertomorrow":
                due = today + timedelta(days=2)
            elif kind == "days":
                due = today + timedelta(days=int(m.group(1)))
            elif kind == "weekday":
                target = WEEKDAYS[m.group(1)]
                ahead = (target - today.weekday()) % 7 or 7
                due = today + timedelta(days=ahead)
            elif kind == "monthday":
                day, month = int(m.group(1)), MONTHS[m.group(2)]
                year = today.year + (1 if month < today.month else 0)
                due = datetime(year, month, day).date()
            elif kind == "numeric":
                day, month = int(m.group(1)), int(m.group(2))
                year = today.year + (1 if month < today.month else 0)
                due = datetime(year, month, day).date()
        except ValueError:
            continue

        if not due:
            continue

        cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
        return due.isoformat(), cleaned or text

    return None, text


def human_due(iso: str):
    """'2026-09-10' → 'ertaga' yoki '10-sentabr'."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso).date()
    except ValueError:
        return iso

    delta = (d - _today()).days
    if delta == 0:
        return "bugun"
    if delta == 1:
        return "ertaga"
    if delta == -1:
        return "kecha"

    names = {v: k for k, v in MONTHS.items() if k not in ("sentyabr", "oktyabr")}
    return f"{d.day}-{names[d.month]}"
