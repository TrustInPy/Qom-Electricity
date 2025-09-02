import re
import logging
from datetime import datetime
from telethon import events
from config import ADMIN_USER_ID, DEFAULT_URL
import db
from crawler import crawl, page_signature
from notifier import send_matching_sections, send_long_message

log = logging.getLogger("commands")

GROUP_HELP = (
    "دستورات گروه:\n"
    "• /start — فعال‌سازی ربات برای این گروه\n"
    "• /help — نمایش راهنما\n"
    "• /addkw <کلیدواژه> — افزودن کلیدواژه برای این گروه\n"
    "• /delkw <کلیدواژه> — حذف کلیدواژه\n"
    "• /listkw — نمایش کلیدواژه‌های ثبت‌شده\n"
    "• /check — اجرای بررسی دستی\n"
    "\n"
    "جهت پیدا کردن کلید واژه باید از <a href='https://qepd.co.ir/fa-IR/DouranPortal/6423/page/%D8%AE%D8%A7%D9%85%D9%88%D8%B4%DB%8C-%D9%87%D8%A7'>این صفحه</a> اقدام کنید."
)

ADMIN_HELP = (
    "دستورات مدیریت (فقط PV ادمین):\n"
    "• /admin — نمایش این راهنما\n"
    "• /stats — آمار کلی (آخرین کلید، تعداد گروه‌ها، تعداد ارسال‌ها)\n"
    "• /lastupdate — نمایش آخرین کلید به‌روزرسانی ثبت‌شده\n"
    "• /listchats — فهرست گروه‌های ثبت‌شده\n"
    "• /showchat <chat_id> — نمایش وضعیت یک گروه (کلیدواژه‌ها)\n"
    "• /listkw_chat <chat_id> — لیست کلیدواژه‌های یک گروه\n"
    "• /addkw_chat <chat_id> <kw> — افزودن کلیدواژه برای گروه\n"
    "• /delkw_chat <chat_id> <kw> — حذف کلیدواژه از گروه\n"
    "• /forcecrawl — مجبور کردن دور بعدی برای بررسی به عنوان به‌روزرسانی جدید\n"
    "• /dumpdb — دریافت فایل پایگاه داده (bot.db)\n"
)

def is_admin(event) -> bool:
    return event.is_private and (event.sender_id == ADMIN_USER_ID)

def register(client):
    @client.on(events.NewMessage(pattern=r"^/start"))
    async def start_handler(event):
        if event.is_group or event.is_channel:
            db.upsert_chat(event.chat_id)
            await event.reply("ربات برای این گروه فعال شد. برای راهنما: /help")
            log.info("group registered | chat=%s", event.chat_id)

    @client.on(events.NewMessage(pattern=r"^/help$"))
    async def help_handler(event):
        if event.is_group or event.is_channel:
            await event.reply(GROUP_HELP, parse_mode="html")

    @client.on(events.NewMessage(pattern=r"^/addkw\s+(.+)$"))
    async def addkw_handler(event):
        if not (event.is_group or event.is_channel):
            return
        kw = event.pattern_match.group(1).strip()
        db.upsert_chat(event.chat_id)
        ok = db.add_keyword(event.chat_id, kw)
        if not ok:
            await event.reply("از قبل وجود دارد یا نامعتبر بود.")
            return
    
        # Added successfully — do an immediate one-off check for THIS kw only
        try:
            last_update, sections, ann_display, ann_key = await crawl(DEFAULT_URL)
        except Exception as e:
            await event.reply("افزوده شد ✅\n(بررسی فوری ناموفق بود)")
            return
    
        if not sections:
            await event.reply("افزوده شد ✅\n(موردی در صفحه یافت نشد)")
            return
    
        last_key = ann_key or last_update or page_signature(sections)
        last_display = last_update if last_update else "نامشخص (شناسه محتوا)"
    
        # Force-send but only for the newly added keyword to avoid re-sending old ones
        sent = await send_matching_sections(
            client=event.client,
            chat_id=event.chat_id,
            last_update_key=last_key,
            last_update_display=last_display,
            sections=sections,
            keywords=[kw],
            force_send=True,
            ann_display=ann_display,
        )
    
        if sent:
            await event.reply(f"افزوده شد ✅\n{sent} مورد مطابق «{kw}» ارسال شد.")
        else:
            await event.reply(f"افزوده شد ✅\n(موردی مطابق «{kw}» پیدا نشد)")
    

    @client.on(events.NewMessage(pattern=r"^/delkw\s+(.+)$"))
    async def delkw_handler(event):
        if not (event.is_group or event.is_channel): return
        kw = event.pattern_match.group(1).strip()
        ok = db.del_keyword(event.chat_id, kw)
        await event.reply("حذف شد ✅" if ok else "پیدا نشد.")

    @client.on(events.NewMessage(pattern=r"^/listkw$"))
    async def listkw_handler(event):
        if not (event.is_group or event.is_channel): return
        kws = db.list_keywords(event.chat_id)
        if not kws:
            await event.reply("هنوز کلیدواژه‌ای ثبت نشده.")
        else:
            await event.reply("کلیدواژه‌ها:\n- " + "\n- ".join(kws))

    @client.on(events.NewMessage(pattern=r"^/check$"))
    async def check_handler(event):
        # anyone can use; send items regardless of previous sends
        if not (event.is_group or event.is_channel): return
        try:
            kws = db.list_keywords(event.chat_id)
            if not kws:
                await event.reply("کلیدواژه‌ای ثبت نشده."); return

            try:
                last_update, sections, ann_display, ann_key = await crawl(DEFAULT_URL)
            except Exception as e:
                await event.reply(f"خطا در دریافت داده: {e}")
                log.exception("check: crawl failed | chat=%s", event.chat_id)
                return

            if not sections:
                await event.reply("موردی یافت نشد."); return

            last_key = ann_key or last_update or page_signature(sections)
            last_display = last_update if last_update else "نامشخص (شناسه محتوا)"

            await send_matching_sections(client, event.chat_id, last_key, last_display, sections, kws,
                                         force_send=True, ann_display=ann_display)
        except Exception as e:
            await event.reply(f"خطا: {e}")
            log.exception("check handler error | chat=%s", event.chat_id)

    # ---------- Admin ----------
    @client.on(events.NewMessage(pattern=r"^/admin$", func=is_admin))
    async def admin_help(event):
        await event.reply(ADMIN_HELP)

    @client.on(events.NewMessage(pattern=r"^/stats$", func=is_admin))
    async def admin_stats(event):
        last = db.get_setting("last_update_seen") or "—"
        chats = db.list_chats()
        total_sent, per_chat = db.stats()
        lines = [
            f"LastUpdateKey: {last}",
            f"Total chats: {len(chats)}",
            f"Total sent sections: {total_sent}",
            "Per chat:",
        ] + [f"- {cid}: {cnt}" for cid, cnt in per_chat] or ["(none)"]
        await event.reply("\n".join(lines))

    @client.on(events.NewMessage(pattern=r"^/lastupdate$", func=is_admin))
    async def admin_lastupdate(event):
        await event.reply(f"LastUpdateKey: {db.get_setting('last_update_seen') or '—'}")

    @client.on(events.NewMessage(pattern=r"^/listchats$", func=is_admin))
    async def admin_listchats(event):
        chats = db.list_chats()
        if not chats:
            await event.reply("No chats registered."); return
        out = []
        for chat_id, _url, created_at in chats:
            dt = datetime.fromtimestamp(created_at).isoformat(sep=" ", timespec="seconds")
            try:
                entity = await client.get_entity(chat_id)
                chat_name = entity.title if hasattr(entity, "title") else entity.first_name
            except Exception:
                chat_name = "?"
            out.append(f"{chat_name} ({chat_id}) | joined={dt}")

        await event.reply("\n".join(out))

    @client.on(events.NewMessage(pattern=r"^/showchat\s+(-?\d+)$", func=is_admin))
    async def admin_showchat(event):
        chat_id = int(event.pattern_match.group(1))
        kws = db.list_keywords(chat_id)
        await event.reply(f"Chat: {chat_id}\nKeywords:\n- " + ("\n- ".join(kws) if kws else "(none)"))

    @client.on(events.NewMessage(pattern=r"^/listkw_chat\s+(-?\d+)$", func=is_admin))
    async def admin_listkw_chat(event):
        chat_id = int(event.pattern_match.group(1))
        kws = db.list_keywords(chat_id)
        await event.reply("Keywords:\n- " + ("\n- ".join(kws) if kws else "(none)"))

    @client.on(events.NewMessage(pattern=r"^/addkw_chat\s+(-?\d+)\s+(.+)$", func=is_admin))
    async def admin_addkw_chat(event):
        chat_id = int(event.pattern_match.group(1))
        kw = event.pattern_match.group(2).strip()
        db.upsert_chat(chat_id)
        ok = db.add_keyword(chat_id, kw)
        if not ok:
            await event.reply("Already exists or invalid.")
            return

        # Try immediate crawl for the newly added keyword
        try:
            last_update, sections, ann_display, ann_key = await crawl(DEFAULT_URL)
        except Exception as e:
            await event.reply("Added ✅\n(Immediate check failed)")
            return

        if not sections:
            await event.reply("Added ✅\n(No sections found)")
            return

        last_key = ann_key or last_update or page_signature(sections)
        last_display = last_update if last_update else "نامشخص (شناسه محتوا)"

        sent = await send_matching_sections(
            client=event.client,
            chat_id=chat_id,
            last_update_key=last_key,
            last_update_display=last_display,
            sections=sections,
            keywords=[kw],
            force_send=True,
            ann_display=ann_display,
        )

        if sent:
            await event.reply(f"Added ✅\n{sent} section(s) sent to {chat_id} for keyword «{kw}».")
        else:
            await event.reply(f"Added ✅\n(No matches found for «{kw}»)")


    @client.on(events.NewMessage(pattern=r"^/delkw_chat\s+(-?\d+)\s+(.+)$", func=is_admin))
    async def admin_delkw_chat(event):
        chat_id = int(event.pattern_match.group(1))
        kw = event.pattern_match.group(2).strip()
        ok = db.del_keyword(chat_id, kw)
        await event.reply("Deleted ✅" if ok else "Not found.")

    @client.on(events.NewMessage(pattern=r"^/forcecrawl$", func=is_admin))
    async def admin_forcecrawl(event):
        db.set_setting("last_update_seen", "")
        await event.reply("Next cycle will treat as new update. ✅")

    @client.on(events.NewMessage(pattern=r"^/dumpdb$", func=is_admin))
    async def admin_dumpdb(event):
        from config import DB_PATH
        import os
        if os.path.exists(DB_PATH):
            await event.client.send_file(event.chat_id, DB_PATH, caption="bot.db")
        else:
            await event.reply("DB file not found.")

    # ---- helper: resolve chat title for pretty listing ----
    async def _chat_title(client, chat_id: int) -> str:
        try:
            ent = await client.get_entity(chat_id)
            if hasattr(ent, "title") and ent.title:
                return ent.title
            if hasattr(ent, "first_name") and ent.first_name:
                return ent.first_name
            return "?"
        except Exception:
            return "?"

    # ===== List groups =====
    @client.on(events.NewMessage(pattern=r"^/groups$", func=is_admin))
    async def admin_list_groups(event):
        chats = db.list_chats()
        if not chats:
            await event.reply("هیچ گروهی ثبت نشده.")
            return
        lines = []
        for chat_id, _url, created_at in chats:
            name = await _chat_title(event.client, chat_id)
            lines.append(f"• {name} ({chat_id})")
        # طول پیام را کنترل کنیم
        text = "گروه‌های ثبت‌شده:\n" + "\n".join(lines)
        if len(text) > 3500:
            text = text[:3500] + "\n..."
        await event.reply(text)

    # ---- extract text: from inline args OR from replied message ----
    def _extract_broadcast_text(event, inline_text: str) -> str:
        if inline_text:
            return inline_text.strip()
        # اگر ریپلای کرده بود
        if event.is_reply:
            # فقط متن ساده را برمی‌داریم (بدون مدیا)
            return (event.message.reply_to_msg_id and "") or ""
        return ""

    # نسخه بهتر: ریپلای را به‌طور مطمئن بخوانیم
    async def _get_broadcast_text(event, inline_text: str):
        inline_text = (inline_text or "").strip()
        if inline_text:
            return inline_text
        if event.is_reply:
            try:
                reply = await event.get_reply_message()
                if reply and (reply.message or "").strip():
                    return reply.message.strip()
            except Exception:
                pass
        return ""

    # ===== Broadcast to ALL groups =====
    @client.on(events.NewMessage(pattern=r"^/broadcast_all(?:\s+(.+))?$", func=is_admin))
    async def admin_broadcast_all(event):
        msg_text = await _get_broadcast_text(event, (event.pattern_match.group(1) or ""))
        if not msg_text:
            await event.reply("متنی برای ارسال پیدا نشد. یا بعد از دستور بنویسید یا روی پیام ریپلای کنید.")
            return

        chats = db.list_chats()
        if not chats:
            await event.reply("هیچ گروهی ثبت نشده.")
            return

        ok, fail = 0, 0
        for chat_id, _url, _created in chats:
            try:
                await send_long_message(event.client, chat_id, msg_text)
                ok += 1
            except Exception as e:
                fail += 1
        await event.reply(f"ارسال به همه انجام شد. موفق: {ok} | ناموفق: {fail}")

    # ===== Broadcast to selected groups by IDs =====
    # شکل ۱: /broadcast -100123,-100456 سلام
    # شکل ۲: (ریپلای به یک پیام) /broadcast -100123,-100456
    @client.on(events.NewMessage(pattern=r"^/broadcast\s+([-,\d ]+)(?:\s+(.+))?$", func=is_admin))
    async def admin_broadcast_selected(event):
        raw_ids = (event.pattern_match.group(1) or "").strip()
        msg_text = await _get_broadcast_text(event, (event.pattern_match.group(2) or ""))
        if not msg_text:
            await event.reply("متنی برای ارسال پیدا نشد. یا بعد از دستور بنویسید یا روی پیام ریپلای کنید.")
            return

        # parse IDs: allow spaces and commas
        ids = []
        for tok in re.split(r"[,\s]+", raw_ids):
            tok = tok.strip()
            if not tok:
                continue
            try:
                ids.append(int(tok))
            except ValueError:
                pass

        if not ids:
            await event.reply("هیچ chat_id معتبری ارائه نشد.")
            return

        ok, fail = 0, 0
        for cid in ids:
            try:
                await send_long_message(event.client, cid, msg_text)
                ok += 1
            except Exception:
                fail += 1

        await event.reply(f"ارسال انجام شد. موفق: {ok} | ناموفق: {fail}")
        