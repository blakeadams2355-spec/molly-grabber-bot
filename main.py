# main.py
import re
import asyncio
import os
import random
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, \
    InputMediaVideo
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, FloodWait

import config
import database

database.init_db()

# Проверка наличия STRING_SESSION в конфиге
if hasattr(config, "STRING_SESSION") and config.STRING_SESSION:
    print("✅ Использую STRING_SESSION для входа!")
    userbot = Client("my_userbot", api_id=config.API_ID, api_hash=config.API_HASH, session_string=config.STRING_SESSION, in_memory=True)
else:
    print("⚠️ STRING_SESSION не найден, пытаюсь войти обычно...")
    userbot = Client("my_userbot", api_id=config.API_ID, api_hash=config.API_HASH)

bot = Client("my_admin_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

PHOTOS = {
    "welcome": "AgACAgIAAxkBAANQaVe-3Zy52Y1ZTdcyMqI3-P4K3bsAAhIPaxv0ZrhKL5SyfYdHoaEACAEAAwIAA3kABx4E",
    "main_menu": "AgACAgIAAxkBAAIBRGlX4v2mfFPMPH7o79CGyLU40uGBAAKTD2sbVqa5SsN29VVa_i0DAAgBAAMCAAN5AAceBA",
    "add_bind": "AgACAgIAAxkBAAIBRmlX4xhHeeLAM8ZmJBHP8h7hbGEkAAKUD2sbVqa5Srvwnh4-Y08ACQEAAwIAA3kABx4E",
    "manage_binds": "AgACAgIAAxkBAAIBTGlX47r1obGDGKO41BWVIi_NWeuuAAKXD2sbVqa5Sj9WSHEFKu1xAAgBAAMCAAN5AAceBA",
    "words": "AgACAgIAAxkBAAIBSmlX455JcWNX7BxP3AlVOhe9jOqWAAKVD2sbVqa5SrmxcbfkrTxVAAgBAAMCAAN5AAceBA",
    "settings": "AgACAgIAAxkBAAIBTmlX49S2181jAx4n_eNS5SeorGM6AAKYD2sbVqa5SgiV-hlOmjzrAAgBAAMCAAN5AAceBA",
    "faq": "AgACAgIAAxkBAAIBUGlX4-q2atYAAd5BQQg71IQVvXOH3gACmQ9rG1amuUp7QMysM5TuLwAIAQADAgADeQAHHgQ"
}

input_wait = {}
temp_data = {}
processed_groups = []

CACHE_LINKS = {}
CACHE_TEXTS = {}
CACHE_BLACKLIST = []
CACHE_SETTINGS = {}


def reload_cache():
    global CACHE_LINKS, CACHE_TEXTS, CACHE_BLACKLIST, CACHE_SETTINGS
    CACHE_LINKS = {}
    CACHE_TEXTS = {}
    CACHE_BLACKLIST = []
    CACHE_SETTINGS = {}

    all_reps = database.get_replacements()
    for _, r_type, orig, repl in all_reps:
        if r_type == 'link':
            CACHE_LINKS[orig] = repl
        else:
            CACHE_TEXTS[orig] = repl

    all_bl = database.get_blacklist()
    for _, word in all_bl:
        CACHE_BLACKLIST.append(word.lower())

    logs_val = database.get_setting("logs_enabled")
    CACHE_SETTINGS["logs_enabled"] = (logs_val == "1")

    print(f"Кэш обновлен. Логи: {CACHE_SETTINGS['logs_enabled']}")


reload_cache()


async def send_log(text):
    if CACHE_SETTINGS.get("logs_enabled"):
        try:
            await bot.send_message(config.ADMIN_ID, f"🤖 **Лог:**\n{text}")
        except:
            pass


async def edit_menu(message, text, reply_markup=None, photo_key=None):
    try:
        if photo_key and PHOTOS.get(photo_key) and PHOTOS[photo_key].startswith("AgAC"):
            media = InputMediaPhoto(PHOTOS[photo_key], caption=text, parse_mode=ParseMode.MARKDOWN)
            await message.edit_media(media=media, reply_markup=reply_markup)
        else:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except:
        try:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        except:
            pass


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Связать каналы", callback_data="add_bind")],
        [InlineKeyboardButton("⚙️ Управление каналами", callback_data="manage_binds")],
        [InlineKeyboardButton("📝 Редактор слов", callback_data="words_menu")],
        [InlineKeyboardButton("🛠 Настройки", callback_data="settings_menu"),
         InlineKeyboardButton("❓ FAQ / Помощь", callback_data="faq_menu")]
    ])


def settings_menu_kb():
    is_on = CACHE_SETTINGS.get("logs_enabled")
    log_text = "✅ Логи: ВКЛ" if is_on else "❌ Логи: ВЫКЛ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(log_text, callback_data="toggle_logs")],
        [InlineKeyboardButton("📥 Загрузить базу", callback_data="upload_db")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]
    ])


def words_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Слово-ссылка", callback_data="add_link_word"),
         InlineKeyboardButton("➕ Символ", callback_data="add_symbol")],
        [InlineKeyboardButton("⛔ Стоп-слова", callback_data="blacklist_menu")],
        [InlineKeyboardButton("📋 Список замен", callback_data="list_words")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]
    ])


def blacklist_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить стоп-слово", callback_data="add_bl_word")],
        [InlineKeyboardButton("📋 Список", callback_data="list_bl")],
        [InlineKeyboardButton("🔙 Назад", callback_data="words_menu")]
    ])


def faq_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 О боте", callback_data="help_about"),
         InlineKeyboardButton("🔗 Связки", callback_data="help_binds")],
        [InlineKeyboardButton("📝 Слова и ссылки", callback_data="help_words"),
         InlineKeyboardButton("⛔ Стоп-слова", callback_data="help_black")],
        [InlineKeyboardButton("🛠 Настройки", callback_data="help_settings")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]
    ])


def back_to_faq_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к вопросам", callback_data="faq_menu")]])


def bind_detail_kb(bind_id, is_active):
    status_text = "🔴 Выключить" if is_active else "🟢 Включить"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(status_text, callback_data=f"toggle_{bind_id}")],
        [InlineKeyboardButton("📥 Скопировать посты", callback_data=f"copy_posts_{bind_id}")],
        [InlineKeyboardButton("🗑 Удалить связку", callback_data=f"del_{bind_id}")],
        [InlineKeyboardButton("🔙 К списку связок", callback_data="manage_binds")]
    ])


# --- Функции обработки текста ---
def check_blacklist(text):
    if not text:
        return False
    text_lower = text.lower()
    for bad_word in CACHE_BLACKLIST:
        if bad_word in text_lower:
            return True
    return False


def process_text_replacements(text):
    if not text:
        return None, False
    for old, new in CACHE_TEXTS.items():
        text = text.replace(old, new)
    found = False
    for keyword in CACHE_LINKS.keys():
        if keyword.lower() in text.lower():
            found = True
            break
    if not found:
        return text, False
    new_text = text
    for word, link in CACHE_LINKS.items():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        new_text = pattern.sub(f"[{word}]({link})", new_text)
    return new_text, True


# --- Функция копирования одного поста ---
async def copy_single_post(message: Message, dest_id: int, copy_all: bool = False):
    """Копирует один пост в канал назначения с заменами"""
    text = message.text or message.caption or ""

    if check_blacklist(text):
        return False, "blacklist"

    final_text, found = process_text_replacements(text)

    # Если copy_all=True, копируем даже без ключевых слов
    if not found and not copy_all:
        return False, "no_keywords"

    try:
        if message.media:
            await message.copy(dest_id, caption=final_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await userbot.send_message(dest_id, text=final_text, parse_mode=ParseMode.MARKDOWN,
                                       disable_web_page_preview=True)
        return True, "ok"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await copy_single_post(message, dest_id, copy_all)
    except Exception as e:
        return False, str(e)


# --- Функция копирования альбома ---
async def copy_album(messages: list, dest_id: int, copy_all: bool = False):
    """Копирует альбом в канал назначения с заменами"""
    final_media = []
    has_keywords = False

    for msg in messages:
        caption = msg.caption or ""
        if check_blacklist(caption):
            return False, "blacklist"
        new_cap, found = process_text_replacements(caption)
        if found:
            has_keywords = True
        if msg.photo:
            final_media.append(InputMediaPhoto(msg.photo.file_id, caption=new_cap, parse_mode=ParseMode.MARKDOWN))
        elif msg.video:
            final_media.append(InputMediaVideo(msg.video.file_id, caption=new_cap, parse_mode=ParseMode.MARKDOWN))

    # Если copy_all=True, копируем даже без ключевых слов
    if not has_keywords and not copy_all:
        return False, "no_keywords"

    try:
        await userbot.send_media_group(dest_id, final_media)
        return True, "ok"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await copy_album(messages, dest_id, copy_all)
    except Exception as e:
        return False, str(e)


# --- Функция массового копирования постов ---
async def bulk_copy_posts(bind_id: int, count: int, status_message, copy_all: bool = False):
    """Копирует последние N постов из источника в назначение"""
    binds = database.get_binds()
    bind = None
    for b in binds:
        if b[0] == bind_id:
            bind = b
            break

    if not bind:
        return 0, 0, 0

    source_id = bind[1]
    dest_id = bind[2]

    copied = 0
    skipped_bl = 0
    skipped_kw = 0

    try:
        # Шаг 1: Собираем сообщения (от новых к старым)
        messages = []
        fetch_limit = count * 10
        async for msg in userbot.get_chat_history(source_id, limit=fetch_limit):
            messages.append(msg)

        # Шаг 2: Группируем в посты (альбомы = 1 пост)
        posts = []
        processed_groups = set()

        for msg in messages:
            if msg.media_group_id:
                if msg.media_group_id in processed_groups:
                    continue
                processed_groups.add(msg.media_group_id)
                # Собираем весь альбом
                album = [m for m in messages if m.media_group_id == msg.media_group_id]
                # Сортируем по id чтобы порядок фото был правильный
                album.sort(key=lambda x: x.id)
                posts.append({"type": "album", "messages": album, "id": min(m.id for m in album)})
            else:
                posts.append({"type": "single", "message": msg, "id": msg.id})

        # Шаг 3: Берём последние N постов и сортируем от старых к новым
        posts.sort(key=lambda x: x["id"], reverse=True)  # от новых к старым
        posts = posts[:count]  # берём последние N
        posts.reverse()  # теперь от старых к новым

        # Шаг 4: Копируем по порядку
        for i, post in enumerate(posts):
            if post["type"] == "album":
                success, reason = await copy_album(post["messages"], dest_id, copy_all)
            else:
                success, reason = await copy_single_post(post["message"], dest_id, copy_all)

            if success:
                copied += 1
            elif reason == "blacklist":
                skipped_bl += 1
            else:
                skipped_kw += 1

            if (i + 1) % 5 == 0:
                try:
                    await status_message.edit_text(f"⏳ Обработано: {i + 1}/{len(posts)}\n✅ Скопировано: {copied}")
                except:
                    pass

            await asyncio.sleep(random.uniform(1, 3))

        return copied, skipped_bl, skipped_kw
    except Exception as e:
        print(f"Bulk copy error: {e}")
        return copied, skipped_bl, skipped_kw


# --- ОБРАБОТЧИКИ КОМАНД ---

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    text = "👋 **Добро пожаловать в MOLLY GRABBER**\n\nОзнакомиться с функионалом бота можно в FAQ / Помощь."
    if PHOTOS.get("welcome") and PHOTOS["welcome"].startswith("AgAC"):
        try:
            await message.reply_photo(photo=PHOTOS["welcome"], caption=text, reply_markup=main_menu())
            return
        except:
            pass
    await message.reply_text(text, reply_markup=main_menu())


@bot.on_message(filters.command("backup") & filters.user(config.ADMIN_ID))
async def backup_cmd(client, message):
    if os.path.exists("bot_data.db"):
        await message.reply_document("bot_data.db", caption="💾 База данных.")
    else:
        await message.reply("База данных не найдена.")


# --- CALLBACKS ---

@bot.on_callback_query()
async def callbacks(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id

    if data == "main_menu":
        input_wait[user_id] = None
        await edit_menu(callback.message, "🏠 **Главное меню**", main_menu(), "main_menu")

    elif data == "toggle_logs":
        current = CACHE_SETTINGS.get("logs_enabled")
        database.set_setting("logs_enabled", "0" if current else "1")
        reload_cache()
        await callback.message.edit_reply_markup(reply_markup=settings_menu_kb())
        await callback.answer(f"Логи {'ВКЛ' if not current else 'ВЫКЛ'}")

    elif data == "settings_menu":
        await edit_menu(callback.message, "🛠 **Настройки**", settings_menu_kb(), "settings")

    elif data == "words_menu":
        await edit_menu(callback.message, "📝 **Редактор слов**", words_menu_kb(), "words")

    elif data == "blacklist_menu":
        await edit_menu(callback.message, "⛔ **Черный список**", blacklist_menu_kb(), "words")

    elif data == "add_bind":
        input_wait[user_id] = "waiting_bind_ids"
        text = "🔗 **Связывание каналов**\n\nВведите ID каналов через пробел:\n`ОТКУДА КУДА`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]])
        await edit_menu(callback.message, text, kb, "add_bind")

    elif data == "manage_binds":
        binds = database.get_binds()
        if not binds:
            await callback.answer("Связок нет!", show_alert=True)
            return
        kb = []
        for b_id, s_id, d_id, s_t, d_t, active in binds:
            status = "🟢" if active else "🔴"
            src = s_t if s_t else s_id
            dst = d_t if d_t else d_id
            kb.append([InlineKeyboardButton(f"{status} {src} ➡️ {dst}", callback_data=f"bind_detail_{b_id}")])
        kb.append([InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")])
        await edit_menu(callback.message, "⚙️ **Управление связками**\n\nНажмите на связку для управления:",
                        InlineKeyboardMarkup(kb), "manage_binds")

    # --- Детали связки ---
    elif data.startswith("bind_detail_"):
        bind_id = int(data.split("_")[2])
        binds = database.get_binds()
        bind = None
        for b in binds:
            if b[0] == bind_id:
                bind = b
                break
        if not bind:
            await callback.answer("Связка не найдена!", show_alert=True)
            return
        b_id, s_id, d_id, s_t, d_t, active = bind
        status = "🟢 Активна" if active else "🔴 Неактивна"
        src = s_t if s_t else s_id
        dst = d_t if d_t else d_id
        text = f"📌 **Связка #{b_id}**\n\n**Источник:** `{src}`\n**Назначение:** `{dst}`\n**Статус:** {status}"
        await edit_menu(callback.message, text, bind_detail_kb(bind_id, active), "manage_binds")

    # --- Копирование постов ---
    elif data.startswith("copy_posts_"):
        bind_id = int(data.split("_")[2])
        temp_data[user_id] = {"copy_bind_id": bind_id}
        input_wait[user_id] = "waiting_copy_count"
        text = "📥 **Копирование постов**\n\nВведите количество последних постов для копирования (1-100):"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data=f"bind_detail_{bind_id}")]])
        await edit_menu(callback.message, text, kb, "manage_binds")

    elif data.startswith("confirm_copy_"):
        parts = data.split("_")
        bind_id = int(parts[2])
        count = int(parts[3])
        copy_all = parts[4] == "all" if len(parts) > 4 else False

        binds = database.get_binds()
        bind = None
        for b in binds:
            if b[0] == bind_id:
                bind = b
                break

        if not bind:
            await callback.answer("Связка не найдена!", show_alert=True)
            return

        mode_text = "ВСЕ посты" if copy_all else "только с ключевыми словами"
        await callback.answer("⏳ Начинаю копирование...")
        status_msg = await bot.send_message(user_id,
                                            f"⏳ Копирую {count} постов ({mode_text})...\nЭто может занять некоторое время.")

        copied, skipped_bl, skipped_kw = await bulk_copy_posts(bind_id, count, status_msg, copy_all)

        result_text = (
            f"✅ **Копирование завершено!**\n\n"
            f"📊 **Результаты:**\n"
            f"• Скопировано: {copied}\n"
            f"• Пропущено (стоп-слова): {skipped_bl}\n"
            f"• Пропущено (нет ключевых): {skipped_kw}"
        )
        await status_msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 К связке", callback_data=f"bind_detail_{bind_id}")]]))

    elif data.startswith("toggle_"):
        bind_id = int(data.split("_")[1])
        database.toggle_bind(bind_id)
        callback.data = f"bind_detail_{bind_id}"
        await callbacks(client, callback)

    elif data.startswith("del_"):
        bind_id = int(data.split("_")[1])
        database.delete_bind(bind_id)
        await callback.answer("🗑 Связка удалена!")
        callback.data = "manage_binds"
        await callbacks(client, callback)

    # --- FAQ ---
    elif data == "faq_menu":
        await edit_menu(callback.message, "❓ **Часто задаваемые вопросы**\nВыберите тему:", faq_menu_kb(), "faq")

    elif data == "help_about":
        text = ("🤖 **О боте**\n\n"
                "Этот бот – граббер контента. Он автоматически копирует посты из одних каналов в другие.\n\n"
                "**Основные функции:**\n"
                "• Мгновенное копирование постов.\n"
                "• Поддержка альбомов (фото/видео).\n"
                "• Замена текста и ссылок на лету.\n"
                "• Фильтрация ненужного контента.")
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_binds":
        text = ("🔗 **Связки каналов**\n\n"
                "Позволяют настроить маршрут копирования.\n\n"
                "1. Нажмите **Связать каналы**.\n"
                "2. Отправьте ID источника и ID назначения.\n"
                "3. Бот начнет пересылать посты.\n\n"
                "В меню **Управление** можно ставить паузу, удалять связки или копировать прошлые посты.")
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_words":
        text = ("📝 **Слова и ссылки**\n\n"
                "🔹 **Слово-ссылка**: Превращает слово в кликабельную ссылку.\n"
                "Пример: если добавить слово `КУПИТЬ` и ссылку `t.me/user`, то в тексте поста слово КУПИТЬ станет ссылкой.\n\n"
                "🔹 **Символ**: Обычная автозамена текста. Меняет одно слово/фразу на другую.")
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_black":
        text = ("⛔ **Стоп-слова**\n\n"
                "Если в посте будет найдено слово из черного списка, бот **не будет** копировать этот пост.\n\n"
                "Удобно для фильтрации рекламы, спама или чужих упоминаний.")
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_settings":
        text = ("🛠 **Настройки**\n\n"
                "🔹 **Логирование**: Если включено, бот присылает отчеты о каждом посте (скопирован/пропущен) в личку админу.\n"
                "🔹 **Загрузить базу**: Позволяет восстановить настройки из файла `bot_data.db`.")
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "upload_db":
        input_wait[user_id] = "waiting_db_upload"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="settings_menu")]])
        await edit_menu(callback.message, "📂 Отправь файл `bot_data.db`", kb, "settings")

    elif data == "list_words":
        reps = database.get_replacements()
        text = "**Замены:**\n\n" if reps else "Список пуст."
        for r_id, r_type, orig, repl in reps:
            icon = "🔗" if r_type == 'link' else "📣"
            text += f"{icon} `{orig}` ➡️ `{repl}` /delrep_{r_id}\n"
        await edit_menu(callback.message, text, words_menu_kb(), "words")

    elif data == "add_link_word":
        input_wait[user_id] = "wait_link_word"
        await edit_menu(callback.message, "1️⃣ Введите **СЛОВО**:",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="words_menu")]]), "words")

    elif data == "add_symbol":
        input_wait[user_id] = "wait_symbol_orig"
        await edit_menu(callback.message, "1️⃣ Введите **СИМВОЛ**:",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="words_menu")]]), "words")

    elif data == "add_bl_word":
        input_wait[user_id] = "wait_bl_word"
        await edit_menu(callback.message, "🚫 Введите **СТОП-СЛОВО**:",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="blacklist_menu")]]),
                        "words")

    elif data == "list_bl":
        bl = database.get_blacklist()
        text = "**Стоп-слова:**\n\n" if bl else "Пусто."
        for b_id, word in bl:
            text += f"❌ `{word}` /delbl_{b_id}\n"
        await edit_menu(callback.message, text, blacklist_menu_kb(), "words")


# --- УДАЛЕНИЕ ---
@bot.on_message(filters.regex(r"^/delrep_(\d+)$"))
async def del_rep_item(client, message):
    try:
        r_id = int(message.matches[0].group(1))
        database.delete_replacement(r_id)
        reload_cache()
        await message.reply("🗑 Удалено!", reply_markup=words_menu_kb())
    except:
        pass


@bot.on_message(filters.regex(r"^/delbl_(\d+)$"))
async def del_bl_item(client, message):
    try:
        b_id = int(message.matches[0].group(1))
        database.delete_blacklist(b_id)
        reload_cache()
        await message.reply("🗑 Удалено!", reply_markup=blacklist_menu_kb())
    except:
        pass


# --- ВВОД ДАННЫХ ---
@bot.on_message(filters.document & filters.private)
async def handle_document(client, message):
    user_id = message.from_user.id
    if input_wait.get(user_id) == "waiting_db_upload":
        if not message.document.file_name.endswith(".db"):
            await message.reply("Нужен файл .db")
            return
        await message.download("bot_data.db")
        reload_cache()
        await message.reply("✅ База восстановлена!", reply_markup=main_menu())
        input_wait[user_id] = None


@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    state = input_wait.get(user_id)
    if not state:
        return

    if state == "waiting_bind_ids":
        try:
            parts = message.text.split()
            if len(parts) != 2:
                raise ValueError
            src, dst = int(parts[0]), int(parts[1])
            msg = await message.reply("⏳ Ищу названия...")
            try:
                s_t = (await userbot.get_chat(src)).title
            except:
                s_t = str(src)
            try:
                d_t = (await userbot.get_chat(dst)).title
            except:
                d_t = str(dst)
            if database.add_bind(src, dst, s_t, d_t):
                await msg.edit_text(f"✅ Связано: {s_t} -> {d_t}", reply_markup=main_menu())
            else:
                await msg.edit_text("⚠️ Уже есть.", reply_markup=main_menu())
            input_wait[user_id] = None
        except:
            await message.reply("❌ Ошибка ввода ID.")

    elif state == "waiting_copy_count":
        try:
            count = int(message.text)
            if count < 1 or count > 100:
                await message.reply("❌ Введите число от 1 до 100")
                return
            bind_id = temp_data[user_id]["copy_bind_id"]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📝 С ключевыми словами",
                                      callback_data=f"confirm_copy_{bind_id}_{count}_filter")],
                [InlineKeyboardButton(f"📦 ВСЕ посты", callback_data=f"confirm_copy_{bind_id}_{count}_all")],
                [InlineKeyboardButton("🔙 Отмена", callback_data=f"bind_detail_{bind_id}")]
            ])
            await message.reply(
                f"📥 **Копировать {count} постов**\n\n"
                f"Выберите режим:\n\n"
                f"📝 **С ключевыми словами** — только посты где есть слова-ссылки\n"
                f"📦 **ВСЕ посты** — все посты (замены всё равно применяются)\n\n"
                f"⚠️ Посты со стоп-словами пропускаются в любом режиме.",
                reply_markup=kb
            )
            input_wait[user_id] = None
        except ValueError:
            await message.reply("❌ Введите число")

    elif state == "wait_link_word":
        temp_data[user_id] = {'word': message.text}
        input_wait[user_id] = "wait_link_url"
        await message.reply(f"👌 Слово: **{message.text}**\n2️⃣ ССЫЛКА:")

    elif state == "wait_link_url":
        word = temp_data[user_id]['word']
        if database.add_replacement('link', word, message.text):
            reload_cache()
            await message.reply("✅ Сохранено!", reply_markup=words_menu_kb())
        else:
            await message.reply("⚠️ Уже есть.", reply_markup=words_menu_kb())
        input_wait[user_id] = None

    elif state == "wait_symbol_orig":
        temp_data[user_id] = {'orig': message.text}
        input_wait[user_id] = "wait_symbol_new"
        await message.reply(f"👌 Меняем: **{message.text}**\n2️⃣ На что:")

    elif state == "wait_symbol_new":
        orig = temp_data[user_id]['orig']
        if database.add_replacement('text', orig, message.text):
            reload_cache()
            await message.reply("✅ Сохранено!", reply_markup=words_menu_kb())
        else:
            await message.reply("⚠️ Уже есть.", reply_markup=words_menu_kb())
        input_wait[user_id] = None

    elif state == "wait_bl_word":
        if database.add_blacklist(message.text):
            reload_cache()
            await message.reply(f"🚫 `{message.text}` в ЧС.", reply_markup=blacklist_menu_kb())
        else:
            await message.reply("⚠️ Уже есть.", reply_markup=blacklist_menu_kb())
        input_wait[user_id] = None


# --- ЮЗЕРБОТ (ЛОГИКА) ---
@userbot.on_message(filters.channel)
async def source_listener(client, message: Message):
    mapping = database.get_active_sources()
    if message.chat.id not in mapping:
        return
    destinations = mapping[message.chat.id]

    if message.media_group_id:
        if message.media_group_id in processed_groups:
            return
        processed_groups.append(message.media_group_id)
        if len(processed_groups) > 50:
            processed_groups.pop(0)

    delay = random.randint(9, 20)
    await send_log(f"⏳ Обнаружен пост в `{message.chat.title}`\nОжидаю {delay} сек...")
    await asyncio.sleep(delay)

    if message.media_group_id:
        try:
            media_group = await client.get_media_group(message.chat.id, message.id)
        except:
            return
        for dest in destinations:
            # ✅ ДОБАВЛЕНО copy_all=True
            success, reason = await copy_album(media_group, dest, copy_all=True)
            if success:
                await send_log("✅ Альбом скопирован!")
            elif reason == "blacklist":
                await send_log("⛔ Пост пропущен: найдено стоп-слово.")
            else:
                await send_log("⚠️ Пост пропущен: нет ключевых слов.")
    else:
        for dest in destinations:
            # ✅ ДОБАВЛЕНО copy_all=True
            success, reason = await copy_single_post(message, dest, copy_all=True)
            if success:
                await send_log("✅ Пост скопирован!")
            elif reason == "blacklist":
                await send_log("⛔ Пост пропущен: найдено стоп-слово.")
            else:
                await send_log("⚠️ Пост пропущен: нет ключевых слов.")


# --- ЗАПУСК ---
async def main():
    print("Запускаем...")
    await userbot.start()

    # 👇 ДОБАВЛЕННЫЙ БЛОК: ВОССТАНОВЛЕНИЕ ДОСТУПА К КАНАЛАМ 👇
    print("♻️ Восстанавливаем доступ к каналам из базы...")
    try:
        binds = database.get_binds()
        for row in binds:
            # row[1] - ID источника, row[2] - ID назначения
            try:
                # Просто запрашиваем чат, чтобы Pyrogram запомнил его Access Hash
                await userbot.get_chat(row[1])
                await userbot.get_chat(row[2])
            except Exception as e:
                print(f"⚠️ Не удалось обновить доступ к {row[1]} или {row[2]}: {e}")
        print("✅ Доступ восстановлен!")
    except Exception as e:
        print(f"Ошибка при восстановлении доступов: {e}")
    # 👆 КОНЕЦ ДОБАВЛЕННОГО БЛОКА 👆

    await bot.start()
    print("Работаем!")
    await idle()
    await userbot.stop()
    await bot.stop()


@bot.on_message(filters.photo & filters.private)
async def get_photo_id(client, message):
    file_id = message.photo.file_id
    await message.reply(f"ID твоего фото:\n<code>{file_id}</code>", parse_mode=ParseMode.HTML)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())