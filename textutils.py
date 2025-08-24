import re
from typing import Optional, Tuple

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# emoji & symbols ranges
EMOJI_RE = re.compile(
    "["  # start char class
    "\u2600-\u26ff"  # Misc symbols
    "\u2700-\u27bf"  # Dingbats
    "\U0001f300-\U0001faff"  # Symbols & Pictographs
    "\U0001f1e6-\U0001f1ff"  # Flags
    "]",
    flags=re.UNICODE,
)

# leading decorations (❌, 🔻, punctuation, ZWJ/VS16, etc.)
DECOR_PREFIX_RE = re.compile(
    r"^[\s\W\u200c\u2066-\u2069\uFE0F\u0640\u061F\u060C\u066A-\u066C\-\–—\·•★☆❖✔✖✳❌🔻⚡️🆔✅➕➖▶️]+"
)


def clean_text(s: str) -> str:
    s = re.sub(r"\u200c", "", s)  # ZWNJ
    s = s.replace("\xa0", " ")  # NBSP
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def normalize_digits(s: str) -> str:
    return s.translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)


def strip_emojis(s: str) -> str:
    return EMOJI_RE.sub("", s)


def strip_decor_prefix(s: str) -> str:
    return DECOR_PREFIX_RE.sub("", s)


def normalize_for_match(s: str) -> str:
    s = clean_text(s)
    s = strip_emojis(s)
    return s.lower()


def parse_start_hour_from_title(title: str) -> Optional[int]:
    """
    Expect patterns like: '... ساعت ۹ تا ۱۱' or 'ساعت 13 تا 15'
    Return the start hour (int) or None.
    """
    t = normalize_digits(title)
    m = re.search(r"ساعت\s*(\d{1,2})\s*تا\s*(\d{1,2})", t)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


# ---- AnnTitle date parsing ----
JALALI_MONTHS = {
    "فروردین": 1,
    "اردیبهشت": 2,
    "خرداد": 3,
    "تیر": 4,
    "مرداد": 5,
    "شهریور": 6,
    "مهر": 7,
    "آبان": 8,
    "آذر": 9,
    "دی": 10,
    "بهمن": 11,
    "اسفند": 12,
}
JALALI_MONTHS_INV = {v: k for k, v in JALALI_MONTHS.items()}

# --- NEW: Persian ordinal day words -> int (normalized without spaces/ZWNJ) ---
_ORDINAL_DAY_MAP = {
    "اول": 1,
    "دوم": 2,
    "سوم": 3,
    "چهارم": 4,
    "پنجم": 5,
    "ششم": 6,
    "هفتم": 7,
    "هشتم": 8,
    "نهم": 9,
    "دهم": 10,
    "یازدهم": 11,
    "دوازدهم": 12,
    "سیزدهم": 13,
    "چهاردهم": 14,
    "پانزدهم": 15,
    "شانزدهم": 16,
    "هفدهم": 17,
    "هجدهم": 18,
    "نوزدهم": 19,
    "بیستم": 20,
    # 21..29 variations (with/without ZWNJ)
    "بیستویکم": 21,
    "بیستویكم": 21,
    "بیست‌ویکم": 21,
    "بیست‌و‌یكم": 21,
    "بیستودوم": 22,
    "بیست‌ودوم": 22,
    "بیستوسوم": 23,
    "بیست‌وسوم": 23,
    "بیستوچهارم": 24,
    "بیست‌وچهارم": 24,
    "بیستوپنجم": 25,
    "بیست‌وپنجم": 25,
    "بیستوششم": 26,
    "بیست‌وششم": 26,
    "بیستوهفتم": 27,
    "بیست‌وهفتم": 27,
    "بیستوهشتم": 28,
    "بیست‌وهشتم": 28,
    "بیستونهم": 29,
    "بیست‌ونهم": 29,
    # 30, 31 variations
    "سیام": 30,
    "سی‌ام": 30,
    "سی ام": 30,
    "سیویکم": 31,
    "سی‌ویکم": 31,
    "سی و یکم": 31,
}


def _normalize_letters(s: str) -> str:
    # remove spaces and ZWNJ to compare tokens robustly
    return re.sub(r"[\s\u200c]+", "", s)


def parse_persian_ordinal_day(token: str) -> Optional[int]:
    norm = _normalize_letters(token)
    return _ORDINAL_DAY_MAP.get(norm)


def extract_announce_date_key(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    From e.g.:
        '... مورخ ۲۲ مرداد ماه ۱۴۰۴'
        '... مورخ دوم شهریور ماه ۱۴۰۴'
    Return (display, key) => ('22 مرداد 1404', 'J1404-06-02') or (None, None)
    """
    s = normalize_digits(clean_text(text))

    # 1) Try numeric day first
    m = re.search(
        r"مورخ\s+(\d{1,2})\s+"
        r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
        r"\s+(?:ماه\s+)?(\d{4})",
        s,
    )
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3))
        month_num = JALALI_MONTHS.get(month_name)
        if month_num:
            display = f"{day} {month_name} {year}"
            key = f"J{year:04d}-{month_num:02d}-{day:02d}"
            return display, key

    # 2) Try word-based ordinal day
    m2 = re.search(
        r"مورخ\s+([آ-ی\u200c\s]+?)\s+"
        r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
        r"\s+(?:ماه\s+)?(\d{4})",
        s,
    )
    if m2:
        day_word = m2.group(1).strip()
        month_name = m2.group(2)
        year = int(m2.group(3))
        day = parse_persian_ordinal_day(day_word)
        month_num = JALALI_MONTHS.get(month_name)
        if day and month_num:
            display = f"{day} {month_name} {year}"
            key = f"J{year:04d}-{month_num:02d}-{day:02d}"
            return display, key

    return None, None


def derive_date_key_from_last_update(
    last_update: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Given '1404/06/02 12:54' -> ('2 شهریور 1404', 'J1404-06-02')
    If no match, return (None, None).
    """
    if not last_update:
        return None, None
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", last_update)
    if not m:
        return None, None
    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    month_name = JALALI_MONTHS_INV.get(month, f"{month:02d}")
    display = f"{day} {month_name} {year}"
    key = f"J{year:04d}-{month:02d}-{day:02d}"
    return display, key
