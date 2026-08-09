import re
import datetime

# ---------------------------------------------------------------------------
# Vietnamese number-word to digit conversion
# sherpa-onnx outputs numbers as words in two styles:
#   Digit-by-digit: "một chín tám bảy" → 1987
#   Formal:         "hai nghìn" → 2000, "một nghìn chín trăm chín mươi chín" → 1999
# ---------------------------------------------------------------------------

_VIET_DIGIT_MAP = {
    "không": 0, "linh": 0, "lẻ": 0,
    "một": 1, "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4, "tư": 4,
    "năm": 5, "lăm": 5,
    "sáu": 6,
    "bảy": 7, "bẩy": 7,
    "tám": 8,
    "chín": 9,
}

# Multiplier words
_VIET_MULTIPLIERS = {
    "nghìn": 1000, "ngàn": 1000,
    "trăm": 100,
    "mươi": 10, "mười": 10,
}

# All number-related words (for detection)
_VIET_NUMBER_WORDS = set(_VIET_DIGIT_MAP.keys()) | set(_VIET_MULTIPLIERS.keys())
_VIET_DIGIT_WORDS = set(_VIET_DIGIT_MAP.keys())  # digits only (for name rejection)


def _parse_viet_number(words: list[str]) -> int | None:
    """
    Parse a sequence of Vietnamese number words into an integer.
    Supports both styles:
      Digit-by-digit: ["một", "chín", "tám", "bảy"] → 1987
      Formal: ["hai", "nghìn"] → 2000
      Formal: ["một", "nghìn", "chín", "trăm", "chín", "mươi", "chín"] → 1999
    """
    if not words:
        return None

    # Check if any multiplier words are present → use formal parsing
    has_multiplier = any(w in _VIET_MULTIPLIERS for w in words)

    if has_multiplier:
        # Formal Vietnamese number: "hai nghìn" = 2000
        total = 0
        current = 0
        for w in words:
            if w in _VIET_DIGIT_MAP:
                current = _VIET_DIGIT_MAP[w]
            elif w in _VIET_MULTIPLIERS:
                mult = _VIET_MULTIPLIERS[w]
                if current == 0:
                    current = 1  # "nghìn" alone means 1000
                total += current * mult
                current = 0
            else:
                return None  # Unknown word in sequence
        total += current  # Add any trailing digit (e.g. "chín" at the end)
        return total if total > 0 else None
    else:
        # Digit-by-digit: ["một", "chín", "chín"] → "199" → 199
        digit_str = ""
        for w in words:
            if w in _VIET_DIGIT_MAP:
                digit_str += str(_VIET_DIGIT_MAP[w])
            else:
                return None
        return int(digit_str) if digit_str else None


def _viet_words_to_digits(text: str) -> str:
    """
    Convert Vietnamese number words to digit strings in text.
    Examples:
      "một chín tám bảy" → "1987"
      "năm sinh hai nghìn" → "năm sinh 2000"
      "năm sinh một nghìn chín trăm chín mươi chín" → "năm sinh 1999"
      "tuổi ba lăm" → "tuổi 35"
    Only converts sequences of 2+ consecutive number words.
    """
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        if words[i] in _VIET_NUMBER_WORDS:
            # Collect consecutive number words
            j = i
            num_words = []
            while j < len(words) and words[j] in _VIET_NUMBER_WORDS:
                num_words.append(words[j])
                j += 1
            # Only convert if 2+ consecutive number words
            if len(num_words) >= 2:
                parsed = _parse_viet_number(num_words)
                if parsed is not None:
                    result.append(str(parsed))
                else:
                    result.extend(num_words)
                i = j
            else:
                result.append(words[i])
                i += 1
        else:
            result.append(words[i])
            i += 1
    return " ".join(result)


def _normalize_year(value: str) -> str | None:
    """
    Normalize a numeric string into a valid birth year.

    Incomplete ASR (3 digits) must NOT invent a last digit — padding with 0
    turned "một chín chín" (meant 1999) into 1990. Callers should keep a
    pending prefix and wait for the final digit instead.
    """
    if not value or not value.isdigit():
        return None
    n = int(value)
    current_year = datetime.datetime.now().year
    if len(value) == 4 and 1900 <= n <= current_year:
        return value
    return None


def incomplete_birth_year_prefix(text: str, *, allow_bare: bool = False) -> str | None:
    """
    If utterance is năm-sinh + exactly 3 digits (ASR truncated year), return those digits.
    Example: "năm sinh một chín chín" → "199"

    Bare 3-digit match (no keyword) only when allow_bare=True — e.g. pending birth_year fill.
    """
    lowered = _viet_words_to_digits(text.strip().lower())
    m = re.search(
        r"(?:năm\s+sinh|sinh\s+năm|nam\s+sinh)\s+(\d{3})\b",
        lowered,
    )
    if not m and allow_bare:
        m = re.fullmatch(r"(\d{3})", lowered.strip())
    if not m:
        return None
    prefix = m.group(1)
    n = int(prefix)
    if 190 <= n <= 202:
        return prefix
    return None


def complete_truncated_birth_year(prefix: str, text: str) -> str | None:
    """Append one final digit (word or numeral) to a 3-digit truncated year prefix."""
    if not prefix or len(prefix) != 3 or not prefix.isdigit():
        return None
    lowered = _viet_words_to_digits(text.strip().lower()).strip()
    digit: str | None = None
    if lowered in _VIET_DIGIT_MAP:
        digit = str(_VIET_DIGIT_MAP[lowered])
    else:
        m = re.fullmatch(r"(\d)", lowered)
        if m:
            digit = m.group(1)
        else:
            # single digit word that survived conversion as digit already
            m = re.fullmatch(r"(\d)", lowered.split()[-1] if lowered else "")
            if m:
                digit = m.group(1)
    if digit is None:
        return None
    return _normalize_year(prefix + digit)

# ---------------------------------------------------------------------------
# System control commands that should NEVER be parsed as patient names.
# ---------------------------------------------------------------------------

SYSTEM_COMMANDS = [
    "chụp", "chụp ảnh",
    "xóa", "xóa ảnh", "xóa hết", "xóa tất cả",
    "tiếp", "bệnh nhân tiếp", "tiếp theo", "chuyển bệnh nhân", "bệnh án tiếp",
    "xem", "xem lại",
    "tìm", "tìm kiếm", "tra cứu", "tra cứu bệnh nhân", "tìm kiếm hồ sơ",
    "bắt đầu", "tạo phiên", "bắt đầu phiên", "mở phiên", "kích hoạt",
    "hoàn thành", "kết thúc", "lưu", "lưu csdl",
    # Field-entry keywords spoken ALONE (without data after them)
    "họ và tên", "họ tên", "tên là", "tên",
    "năm sinh", "sinh năm", "sinh", "nam sinh",
    "giới tính",
    "tuổi",
    "mã", "mã bệnh nhân", "mã số",
]

# ---------------------------------------------------------------------------
# Keyword-based single-field voice commands
# ---------------------------------------------------------------------------

_ASR_FILLER_SUFFIXES = frozenset({"ạ", "nhé", "nha", "đi", "ơi", "à"})


def normalize_voice_text(text: str) -> str:
    """Lowercase + collapse whitespace + strip common ASR punctuation."""
    if not text:
        return ""
    lowered = text.strip().lower()
    lowered = re.sub(r"[,.\?!;:]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def normalize_name_keyword(text: str) -> str:
    """Fix common ASR mis-hearings of «họ và tên» before keyword matching."""
    t = normalize_voice_text(text)
    t = re.sub(r"\bhọ\s+(?:vào|là|va)\s+tên\b", "họ và tên", t)
    t = re.sub(r"\bhọ\s+tên\b", "họ và tên", t)
    return t


_FIELD_PATTERNS = [
    # Require explicit name keyword (not bare "tên …" — too easy to false-trigger)
    (r'(?:họ\s+và\s+tên|họ\s+tên|tên\s+là)\s+(.+)', "full_name"),
    # "Năm sinh <year>" or "Sinh năm <year>" or "Nam sinh <year>"
    (r'(?:năm\s+sinh|sinh\s+năm|nam\s+sinh)\s+(\d{3,4})', "birth_year"),
    # "Tuổi <age>" or "<N> tuổi"
    (r'(?:tuổi)\s+(\d{1,3})', "age"),
    (r'(\d{1,3})\s+tuổi', "age"),
    # "Giới tính <gender>" — never accept bare nam/nữ
    (r'giới\s+tính\s+(nam|nữ|trai|gái)', "gender"),
    # "Mã bệnh nhân <id>" or "Mã <id>" — voice must not set patient_id in app, but keep parse for completeness
    (r'(?:mã\s+bệnh\s+nhân|mã\s+số|mã)\s+([a-z0-9_-]+)', "patient_id"),
]

# Words that are NEVER valid patient names
_NOISE_WORDS = [
    "bệnh nhân", "bệnh án", "hồ sơ", "tên là", "tên", "năm sinh", "sinh năm", "tuổi",
    "giới tính", "nam", "nữ", "ông", "bà", "anh", "chị", "em", "cháu",
    "mã", "tạo phiên", "bắt đầu", "mới", "khám", "tiếp", "chụp", "xóa",
    "họ và tên", "họ tên", "sinh",
]

# Words that should never appear as a standalone extracted patient name
_INVALID_NAMES = {
    "họ", "và", "tên", "họ và", "họ tên", "họ và tên",
    "năm", "sinh", "năm sinh", "sinh năm",
    "giới", "tính", "giới tính",
    "nam", "nữ", "trai", "gái",
    "tuổi", "mã", "mã số",
    "tiếp", "chụp", "xóa", "lưu", "hoàn thành", "kết thúc",
    "bắt đầu", "tạo phiên", "mở phiên",
    # Vietnamese digit words — never valid as patient names
    "một", "hai", "ba", "bốn", "tư", "lăm", "sáu", "bảy", "bẩy", "tám", "chín",
    "không", "mốt", "linh", "lẻ",
    "một chín", "một chín tám", "một chín tám bảy",  # common ASR digit-word combos
}


def _try_single_field(text: str) -> dict | None:
    """
    Try to parse text as a single-field keyword command.
    Returns a dict with only the recognized field, or None if no keyword matched.
    Bare words (e.g. nam/nữ alone) never match — keyword required.
    """
    lowered = normalize_name_keyword(text)

    for pattern, field_key in _FIELD_PATTERNS:
        m = re.search(pattern, lowered)
        if m:
            value = m.group(1).strip()
            if not value:
                continue

            result = {"_partial": True}

            if field_key == "full_name":
                cleaned = re.sub(
                    r'[^a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]',
                    '', value
                ).strip()
                words = [w.capitalize() for w in cleaned.split() if len(w) > 0]
                if not words:
                    continue
                name = " ".join(words)
                if name.lower() in _INVALID_NAMES:
                    continue
                # Reject if all words are digit words (e.g. "một chín tám bảy")
                if all(w.lower() in _VIET_DIGIT_WORDS for w in words):
                    continue
                result["full_name"] = name

            elif field_key == "birth_year":
                normalized = _normalize_year(value)
                if normalized:
                    result["birth_year"] = normalized
                else:
                    continue

            elif field_key == "age":
                age = int(value)
                if 0 < age <= 120:
                    result["birth_year"] = str(datetime.datetime.now().year - age)
                else:
                    continue

            elif field_key == "gender":
                if value in ("nam", "trai"):
                    result["gender"] = "Nam"
                elif value in ("nữ", "gái"):
                    result["gender"] = "Nữ"
                else:
                    continue

            elif field_key == "patient_id":
                raw_id = value.upper()
                if not raw_id.startswith("BN"):
                    raw_id = f"BN_{raw_id}"
                result["patient_id"] = raw_id

            return result

    return None


def parse_patient_speech(text: str) -> dict | None:
    """
    Parses a Vietnamese spoken sentence to extract Patient Demographics.

    Live app path (`voice_detector`) uses keyword-gated `_try_single_field` /
    pending fill only — not this full-sentence mode.

    This helper remains for tests / offline tools:
    1. Single-field keyword: "Họ và tên Nguyễn Văn An" → partial update
    2. Full sentence (legacy): "Bệnh nhân … 1985 Nam" → multi-field

    Returns None if text is a system control command or does not contain valid data.
    Patient ID is NEVER auto-generated — it must come from keyboard or barcode only.
    """
    if not text:
        return None

    raw = text.strip()
    lowered = raw.lower()

    # 0. Convert Vietnamese digit words to numbers FIRST
    #    "năm sinh một chín tám bảy" → "năm sinh 1987"
    lowered = _viet_words_to_digits(lowered)

    # 1. Try single-field keyword mode FIRST
    single = _try_single_field(lowered)
    if single is not None:
        return single

    # 2. Ignore system control commands (exact match or keyword-only text)
    if lowered in SYSTEM_COMMANDS:
        return None

    for cmd in SYSTEM_COMMANDS:
        if lowered == cmd or lowered.startswith(cmd + " ") or lowered.endswith(" " + cmd):
            cleaned = lowered
            for c in sorted(SYSTEM_COMMANDS, key=len, reverse=True):
                cleaned = cleaned.replace(c, "").strip()
            if not cleaned or len(cleaned.split()) < 2:
                return None

    # 3. Full-sentence mode ──────────────────────────────────────────────────

    trigger_words = [
        "bệnh nhân", "bệnh án", "hồ sơ", "tên là", "tên",
        "bác sĩ", "bác", "anh", "chị", "em", "ông", "bà", "cháu",
        "năm sinh", "sinh năm", "mã", "tuổi"
    ]
    if not any(w in lowered for w in trigger_words):
        return None

    # 3a. Extract Gender
    gender = "Nam"
    if any(g in lowered for g in ["giới tính nữ", "nữ", "gái", "bà", "chị", "cô"]):
        gender = "Nữ"
    elif any(g in lowered for g in ["giới tính nam", "nam", "trai", "ông", "anh"]):
        gender = "Nam"

    # 3b. Extract Birth Year or Age
    current_year = datetime.datetime.now().year
    birth_year = ""

    year_match = re.search(r'\b(\d{3,4})\b', lowered)
    if year_match:
        normalized = _normalize_year(year_match.group(1))
        if normalized:
            birth_year = normalized
    if not birth_year:
        age_match = re.search(r'(\d{1,3})\s*tuổi', lowered)
        if age_match:
            age = int(age_match.group(1))
            if 0 <= age <= 120:
                birth_year = str(current_year - age)

    # 3c. Extract Patient ID if spoken
    patient_id = ""
    id_match = re.search(r'(?:mã|mã bệnh nhân|mã số)\s*([a-z0-9_-]+)', lowered)
    if id_match:
        raw_id = id_match.group(1).upper()
        if not raw_id.startswith("BN"):
            patient_id = f"BN_{raw_id}"
        else:
            patient_id = raw_id

    # 3d. Extract Full Name
    name_text = lowered

    if id_match:
        name_text = name_text.replace(id_match.group(0), "")
    if year_match:
        name_text = name_text.replace(year_match.group(0), "")
    if 'age_match' in locals() and age_match:
        name_text = name_text.replace(age_match.group(0), "")

    for w in sorted(_NOISE_WORDS, key=len, reverse=True):
        name_text = re.sub(rf'\b{re.escape(w)}\b', '', name_text)

    # Also remove any remaining Vietnamese digit words from the name
    for dw in _VIET_DIGIT_WORDS:
        name_text = re.sub(rf'\b{re.escape(dw)}\b', '', name_text)

    cleaned_name = re.sub(r'[^a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]', '', name_text).strip()
    words = [w.capitalize() for w in cleaned_name.split() if len(w) > 1]
    full_name = " ".join(words)

    # Patient name MUST be at least 2 words
    if not full_name or len(words) < 2:
        return None

    if full_name.lower() in SYSTEM_COMMANDS or full_name.lower() in _INVALID_NAMES:
        return None
    if any(cmd in full_name.lower() for cmd in ["tiếp", "chụp", "xóa", "hoàn thành"]):
        return None

    name_words_lower = [w.lower() for w in full_name.split()]
    if all(w in _INVALID_NAMES for w in name_words_lower):
        return None

    # Build result — patient_id is NEVER auto-generated by voice.
    result = {
        "full_name": full_name,
        "gender": gender,
    }
    if birth_year:
        result["birth_year"] = birth_year
    if patient_id:
        result["patient_id"] = patient_id

    return result


# ---------------------------------------------------------------------------
# Pending field state machine — supports 2-step voice input:
#   Step 1: "họ và tên"   → detect_pending_field → "full_name"
#   Step 2: "lương thế vinh" → fill_pending_field → {"_partial": True, "full_name": "Lương Thế Vinh"}
# ---------------------------------------------------------------------------

# Map keyword-only utterances to the field they refer to (exact phrase only)
_PENDING_FIELD_MAP = {
    "họ và tên": "full_name",
    "họ tên": "full_name",
    "tên là": "full_name",
    "năm sinh": "birth_year",
    "nam sinh": "birth_year",
    "sinh năm": "birth_year",
    "giới tính": "gender",
    "tuổi": "age",
}


def detect_pending_field(text: str) -> str | None:
    """
    Check if text is a keyword-only utterance that should trigger 'pending field' mode.
    Returns the field name ('full_name', 'birth_year', 'gender', 'age') or None.
    """
    lowered = normalize_name_keyword(text)
    if lowered in _PENDING_FIELD_MAP:
        return _PENDING_FIELD_MAP[lowered]
    for phrase, field in _PENDING_FIELD_MAP.items():
        if lowered.startswith(phrase + " "):
            rest = lowered[len(phrase) :].strip()
            if not rest or rest in _ASR_FILLER_SUFFIXES:
                return field
    return None


def fill_pending_field(field: str, text: str) -> dict | None:
    """
    Given a pending field name and the next spoken text, produce a partial result dict.
    Returns None if text cannot be used for the given field.
    """
    lowered = normalize_name_keyword(text)
    # Convert Vietnamese digit words first
    lowered = _viet_words_to_digits(lowered)

    result = {"_partial": True}

    if field == "full_name":
        cleaned = re.sub(
            r'[^a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]',
            '', lowered
        ).strip()
        words = [w.capitalize() for w in cleaned.split() if len(w) > 0]
        if not words:
            return None
        name = " ".join(words)
        if name.lower() in _INVALID_NAMES:
            return None
        if all(w.lower() in _VIET_DIGIT_WORDS for w in words):
            return None
        result["full_name"] = name
        return result

    elif field == "birth_year":
        # Try year match (4 digits only — 3-digit incomplete must not invent last digit)
        m = re.search(r"\b(\d{4})\b", lowered)
        if m:
            normalized = _normalize_year(m.group(1))
            if normalized:
                result["birth_year"] = normalized
                return result
        # Exactly 3 digits → incomplete; let caller set truncated pending (return None)
        if incomplete_birth_year_prefix(lowered, allow_bare=True) or re.fullmatch(
            r"\d{3}", lowered.strip()
        ):
            return None
        # Try age (1-2 digits) only when clearly an age, not a truncated year
        m = re.search(r"\b(\d{1,2})\b", lowered)
        if m:
            val = int(m.group(1))
            if 0 < val <= 120:
                result["birth_year"] = str(datetime.datetime.now().year - val)
                return result
        return None

    elif field == "age":
        m = re.search(r'\b(\d{1,3})\b', lowered)
        if m:
            age = int(m.group(1))
            if 0 < age <= 120:
                result["birth_year"] = str(datetime.datetime.now().year - age)
                return result
        return None

    elif field == "gender":
        if lowered in ("nam", "trai"):
            result["gender"] = "Nam"
            return result
        elif lowered in ("nữ", "gái"):
            result["gender"] = "Nữ"
            return result
        return None

    return None

