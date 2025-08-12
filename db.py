import sqlite3
import time
from contextlib import closing
from typing import List, Optional, Tuple
from config import DB_PATH
import logging

log = logging.getLogger("db")

def init():
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            chat_id INTEGER PRIMARY KEY,
            url TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        );
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS keywords(
            chat_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            UNIQUE(chat_id, keyword)
        );
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS sent_sections(
            chat_id INTEGER NOT NULL,
            last_update TEXT NOT NULL,
            section_hash TEXT NOT NULL,
            title TEXT,
            sent_at INTEGER NOT NULL,
            PRIMARY KEY(chat_id, last_update, section_hash)
        );
        """)
        con.commit()
    log.info("DB initialized at %s", DB_PATH)

def get_setting(key: str) -> Optional[str]:
    with closing(sqlite3.connect(DB_PATH)) as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

def set_setting(key: str, value: str):
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("""
            INSERT INTO settings(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        con.commit()

def upsert_chat(chat_id: int):
    with closing(sqlite3.connect(DB_PATH)) as con:
        now = int(time.time())
        row = con.execute("SELECT chat_id FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            con.execute("INSERT INTO chats(chat_id,url,created_at) VALUES(?,?,?)",
                        (chat_id, "", now))
        con.commit()
    log.debug("chat upserted | chat=%s", chat_id)

def add_keyword(chat_id: int, kw: str) -> bool:
    kw = kw.strip()
    if not kw:
        return False
    with closing(sqlite3.connect(DB_PATH)) as con:
        try:
            con.execute("INSERT INTO keywords(chat_id, keyword) VALUES(?,?)", (chat_id, kw))
            con.commit()
            log.info("keyword added | chat=%s kw=%s", chat_id, kw)
            return True
        except sqlite3.IntegrityError:
            return False

def del_keyword(chat_id: int, kw: str) -> bool:
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute("DELETE FROM keywords WHERE chat_id=? AND keyword=?", (chat_id, kw))
        con.commit()
        ok = cur.rowcount > 0
        if ok:
            log.info("keyword deleted | chat=%s kw=%s", chat_id, kw)
        return ok

def list_keywords(chat_id: int) -> List[str]:
    with closing(sqlite3.connect(DB_PATH)) as con:
        rows = con.execute("SELECT keyword FROM keywords WHERE chat_id=? ORDER BY keyword", (chat_id,)).fetchall()
        return [r[0] for r in rows]

def list_chats() -> List[Tuple[int, str, int]]:
    with closing(sqlite3.connect(DB_PATH)) as con:
        return con.execute("SELECT chat_id, url, created_at FROM chats ORDER BY created_at DESC").fetchall()

def has_sent(chat_id: int, last_update: str, section_hash: str) -> bool:
    with closing(sqlite3.connect(DB_PATH)) as con:
        row = con.execute("""
            SELECT 1 FROM sent_sections WHERE chat_id=? AND last_update=? AND section_hash=?
        """, (chat_id, last_update, section_hash)).fetchone()
        return bool(row)

def mark_sent(chat_id: int, last_update: str, section_hash: str, title: str):
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute("""
            INSERT OR IGNORE INTO sent_sections(chat_id,last_update,section_hash,title,sent_at)
            VALUES(?,?,?,?,?)
        """, (chat_id, last_update, section_hash, title, int(time.time())))
        con.commit()
    log.debug("marked sent | chat=%s lu=%s hash=%s", chat_id, last_update, section_hash)

def stats():
    with closing(sqlite3.connect(DB_PATH)) as con:
        total_sent = con.execute("SELECT COUNT(*) FROM sent_sections").fetchone()[0]
        per_chat = con.execute(
            "SELECT chat_id, COUNT(*) FROM sent_sections GROUP BY chat_id ORDER BY COUNT(*) DESC"
        ).fetchall()
    return total_sent, per_chat
