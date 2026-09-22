import sqlite3

DB_NAME = "vocab.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabularies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            word TEXT,
            word_type TEXT,
            vietnamese TEXT,
            unit TEXT DEFAULT 'Unit 2',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_word(user_id, word, word_type, vietnamese, unit="Unit 2"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vocabularies (user_id, word, word_type, vietnamese, unit)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, word.strip(), word_type.strip(), vietnamese.strip(), unit.strip()))
    conn.commit()
    conn.close()

def get_words(user_id, unit=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if unit:
        cursor.execute("SELECT id, word, word_type, vietnamese, unit FROM vocabularies WHERE user_id = ? AND unit = ?", (user_id, unit))
    else:
        cursor.execute("SELECT id, word, word_type, vietnamese, unit FROM vocabularies WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows
