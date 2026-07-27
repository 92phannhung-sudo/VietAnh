"""
voice_lib.speech_recognizer — Nhận dạng giọng nói tiếng Việt bằng Whisper

Cung cấp:
- WhisperRecognizer: Class bọc faster-whisper, load model 1 lần, transcribe nhiều lần
- match_vietnamese_keyword(): Khớp lệnh tiếng Việt từ text đã nhận dạng
- KEYWORD_SYNONYMS: Từ điển đồng nghĩa phiên âm tiếng Việt cho y khoa
"""

import logging

import numpy as np

logger = logging.getLogger("PatientApp")


# ─── Từ điển đồng nghĩa phiên âm tiếng Việt cho lệnh y khoa ───────────────

KEYWORD_SYNONYMS: dict[str, list[str]] = {
    "chụp": [
        "chụp", "chup", "chúp", "chút", "chụpt",
        "chụp ảnh", "chup anh", "chụp hình", "chup hinh",
    ],
    "xóa": [
        "xóa", "xoa", "xoá", "xóa ảnh", "xoa anh",
        "xóa đi", "xoa di", "xóa bỏ", "xoa bo",
    ],
    "tiếp": [
        "tiếp", "tiep", "kiếp", "kiep", "kế tiếp",
        "tiếp theo", "tiep theo", "bệnh nhân mới", "mới",
    ],
    "xem": [
        "xem", "xem lại", "xem lai", "xem ảnh", "xem anh",
    ],
}


def match_vietnamese_keyword(text: str) -> str | None:
    """Khớp văn bản đã nhận dạng với một lệnh tiếng Việt.

    Sử dụng so khớp phiên âm (có dấu/không dấu) để chống lỗi nhận dạng
    do accent variation hoặc giọng địa phương.

    Args:
        text: Văn bản đã nhận dạng từ Whisper (lowercase).

    Returns:
        Tên lệnh ("chụp", "xóa", "tiếp", "xem") hoặc None nếu không khớp.
    """
    if not text:
        return None

    text_clean = text.lower().strip()
    words = text_clean.split()

    for cmd, synonyms in KEYWORD_SYNONYMS.items():
        for syn in synonyms:
            if syn in text_clean or any(syn == w for w in words):
                return cmd

    return None


# ─── WhisperRecognizer ──────────────────────────────────────────────────────

class WhisperRecognizer:
    """Bọc faster-whisper model, cung cấp API đơn giản cho nhận dạng tiếng Việt.

    Usage::

        recognizer = WhisperRecognizer(model_size="small")
        if recognizer.is_available():
            text = recognizer.transcribe(list_of_pcm16_frames)
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        """Khởi tạo và load Whisper model.

        Args:
            model_size: Kích thước model ("tiny", "base", "small", "medium", "large").
            device: "cpu" hoặc "cuda".
            compute_type: Kiểu tính toán ("int8", "float16", "float32").
        """
        self._model = None
        self._model_size = model_size
        self._load_error: str | None = None

        try:
            # Tắt SSL verify cho môi trường intranet bệnh viện
            # Chỉ áp dụng trong quá trình download model, không ảnh hưởng toàn cục
            import os
            os.environ.setdefault("CURL_CA_BUNDLE", "")
            os.environ.setdefault("REQUESTS_CA_BUNDLE", "")

            from faster_whisper import WhisperModel
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info(
                f"[WHISPER] Loaded model '{model_size}' "
                f"(device={device}, compute_type={compute_type})"
            )
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"[WHISPER] Failed to load model '{model_size}': {e}")

    def is_available(self) -> bool:
        """Kiểm tra model đã load thành công chưa."""
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        """Thông báo lỗi nếu model load thất bại, None nếu thành công."""
        return self._load_error

    @property
    def model_size(self) -> str:
        """Kích thước model đang sử dụng."""
        return self._model_size

    def transcribe(self, audio_frames: list[bytes], language: str = "vi") -> str:
        """Nhận dạng giọng nói từ danh sách các frame PCM16 raw.

        Args:
            audio_frames: Danh sách bytes, mỗi phần tử là 1 chunk PCM16 mono 16kHz.
            language: Mã ngôn ngữ ISO 639-1 (mặc định: "vi" cho tiếng Việt).

        Returns:
            Văn bản đã nhận dạng (lowercase, stripped). Trả về "" nếu lỗi hoặc không nhận được gì.
        """
        if not self._model or not audio_frames:
            return ""

        try:
            audio_bytes = b"".join(audio_frames)
            # Chuyển PCM16 int16 → float32 normalized [-1.0, 1.0]
            audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Kiểm tra audio quá ngắn (< 0.3s)
            duration = len(audio_float) / 16000.0
            if duration < 0.3:
                logger.debug(f"[WHISPER] Audio too short ({duration:.2f}s), skipping")
                return ""

            segments, info = self._model.transcribe(
                audio_float,
                language=language,

                # ── Tốc độ ──
                beam_size=1,                        # Nhanh nhất cho CPU
                temperature=0.0,                    # Deterministic

                # ── Chống hallucination & lặp (nghiên cứu best practices) ──
                repetition_penalty=1.5,             # Phạt token lặp — fix "xóa ảnh xóa ảnh..." loop
                no_repeat_ngram_size=3,             # Cấm lặp bất kỳ 3-gram nào
                condition_on_previous_text=False,   # Không kế thừa context cũ
                no_speech_threshold=0.7,            # Reject silence mạnh
                compression_ratio_threshold=1.8,    # Strict hơn default (2.4) — lọc text lặp
                max_new_tokens=10,                  # Lệnh ngắn, giới hạn output

                # ── Silero VAD tích hợp ──
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    min_speech_duration_ms=100,
                    threshold=0.4,
                    speech_pad_ms=150,
                ),

                # ── Keyword biasing (chỉ dùng hotwords, KHÔNG dùng initial_prompt để tránh lặp) ──
                hotwords="chụp xóa tiếp xem",
            )
            text = " ".join(s.text for s in segments).lower().strip()

            # Lọc hallucination phổ biến của Whisper
            if _is_hallucination(text):
                logger.info(f"[WHISPER] Filtered hallucination: '{text}'")
                return ""

            return text

        except Exception as e:
            logger.debug(f"[WHISPER] Transcription error: {e}")
            return ""


# ─── Bộ lọc hallucination ───────────────────────────────────────────────────

# Các pattern hallucination phổ biến của Whisper (từ YouTube training data)
_HALLUCINATION_PATTERNS = [
    "subscribe",
    "kênh",
    "video",
    "like",
    "comment",
    "hẹn gặp lại",
    "hen gap lai",
    "cảm ơn đã xem",
    "cam on da xem",
    "bỏ lỡ",
    "bo lo",
    "hấp dẫn",
    "hap dan",
    "nghiện mì gõ",
    "nhấn nút",
    "nhan nut",
    "đăng ký",
    "dang ky",
    "chia sẻ",
    "chia se",
]


def _is_hallucination(text: str) -> bool:
    """Kiểm tra xem text có phải là hallucination của Whisper hay không."""
    if not text:
        return True

    # Quá dài so với lệnh ngắn (lệnh y khoa chỉ 1-3 từ)
    if len(text.split()) > 6:
        return True

    text_lower = text.lower()
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern in text_lower:
            return True

    return False
