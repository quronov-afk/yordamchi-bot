import logging
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp
from telegram.ext import Application, CommandHandler, ContextTypes

import api
import db
from config import BOT_TOKEN, APP_URL, PORT, APP_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WELCOME = (
    "✍️ <b>Yordamchi AI</b>\n"
    "<i>Guruhdagi topshiriqlar bir joyda</i>\n\n"
    "Guruhda berilgan topshiriqlar shu yerda yig'iladi: kim nima qilishi kerak, "
    "qachongacha va qaysi biri bajarildi.\n\n"
    "📋 Vazifalar taxtasi: yangi, jarayonda, bajarilgan\n"
    "👥 Rahbar uchun — butun jamoa ko'rinishi\n"
    "⏰ Muddati o'tayotgan ishlar o'zi eslatiladi\n\n"
    "Ilovani ochamizmi?"
)


def open_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ilovani ochish", web_app=WebAppInfo(url=APP_URL))
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not APP_URL:
        await update.effective_message.reply_text("Ilova manzili hali sozlanmagan (APP_URL).")
        return

    user = update.effective_user
    name = user.full_name or user.first_name or "Foydalanuvchi"
    db.upsert_user(user.id, name, user.username)

    # Taklif havolasi bilan kelgan bo'lsa — kompaniyaga qo'shiladi
    code = context.args[0] if context.args else None
    if code and not db.membership(user.id):
        if db.use_invite(code, user.id):
            m = db.membership(user.id)
            await update.effective_message.reply_text(
                f"✅ <b>{m['company_name']}</b> jamoasiga qo'shildingiz!\n"
                f"Rolingiz: <b>{db.ROLES.get(m['role'], 'Xodim')}</b>",
                parse_mode="HTML", reply_markup=open_button())
            return
        await update.effective_message.reply_text(
            "❌ <b>Bu taklif havolasi ishlamadi.</b>\n\n"
            "U allaqachon ishlatilgan bo'lishi mumkin — rahbaringizdan yangi havola so'rang.",
            parse_mode="HTML")
        return

    await update.effective_message.reply_text(
        WELCOME, parse_mode="HTML", reply_markup=open_button())


async def on_startup(app: Application):
    """Yozishmadagi menyu tugmasi ham Mini App'ni ochsin."""
    if APP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text=APP_NAME, web_app=WebAppInfo(url=APP_URL)))
        except Exception as e:
            logger.warning("Menyu tugmasi sozlanmadi: %s", e)


def main():
    threading.Thread(target=api.run_server, args=(PORT,), daemon=True).start()
    logger.info("Mini App %s-portda ishga tushdi", PORT)

    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN yo'q — faqat Mini App rejimida ishlayapti")
        threading.Event().wait()
        return

    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    logger.info("Bot ishga tushdi")
    app.run_polling()


if __name__ == "__main__":
    main()
