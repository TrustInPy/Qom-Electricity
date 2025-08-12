import re
from typing import Optional

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS  = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# emoji & symbols ranges
EMOJI_RE = re.compile(
    "["                     # start char class
    "\u2600-\u26FF"         # Misc symbols
    "\u2700-\u27BF"         # Dingbats
    "\U0001F300-\U0001FAFF" # Symbols & Pictographs
    "\U0001F1E6-\U0001F1FF" # Flags
    "]", flags=re.UNICODE
)

# leading decorations (❌, 🔻, punctuation, ZWJ/VS16, etc.)
DECOR_PREFIX_RE = re.compile(r"^[\s\W\u200c\u2066-\u2069\uFE0F\u0640\u061F\u060C\u066A-\u066C\-\–—\·•★☆❖✔✖✳❌🔻⚡️🆔✅➕➖▶️]+")

def clean_text(s: str) -> str:
    s = re.sub(r"\u200c", "", s)   # ZWNJ
    s = s.replace("\xa0", " ")     # NBSP
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
    "فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4,
    "مرداد": 5, "شهریور": 6, "مهر": 7, "آبان": 8,
    "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12,
}

def extract_announce_date_key(text: str):
    """
    Input: '... مورخ ۲۲ مرداد ماه ۱۴۰۴'
    Output: (display, key) => ('22 مرداد 1404', 'J1404-05-22') or (None, None)
    """
    s = normalize_digits(clean_text(text))
    m = re.search(r"مورخ\s+(\d{1,2})\s+"
                  r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
                  r"\s+(?:ماه\s+)?(\d{4})", s)
    if not m:
        return None, None
    day = int(m.group(1))
    month_name = m.group(2)
    year = int(m.group(3))
    month_num = JALALI_MONTHS.get(month_name)
    if not month_num:
        return None, None
    display = f"{day} {month_name} {year}"
    key = f"J{year:04d}-{month_num:02d}-{day:02d}"
    return display, key
