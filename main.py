import logging
import threading

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
                      MenuButtonWebApp, BotCommand, BotCommandScopeAllPrivateChats,
                      BotCommandScopeAllGroupChats)
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import ai
import api
import db
from config import BOT_TOKEN, APP_URL, PORT, APP_NAME
from parse import parse_due, human_due

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

TASK_HELP = (
    "📋 <b>Vazifa berish</b>\n\n"
    "1. Xodimning xabariga <b>javob berib</b>:\n"
    "<code>/vazifa Hisobotni ertaga tayyorla</code>\n\n"
    "2. Yoki xodimni <b>belgilab</b>:\n"
    "<code>/vazifa @username Hisobotni ertaga tayyorla</code>\n\n"
    "Muddatni oddiy yozsangiz bo'ladi: <i>bugun, ertaga, jumagacha, "
    "3 kunda, 15-sentabr</i>"
)


def open_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ilovani ochish", web_app=WebAppInfo(url=APP_URL))
    ]])


# ----------------------------------------------------------
# Shaxsiy yozishma
# ----------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return await group_help(update, context)

    if not APP_URL:
        await update.effective_message.reply_text("Ilova manzili hali sozlanmagan (APP_URL).")
        return

    user = update.effective_user
    name = user.full_name or user.first_name or "Foydalanuvchi"
    db.upsert_user(user.id, name, user.username)

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


# ----------------------------------------------------------
# Guruh
# ----------------------------------------------------------
async def group_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if db.group_company(chat.id):
        await update.effective_message.reply_text(TASK_HELP, parse_mode="HTML")
    else:
        await update.effective_message.reply_text(
            "👋 <b>Yordamchi AI</b>\n\n"
            "Bu guruhni kompaniyangizga ulash uchun rahbar yoki bo'lim boshlig'i "
            "<code>/ulash</code> deb yozsin.",
            parse_mode="HTML")


async def link_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Bu buyruq ish guruhida yoziladi — botni guruhga qo'shib, o'sha yerda /ulash deb yozing.")
        return

    user = update.effective_user
    db.upsert_user(user.id, user.full_name or user.first_name, user.username)
    m = db.membership(user.id)

    if not m:
        await update.effective_message.reply_text(
            "Avval ilovada kompaniya yarating yoki taklif havolasi orqali jamoaga qo'shiling.")
        return
    if m["role"] not in ("owner", "head"):
        await update.effective_message.reply_text(
            "Guruhni faqat rahbar yoki bo'lim boshlig'i ulay oladi.")
        return

    db.link_group(chat.id, m["company_id"], chat.title, user.id)
    await update.effective_message.reply_text(
        f"✅ Bu guruh <b>{m['company_name']}</b> kompaniyasiga ulandi.\n\n" + TASK_HELP,
        parse_mode="HTML")


def find_assignee(update: Update):
    """Topshiriq kimga berilganini aniqlaydi: javob yoki @belgilash orqali."""
    msg = update.effective_message

    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        if not target.is_bot:
            db.upsert_user(target.id, target.full_name or target.first_name, target.username)
            return target.id, target.full_name or target.first_name, None

    for ent in msg.entities or []:
        if ent.type == "text_mention" and ent.user:
            target = ent.user
            db.upsert_user(target.id, target.full_name or target.first_name, target.username)
            return target.id, target.full_name or target.first_name, None
        if ent.type == "mention":
            uname = msg.text[ent.offset:ent.offset + ent.length]
            found = db.user_by_username(uname)
            if found:
                return found["id"], found["name"], uname
            return None, None, uname

    return None, None, None


async def save_task(msg, company_id, assignee_id, assignee_name, text, due_phrase, author_id):
    due, text = parse_due(text) if due_phrase is None else (parse_due(due_phrase)[0], text)
    db.add_task(company_id, msg.chat_id, msg.message_id, text, assignee_id, author_id, due)

    line = f"✅ <b>Vazifa yozib olindi</b>\n\n📝 {text}\n👤 Mas'ul: {assignee_name}"
    if due:
        line += f"\n⏰ Muddat: {human_due(due)}"
    await msg.reply_text(line, parse_mode="HTML")


async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text("Vazifa ish guruhida beriladi — botni guruhga qo'shing.")
        return

    company_id = db.group_company(chat.id)
    if not company_id:
        await msg.reply_text(
            "Bu guruh hali kompaniyaga ulanmagan. Rahbar <code>/ulash</code> deb yozsin.",
            parse_mode="HTML")
        return

    author = update.effective_user
    db.upsert_user(author.id, author.full_name or author.first_name, author.username)
    author_m = db.membership(author.id)
    if not author_m or author_m["company_id"] != company_id:
        await msg.reply_text("Siz bu kompaniya jamoasida emassiz.")
        return

    assignee_id, assignee_name, missing = find_assignee(update)
    if not assignee_id:
        if missing:
            await msg.reply_text(
                f"{missing} hali ilovaga kirmagan. Unga taklif havolasini yuboring — "
                "ilovadagi «Jamoa» bo'limidan olasiz.")
        else:
            await msg.reply_text(TASK_HELP, parse_mode="HTML")
        return

    text = " ".join(context.args) if context.args else ""
    if missing:
        text = text.replace(missing, "", 1).strip()
    if not text and msg.reply_to_message:
        text = (msg.reply_to_message.text or msg.reply_to_message.caption or "").strip()
    if not text:
        await msg.reply_text(TASK_HELP, parse_mode="HTML")
        return

    await save_task(msg, company_id, assignee_id, assignee_name, text, None, author.id)


# ----------------------------------------------------------
# AI: buyruqsiz, oddiy yozishma yoki ovozdan vazifa aniqlash
# ----------------------------------------------------------
async def ai_group_context(update: Update):
    """Guruh, kompaniya va muallifni tekshiradi. Mos bo'lmasa None qaytaradi."""
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        return None

    company_id = db.group_company(chat.id)
    if not company_id:
        return None

    author = update.effective_user
    if author.is_bot:
        return None
    db.upsert_user(author.id, author.full_name or author.first_name, author.username)
    author_m = db.membership(author.id)
    if not author_m or author_m["company_id"] != company_id:
        return None

    return company_id, author


async def resolve_ai_assignee(update: Update, company_id, result):
    """Aniq @belgilash/javob bo'lsa — o'shani ishonchli deb oladi, bo'lmasa AI aytgan ismni jamoadan qidiradi."""
    assignee_id, assignee_name, _missing = find_assignee(update)
    if assignee_id:
        return assignee_id, assignee_name

    person = db.member_by_name(company_id, result.get("assignee"))
    if person:
        return person["id"], person["name"]
    return None, None


async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ctx = await ai_group_context(update)
    if not ctx:
        return
    company_id, author = ctx
    msg = update.effective_message

    team_names = [p["name"] for p in db.team(company_id) if p["id"] != author.id]
    if not team_names:
        return

    result = ai.from_text(msg.text, team_names)
    if not result:
        return

    assignee_id, assignee_name = await resolve_ai_assignee(update, company_id, result)
    if not assignee_id:
        return

    await save_task(msg, company_id, assignee_id, assignee_name,
                     result["task"], result.get("due"), author.id)


async def handle_group_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ctx = await ai_group_context(update)
    if not ctx:
        return
    company_id, author = ctx
    msg = update.effective_message

    team_names = [p["name"] for p in db.team(company_id) if p["id"] != author.id]
    if not team_names:
        return

    file = await context.bot.get_file(msg.voice.file_id)
    audio = bytes(await file.download_as_bytearray())

    result = ai.from_audio(audio, "audio/ogg", team_names)
    if not result:
        return

    assignee_id, assignee_name = await resolve_ai_assignee(update, company_id, result)
    if not assignee_id:
        return

    await save_task(msg, company_id, assignee_id, assignee_name,
                     result["task"], result.get("due"), author.id)


# ----------------------------------------------------------
async def on_startup(app: Application):
    if APP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text=APP_NAME, web_app=WebAppInfo(url=APP_URL)))
        except Exception as e:
            logger.warning("Menyu tugmasi sozlanmadi: %s", e)

    try:
        await app.bot.set_my_commands(
            [BotCommand("start", "Ilovani ochish")],
            scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands([
            BotCommand("vazifa", "Topshiriq berish"),
            BotCommand("ulash", "Guruhni kompaniyaga ulash"),
            BotCommand("yordam", "Qanday ishlaydi"),
        ], scope=BotCommandScopeAllGroupChats())
    except Exception as e:
        logger.warning("Buyruqlar ro'yxati sozlanmadi: %s", e)


def main():
    threading.Thread(target=api.run_server, args=(PORT,), daemon=True).start()
    logger.info("Mini App %s-portda ishga tushdi", PORT)

    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN yo'q — faqat Mini App rejimida ishlayapti")
        threading.Event().wait()
        return

    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ulash", link_group))
    app.add_handler(CommandHandler("vazifa", new_task))
    app.add_handler(CommandHandler("yordam", group_help))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_text))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.VOICE, handle_group_voice))
    logger.info("Bot ishga tushdi")
    app.run_polling()


if __name__ == "__main__":
    main()
