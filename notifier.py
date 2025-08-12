import html
import hashlib
import logging
import re
from typing import List, Tuple, Optional
from telethon import TelegramClient
from db import has_sent, mark_sent
from textutils import parse_start_hour_from_title, normalize_for_match, strip_decor_prefix

log = logging.getLogger("notifier")

def _html_escape(s: str) -> str:
    return html.escape(s, quote=False)

def _highlight_keywords_html(text: str, kws: List[str]) -> str:
    safe = _html_escape(text)
    # longest-first to avoid nested replacements
    for kw in sorted(set([k for k in kws if k.strip()]), key=len, reverse=True):
        kw_safe = _html_escape(kw)
        safe = re.sub(rf"({re.escape(kw_safe)})", r"<b>\1</b>", safe)
    return safe

def _chips(keywords: List[str]) -> str:
    # Multi-line bullets (as you chose)
    if not keywords:
        return "—"
    items = sorted(set(keywords), key=str.lower)
    return "\n".join(f"📌 {_html_escape(k)}" for k in items)

def sort_sections(sections: List[Tuple[str, List[str]]]) -> List[Tuple[str, List[str]]]:
    with_keys = []
    for s in sections:
        title, body = s
        hour = parse_start_hour_from_title(title)
        with_keys.append((999 if hour is None else hour, title, body))
    with_keys.sort(key=lambda x: x[0])
    return [(t, b) for _, t, b in with_keys]

def format_section_keywords(idx: int,
                            title: str,
                            matched_keywords: List[str],
                            last_update_display: str,
                            ann_display: Optional[str] = None) -> str:
    title_clean = strip_decor_prefix(title)
    title_h = _highlight_keywords_html(title_clean, matched_keywords)
    chips = _chips(matched_keywords)
    footer = []
    if ann_display:
        footer.append(f"📅 <b>{_html_escape(ann_display)}</b>")
    # footer.append(f"⏰ بروزرسانی: <code>{_html_escape(last_update_display)}</code>")
    
    return (
        f"⚡ <b>{title_h}</b>\n\n"
        f"{chips}\n\n"
        + "\n".join(footer)
    )

async def send_long_message(client: TelegramClient, chat_id: int, text: str, chunk_size: int = 3500):
    if len(text) <= chunk_size:
        await client.send_message(chat_id, text, parse_mode="html")
        return
    buf, total, chunks = [], 0, []
    for line in text.split("\n"):
        add = len(line) + 1
        if total + add > chunk_size:
            chunks.append("\n".join(buf)); buf = [line]; total = add
        else:
            buf.append(line); total += add
    if buf:
        chunks.append("\n".join(buf))
    for i, ch in enumerate(chunks, 1):
        suffix = f"\n(بخش پیام {i}/{len(chunks)})" if len(chunks) > 1 else ""
        await client.send_message(chat_id, ch + suffix, parse_mode="html")

async def send_matching_sections(client: TelegramClient,
                                 chat_id: int,
                                 last_update_key: str,
                                 last_update_display: str,
                                 sections: List[Tuple[str, List[str]]],
                                 keywords: List[str],
                                 force_send: bool = False,
                                 ann_display: Optional[str] = None) -> int:
    count = 0
    kw_orig = [k for k in keywords if k.strip()]
    kw_lower = [k.strip().lower() for k in kw_orig]

    sections_sorted = sort_sections(sections)

    for i, (title, body) in enumerate(sections_sorted, start=1):
        # normalized (emoji-free) text for matching
        section_text_norm = normalize_for_match(title + "\n" + "\n".join(body))
        matched_idx = [idx for idx, k in enumerate(kw_lower) if k and (k in section_text_norm)]
        if not matched_idx:
            continue
        matched_keywords = [kw_orig[idx] for idx in matched_idx]

        # dedupe key on raw content (stable)
        sh = hashlib.sha256((title + "\n" + "\n".join(body)).encode("utf-8", "ignore")).hexdigest()[:24]
        if (not force_send) and has_sent(chat_id, last_update_key, sh):
            log.debug("skip sent | chat=%s lu=%s hash=%s", chat_id, last_update_key, sh)
            continue

        msg = format_section_keywords(i, title, matched_keywords, last_update_display, ann_display)
        try:
            await send_long_message(client, chat_id, msg)
            mark_sent(chat_id, last_update_key, sh, title)
            count += 1
            log.info("sent | chat=%s lu=%s hash=%s keys=%s", chat_id, last_update_key, sh, matched_keywords)
        except Exception as e:
            log.exception("send failed | chat=%s err=%s", chat_id, e)
    return count
