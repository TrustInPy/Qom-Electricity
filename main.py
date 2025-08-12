import asyncio
import logging
from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN, PROXY, CRAWL_INTERVAL_MIN, DEFAULT_URL
from logging_config import setup_logging
import db
from crawler import crawl, page_signature
from notifier import send_matching_sections
from commands import register as register_commands

log = logging.getLogger("main")

async def periodic_crawler(client: TelegramClient):
    print("[crawler] started")
    while True:
        try:
            try:
                last_update, sections, ann_display, ann_key = await crawl(DEFAULT_URL)
            except Exception as e:
                log.exception("fetch main URL failed: %s", e)
                last_update, sections, ann_display, ann_key = None, [], None, None

            if not sections:
                log.warning("no sections parsed; will retry later.")
            else:
                # Prefer date key; fallback to last_update; then content signature
                base_key = ann_key or last_update or page_signature(sections)
                last_display = last_update if last_update else "نامشخص (شناسه محتوا)"

                prev = db.get_setting("last_update_seen")
                if prev != base_key:
                    db.set_setting("last_update_seen", base_key)
                    log.info("New update key: %s (prev: %s)", base_key, prev)

                    chats = db.list_chats()
                    for chat_id, _url, _created in chats:
                        try:
                            kws = db.list_keywords(chat_id)
                            if not kws:
                                continue
                            sent = await send_matching_sections(client, chat_id, base_key, last_display,
                                                                sections, kws, ann_display=ann_display)
                            if sent:
                                log.info("chat %s: sent %s sections.", chat_id, sent)
                        except Exception as e:
                            log.exception("chat %s: processing error: %s", chat_id, e)
                else:
                    log.debug("No change in update key (%s).", base_key)
        except Exception as e:
            log.exception("crawler loop error: %s", e)

        await asyncio.sleep(CRAWL_INTERVAL_MIN * 60)

async def main():
    setup_logging()
    db.init()

    client = TelegramClient("qepd_bot", API_ID, API_HASH, proxy=PROXY)
    await client.start(bot_token=BOT_TOKEN)

    register_commands(client)

    asyncio.create_task(periodic_crawler(client))
    log.info("Bot is up. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
