# database.py
import sqlite3


def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    # Таблица связок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS binds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            dest_id INTEGER,
            source_title TEXT,
            dest_title TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Таблица замен
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replacements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            r_type TEXT,
            original TEXT,
            replacement TEXT
        )
    ''')

    # Таблица черный список
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT
        )
    ''')

    # --- НОВАЯ ТАБЛИЦА: НАСТРОЙКИ ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    conn.commit()
    conn.close()


# --- ФУНКЦИИ СВЯЗОК ---
def add_bind(source, dest, s_title, d_title):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM binds WHERE source_id = ? AND dest_id = ?", (source, dest))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO binds (source_id, dest_id, source_title, dest_title) VALUES (?, ?, ?, ?)",
                       (source, dest, s_title, d_title))
        conn.commit()
        res = True
    else:
        res = False
    conn.close()
    return res


def get_binds():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_id, dest_id, source_title, dest_title, is_active FROM binds")
    rows = cursor.fetchall()
    conn.close()
    return rows


def toggle_bind(bind_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM binds WHERE id = ?", (bind_id,))
    res = cursor.fetchone()
    if res:
        new = 0 if res[0] == 1 else 1
        cursor.execute("UPDATE binds SET is_active = ? WHERE id = ?", (new, bind_id))
        conn.commit()
        conn.close()
        return new
    conn.close()
    return None


def delete_bind(bind_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM binds WHERE id = ?", (bind_id,))
    conn.commit()
    conn.close()


def get_active_sources():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT source_id, dest_id FROM binds WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    mapping = {}
    for src, dst in rows:
        if src not in mapping: mapping[src] = []
        mapping[src].append(dst)
    return mapping


# --- ФУНКЦИИ ЗАМЕН ---
def add_replacement(r_type, original, replacement):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM replacements WHERE original = ?", (original,))
    if cursor.fetchone():
        conn.close()
        return False
    cursor.execute("INSERT INTO replacements (r_type, original, replacement) VALUES (?, ?, ?)",
                   (r_type, original, replacement))
    conn.commit()
    conn.close()
    return True


def get_replacements():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, r_type, original, replacement FROM replacements")
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_replacement(r_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM replacements WHERE id = ?", (r_id,))
    conn.commit()
    conn.close()


# --- ФУНКЦИИ ЧЕРНОГО СПИСКА ---
def add_blacklist(word):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blacklist WHERE word = ?", (word,))
    if cursor.fetchone():
        conn.close()
        return False
    cursor.execute("INSERT INTO blacklist (word) VALUES (?)", (word,))
    conn.commit()
    conn.close()
    return True


def get_blacklist():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, word FROM blacklist")
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_blacklist(b_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blacklist WHERE id = ?", (b_id,))
    conn.commit()
    conn.close()


# --- НОВЫЕ ФУНКЦИИ (НАСТРОЙКИ) ---
def set_setting(key, value):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None