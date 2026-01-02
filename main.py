# main.py
import re
import asyncio
import os
import random
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, \
    InputMediaVideo
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified

import config
import database

# Инициализация БД
database.init_db()

# --- Клиенты ---
userbot = Client("my_userbot", api_id=config.API_ID, api_hash=config.API_HASH)
bot = Client("my_admin_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# --- 🖼 НАСТРОЙКИ КАРТИНОК ---
# Вставь сюда ID своих картинок, которые получишь через бота
PHOTOS = {
    "welcome": "AgACAgIAAxkBAANQaVe-3Zy52Y1ZTdcyMqI3-P4K3bsAAhIPaxv0ZrhKL5SyfYdHoaEACAEAAwIAA3kABx4E",
    "main_menu": "AgACAgIAAxkBAAIBRGlX4v2mfFPMPH7o79CGyLU40uGBAAKTD2sbVqa5SsN29VVa_i0DAAgBAAMCAAN5AAceBA",
    "add_bind": "AgACAgIAAxkBAAIBRmlX4xhHeeLAM8ZmJBHP8h7hbGEkAAKUD2sbVqa5Srvwnh4-Y08ACQEAAwIAA3kABx4E",
    "manage_binds": "AgACAgIAAxkBAAIBTGlX47r1obGDGKO41BWVIi_NWeuuAAKXD2sbVqa5Sj9WSHEFKu1xAAgBAAMCAAN5AAceBA",
    "words": "AgACAgIAAxkBAAIBSmlX455JcWNX7BxP3AlVOhe9jOqWAAKVD2sbVqa5SrmxcbfkrTxVAAgBAAMCAAN5AAceBA",
    "settings": "AgACAgIAAxkBAAIBTmlX49S2181jAx4n_eNS5SeorGM6AAKYD2sbVqa5SgiV-hlOmjzrAAgBAAMCAAN5AAceBA",
    "faq": "AgACAgIAAxkBAAIBUGlX4-q2atYAAd5BQQg71IQVvXOH3gACmQ9rG1amuUp7QMysM5TuLwAIAQADAgADeQAHHgQ"
}

# --- Глобальные переменные ---
input_wait = {}
temp_data = {}
processed_groups = []

# КЭШ
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


# --- ЛОГИРОВАНИЕ ---
async def send_log(text):
    if CACHE_SETTINGS.get("logs_enabled"):
        try:
            await bot.send_message(config.ADMIN_ID, f"🤖 **Лог:**\n{text}")
        except:
            pass


# --- ФУНКЦИЯ ПЛАВНОЙ СМЕНЫ МЕНЮ ---
async def edit_menu(message, text, reply_markup=None, photo_key=None):
    """Меняет картинку и текст. Если photo_key есть в PHOTOS — меняет фото."""
    try:
        # Если передан ключ фото и он есть в настройках
        if photo_key and PHOTOS.get(photo_key) and PHOTOS[photo_key].startswith("AgAC"):
            media = InputMediaPhoto(PHOTOS[photo_key], caption=text, parse_mode=ParseMode.MARKDOWN)
            await message.edit_media(media=media, reply_markup=reply_markup)
        else:
            # Если фото менять не надо или ID нет
            await message.edit_caption(caption=text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except Exception as e:
        try:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        except:
            pass


# --- МЕНЮ (КЛАВИАТУРЫ) ---

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


# --- ОБРАБОТЧИКИ КОМАНД ---

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    text = "👋 **Добро пожаловать в MOLLY GRABBER**\n\nОзнакомиться с функицоналом бота можно в FAQ / Помощь."
    # Пробуем отправить с картинкой Welcome
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


# --- CALLBACKS (МЕНЮ) ---

@bot.on_callback_query()
async def callbacks(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id

    # === ГЛАВНЫЕ РАЗДЕЛЫ (Смена картинок) ===

    if data == "main_menu":
        input_wait[user_id] = None
        await edit_menu(callback.message, "🏠 **Главное меню**", main_menu(), "main_menu")

    elif data == "settings_menu":
        await edit_menu(callback.message, "🛠 **Настройки**", settings_menu_kb(), "settings")

    elif data == "words_menu":
        await edit_menu(callback.message, "📝 **Редактор слов**", words_menu_kb(), "words")

    elif data == "blacklist_menu":
        # Используем ту же картинку, что и для слов, или можно добавить отдельную
        await edit_menu(callback.message, "⛔ **Черный список**", blacklist_menu_kb(), "words")

    elif data == "add_bind":
        input_wait[user_id] = "waiting_bind_ids"
        text = "🔗 **Связывание каналов**\n\nВведите ID каналов через пробел:\n`ОТКУДА КУДА`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]])
        await edit_menu(callback.message, text, kb, "binds")

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
            kb.append([InlineKeyboardButton(f"{src} ➡️ {dst}", callback_data=f"toggle_{b_id}")])
            kb.append([InlineKeyboardButton(f"{status} Статус", callback_data=f"toggle_{b_id}"),
                       InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{b_id}")])
        kb.append([InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")])
        await edit_menu(callback.message, "⚙️ **Управление связками**", InlineKeyboardMarkup(kb), "manage")

    # === FAQ РАЗДЕЛ (Смена картинки на FAQ) ===

    elif data == "faq_menu":
        await edit_menu(callback.message, "❓ **Часто задаваемые вопросы**\nВыберите тему:", faq_menu_kb(), "faq")

    # === ОТВЕТЫ FAQ (Текст меняется, картинка FAQ остается) ===

    elif data == "help_about":
        text = (
            "🤖 **О боте**\n\n"
            "Этот бот — граббер контента. Он автоматически копирует посты из одних каналов в другие.\n\n"
            "**Основные функции:**\n"
            "• Мгновенное копирование постов.\n"
            "• Поддержка альбомов (фото/видео).\n"
            "• Замена текста и ссылок на лету.\n"
            "• Фильтрация ненужного контента."
        )
        await edit_menu(callback.message, text, back_to_faq_kb())  # Картинка не меняется (остается FAQ)

    elif data == "help_binds":
        text = (
            "🔗 **Связки каналов**\n\n"
            "Позволяют настроить маршрут копирования.\n\n"
            "1. Нажмите **Связать каналы**.\n"
            "2. Отправьте ID источника и ID назначения.\n"
            "3. Бот начнет пересылать посты.\n\n"
            "В меню **Управление** можно ставить паузу или удалять связки."
        )
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_words":
        text = (
            "📝 **Слова и ссылки**\n\n"
            "🔹 **Слово-ссылка**: Превращает слово в кликабельную ссылку.\n"
            "Пример: если добавить слово `КУПИТЬ` и ссылку `t.me/user`, то в тексте поста слово КУПИТЬ станет ссылкой.\n\n"
            "🔹 **Символ**: Обычная автозамена текста. Меняет одно слово/фразу на другую."
        )
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_black":
        text = (
            "⛔ **Стоп-слова**\n\n"
            "Если в посте будет найдено слово из черного списка, бот **не будет** копировать этот пост.\n\n"
            "Удобно для фильтрации рекламы, спама или чужих упоминаний."
        )
        await edit_menu(callback.message, text, back_to_faq_kb())

    elif data == "help_settings":
        text = (
            "🛠 **Настройки**\n\n"
            "🔹 **Логирование**: Если включено, бот присылает отчеты о каждом посте (скопирован/пропущен) в личку админу.\n"
            "🔹 **Загрузить базу**: Позволяет восстановить настройки из файла `bot_data.db`."
        )
        await edit_menu(callback.message, text, back_to_faq_kb())


    # === ФУНКЦИОНАЛ (Без смены картинок, если не указано) ===

    elif data == "toggle_logs":
        current = CACHE_SETTINGS.get("logs_enabled")
        database.set_setting("logs_enabled", "0" if current else "1")
        reload_cache()
        await callback.message.edit_reply_markup(reply_markup=settings_menu_kb())
        await callback.answer(f"Логи {'ВКЛ' if not current else 'ВЫКЛ'}")

    elif data == "upload_db":
        input_wait[user_id] = "waiting_db_upload"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="settings_menu")]])
        await edit_menu(callback.message, "📂 Отправь файл `bot_data.db`", kb, "settings")

    elif data.startswith("toggle_"):
        database.toggle_bind(int(data.split("_")[1]))
        callback.data = "manage_binds"
        await callbacks(client, callback)

    elif data.startswith("del_"):
        database.delete_bind(int(data.split("_")[1]))
        callback.data = "manage_binds"
        await callbacks(client, callback)

    elif data == "list_words":
        reps = database.get_replacements()
        text = "**Замены:**\n\n" if reps else "Список пуст."
        for r_id, r_type, orig, repl in reps:
            icon = "🔗" if r_type == 'link' else "🔣"
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
    if not state: return

    if state == "waiting_bind_ids":
        try:
            parts = message.text.split()
            if len(parts) != 2: raise ValueError
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
def check_blacklist(text):
    if not text: return False
    text_lower = text.lower()
    for bad_word in CACHE_BLACKLIST:
        if bad_word in text_lower: return True
    return False


def process_text_replacements(text):
    if not text: return None, False
    for old, new in CACHE_TEXTS.items():
        text = text.replace(old, new)
    found = False
    for keyword in CACHE_LINKS.keys():
        if keyword.lower() in text.lower():
            found = True
            break
    if not found: return text, False
    new_text = text
    for word, link in CACHE_LINKS.items():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        new_text = pattern.sub(f"[{word}]({link})", new_text)
    return new_text, True


@userbot.on_message(filters.channel)
async def source_listener(client, message: Message):
    mapping = database.get_active_sources()
    if message.chat.id not in mapping: return
    destinations = mapping[message.chat.id]

    if message.media_group_id:
        if message.media_group_id in processed_groups: return
        processed_groups.append(message.media_group_id)
        if len(processed_groups) > 50: processed_groups.pop(0)

    delay = random.randint(9, 20)
    await send_log(f"⏳ Обнаружен пост в `{message.chat.title}`\nОжидаю {delay} сек...")
    await asyncio.sleep(delay)

    if message.media_group_id:
        try:
            media_group = await client.get_media_group(message.chat.id, message.id)
        except:
            return
        final_media = []
        has_keywords = False
        is_blacklisted = False
        for msg in media_group:
            caption = msg.caption or ""
            if check_blacklist(caption):
                is_blacklisted = True
                break
            new_cap, found = process_text_replacements(caption)
            if found: has_keywords = True
            if msg.photo:
                final_media.append(InputMediaPhoto(msg.photo.file_id, caption=new_cap, parse_mode=ParseMode.MARKDOWN))
            elif msg.video:
                final_media.append(InputMediaVideo(msg.video.file_id, caption=new_cap, parse_mode=ParseMode.MARKDOWN))
        if is_blacklisted:
            await send_log("⛔ Пост пропущен: найдено стоп-слово.")
            return
        if has_keywords:
            for dest in destinations:
                try:
                    await client.send_media_group(dest, final_media)
                    await send_log("✅ Альбом скопирован!")
                except Exception as e:
                    print(f"Err Group: {e}")
        else:
            await send_log("⚠️ Пост пропущен: нет ключевых слов.")
    else:
        text = message.text or message.caption or ""
        if check_blacklist(text):
            await send_log("⛔ Пост пропущен: найдено стоп-слово.")
            return
        final_text, found = process_text_replacements(text)
        if found:
            for dest in destinations:
                try:
                    if message.media:
                        await message.copy(dest, caption=final_text, parse_mode=ParseMode.MARKDOWN)
                    else:
                        await client.send_message(dest, text=final_text, parse_mode=ParseMode.MARKDOWN,
                                                  disable_web_page_preview=True)
                    await send_log("✅ Пост скопирован!")
                except Exception as e:
                    print(f"Err Single: {e}")
        else:
            await send_log("⚠️ Пост пропущен: нет ключевых слов.")


# --- ЗАПУСК ---
async def main():
    print("Запускаем...")
    await userbot.start()
    await bot.start()
    print("Работаем!")
    await idle()
    await userbot.stop()
    await bot.stop()


# --- ПОМОЩНИК ДЛЯ ID КАРТИНОК ---
@bot.on_message(filters.photo & filters.private)
async def get_photo_id(client, message):
    file_id = message.photo.file_id
    await message.reply(f"ID твоего фото (копируй и вставляй в скрипт):\n<code>{file_id}</code>",
                        parse_mode=ParseMode.HTML)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())