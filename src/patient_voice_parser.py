import re
import datetime

# ---------------------------------------------------------------------------
# Vietnamese digit-word to number conversion
# sherpa-onnx often outputs "một chín tám bảy" instead of "1987"
# ---------------------------------------------------------------------------

_VIET_DIGIT_MAP = {
    "không": "0", "linh": "0", "lẻ": "0",
    "một": "1", "mốt": "1",
    "hai": "2",
    "ba": "3",
    "bốn": "4", "tư": "4",
    "năm": "5", "lăm": "5",
    "sáu": "6",
    "bảy": "7", "bẩy": "7",
    "tám": "8",
    "chín": "9",
}

# Words that are Vietnamese digits (used to detect number-word sequences)
_VIET_DIGIT_WORDS = set(_VIET_DIGIT_MAP.keys())


def _viet_words_to_digits(text: str) -> str:
    """
    Convert Vietnamese number words to digit strings.
    Examples:
      "một chín tám bảy" → "1987"
      "năm sinh một chín tám bảy" → "năm sinh 1987"
      "tuổi ba lăm" → "tuổi 35"
    Only converts sequences of 2+ consecutive digit words.
    """
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        # Check if current word is a digit word
        if words[i] in _VIET_DIGIT_WORDS:
            # Collect consecutive digit words
            digit_str = ""
            j = i
            while j < len(words) and words[j] in _VIET_DIGIT_WORDS:
                digit_str += _VIET_DIGIT_MAP[words[j]]
                j += 1
            # Only convert if 2+ consecutive digit words (avoid converting standalone "năm" etc.)
            if j - i >= 2:
                result.append(digit_str)
                i = j
            else:
                result.append(words[i])
                i += 1
        else:
            result.append(words[i])
            i += 1
    return " ".join(result)


# ---------------------------------------------------------------------------
# System control commands that should NEVER be parsed as patient names.
# ---------------------------------------------------------------------------

SYSTEM_COMMANDS = [
    "chụp", "chụp ảnh",
    "xóa", "xóa ảnh",
    "tiếp", "bệnh nhân tiếp", "tiếp theo", "chuyển bệnh nhân", "bệnh án tiếp",
    "xem", "xem lại",
    "tìm", "tìm kiếm", "tra cứu", "tra cứu bệnh nhân", "tìm kiếm hồ sơ",
    "bắt đầu", "tạo phiên", "bắt đầu phiên", "mở phiên", "kích hoạt",
    "hoàn thành", "kết thúc", "lưu", "lưu csdl",
    # Field-entry keywords spoken ALONE (without data after them)
    "họ và tên", "họ tên", "tên là", "tên",
    "năm sinh", "sinh năm", "sinh",
    "giới tính",
    "tuổi",
    "mã", "mã bệnh nhân", "mã số",
]

# ---------------------------------------------------------------------------
# Keyword-based single-field voice commands
# ---------------------------------------------------------------------------

_FIELD_PATTERNS = [
    # "Họ và tên <name>" or "Họ tên <name>" or "Tên là <name>" or "Tên <name>"
    (r'(?:họ\s+và\s+tên|họ\s+tên|tên\s+là|tên)\s+(.+)', "full_name"),
    # "Năm sinh <year>" or "Sinh năm <year>" or "Sinh <year>"
    (r'(?:năm\s+sinh|sinh\s+năm|sinh)\s+(\d{4})', "birth_year"),
    # "Tuổi <age>" or "<N> tuổi"
    (r'(?:tuổi)\s+(\d{1,3})', "age"),
    (r'(\d{1,3})\s+tuổi', "age"),
    # "Giới tính <gender>"
    (r'giới\s+tính\s+(nam|nữ|trai|gái)', "gender"),
    # "Mã bệnh nhân <id>" or "Mã <id>"
    (r'(?:mã\s+bệnh\s+nhân|mã\s+số|mã)\s+([a-z0-9_-]+)', "patient_id"),
]

# Standalone gender words (spoken alone without "giới tính" prefix)
_STANDALONE_GENDER = {"nam": "Nam", "nữ": "Nữ"}

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
    """
    lowered = text.strip().lower()

    # Check standalone gender words ("nam" or "nữ" spoken alone)
    if lowered in _STANDALONE_GENDER:
        return {"_partial": True, "gender": _STANDALONE_GENDER[lowered]}

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
                year = int(value)
                if 1900 <= year <= datetime.datetime.now().year:
                    result["birth_year"] = str(year)
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

    Supports two modes:
    1. Single-field keyword: "Họ và tên Nguyễn Văn An" → partial update of just full_name
    2. Full sentence: "Bệnh nhân Nguyễn Văn An 1985 Nam" → full patient record

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

    year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', lowered)
    if year_match:
        birth_year = year_match.group(1)
    else:
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

# Map keyword-only utterances to the field they refer to
_PENDING_FIELD_MAP = {
    "họ và tên": "full_name",
    "họ tên": "full_name",
    "tên là": "full_name",
    "tên": "full_name",
    "năm sinh": "birth_year",
    "sinh năm": "birth_year",
    "giới tính": "gender",
    "tuổi": "age",
}


def detect_pending_field(text: str) -> str | None:
    """
    Check if text is a keyword-only utterance that should trigger 'pending field' mode.
    Returns the field name ('full_name', 'birth_year', 'gender', 'age') or None.
    """
    lowered = text.strip().lower()
    return _PENDING_FIELD_MAP.get(lowered)


def fill_pending_field(field: str, text: str) -> dict | None:
    """
    Given a pending field name and the next spoken text, produce a partial result dict.
    Returns None if text cannot be used for the given field.
    """
    lowered = text.strip().lower()
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
        # Try digit match
        m = re.search(r'\b(\d{4})\b', lowered)
        if m:
            year = int(m.group(1))
            if 1900 <= year <= datetime.datetime.now().year:
                result["birth_year"] = str(year)
                return result
        # Try age
        m = re.search(r'\b(\d{1,3})\b', lowered)
        if m:
            val = int(m.group(1))
            if 1900 <= val <= datetime.datetime.now().year:
                result["birth_year"] = str(val)
                return result
            elif 0 < val <= 120:
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

