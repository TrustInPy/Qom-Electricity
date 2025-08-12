import asyncio
import hashlib
import logging
import re
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from config import DEFAULT_URL, LAST_UPDATE_SELECTOR_ID
from textutils import clean_text, strip_decor_prefix, extract_announce_date_key

log = logging.getLogger("crawler")

def is_section_start(line: str) -> bool:
    return ("ساعت" in line) and (("قطعی" in line) or ("برق" in line))

async def fetch_html(url: str, timeout=30, retries=3, backoff=2.0) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as sess:
                r = await sess.get(url)
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                log.debug("fetch ok attempt=%s", attempt)
                return r.text
        except Exception as e:
            last_err = e
            log.warning("fetch failed attempt=%s err=%s", attempt, e)
            await asyncio.sleep(backoff * attempt)
    raise RuntimeError(f"fetch failed after {retries} retries: {last_err}")

def parse_last_update(soup: BeautifulSoup) -> Optional[str]:
    node = soup.find(id=LAST_UPDATE_SELECTOR_ID)
    if node:
        text = clean_text(node.get_text(" ", strip=True))
        m = re.search(r"[:：]\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})", text)
        return m.group(1) if m else text
    return None

def parse_announce_date(soup: BeautifulSoup):
    """
    Find the AnnTitle with 'مورخ ...' and return (display, key), else (None, None)
    """
    for el in soup.select("span.ItemTitle.AnnTitle"):
        txt = clean_text(el.get_text(" ", strip=True))
        display, key = extract_announce_date_key(txt)
        if key:
            return display, key
    return None, None

def extract_lines(soup: BeautifulSoup) -> List[str]:
    candidates = soup.select("div.AnnDescription")
    if not candidates:
        candidates = soup.select("div.dp-module-content")
    container = candidates[0] if candidates else soup

    nodes = container.select("p, li")
    lines: List[str] = []
    for node in nodes:
        txt = node.get_text(" ", strip=True)
        txt = clean_text(txt)
        txt = strip_decor_prefix(txt)   # drop leading ❌, 🔻, bullets, etc.
        if txt:
            lines.append(txt)

    seen, out = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln); out.append(ln)
    return out

def split_sections(lines: List[str]) -> List[Tuple[str, List[str]]]:
    sections: List[Tuple[str, List[str]]] = []
    title: Optional[str] = None
    body: List[str] = []
    for ln in lines:
        if is_section_start(ln):
            if title is not None:
                sections.append((title, body))
                body = []
            title = ln
        else:
            if title is not None:
                body.append(ln)
    if title is not None:
        sections.append((title, body))
    return sections

def page_signature(sections: List[Tuple[str, List[str]]]) -> str:
    h = hashlib.sha256()
    for title, body in sections:
        h.update(title.encode("utf-8", "ignore"))
        h.update("\n".join(body).encode("utf-8", "ignore"))
    return "sig:" + h.hexdigest()[:16]

async def crawl(url: str = DEFAULT_URL):
    """
    Returns: (last_update, sections, ann_display, ann_key)
    """
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    last_update = parse_last_update(soup)
    ann_display, ann_key = parse_announce_date(soup)
    lines = extract_lines(soup)
    sections = split_sections(lines)
    log.info("crawl complete | sections=%s lu=%s ann_key=%s", len(sections), last_update, ann_key)
    return last_update, sections, ann_display, ann_key
