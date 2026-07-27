"""
voice_lib.audio_processing — Xử lý tín hiệu âm thanh PCM16

Cung cấp:
- Resample PCM16 (linear interpolation) cho các mic không hỗ trợ 16kHz
- Software AGC (Automatic Gain Control) để chuẩn hóa âm lượng
- Tính RMS và mức volume cho visual feedback
- Hằng số VAD (Voice Activity Detection) có thể cấu hình
"""

import math
import struct

# ─── Hằng số cấu hình ──────────────────────────────────────────────────────

# VAD: Ngưỡng RMS tối thiểu để coi là đang nói (âm thanh > ngưỡng = speaking)
# Dùng cho audio ĐÃ qua AGC (backward compat)
VAD_RMS_THRESHOLD: float = 120.0

# VAD: Ngưỡng RMS trên audio RAW (TRƯỚC AGC) để phát hiện giọng nói
# Background noise Realtek ~30-35 RMS, giọng nói thật >50 RMS
# Ngưỡng phải CAO HƠN noise floor để tránh false trigger liên tục
VAD_RAW_RMS_THRESHOLD: float = 50.0

# VAD: Số frame im lặng liên tiếp để kết thúc lời nói
# Với chunk 50ms, 3 frames = 0.15 giây — phản hồi nhanh cho lệnh ngắn
SILENCE_FRAME_COUNT: int = 3

# VAD: Số frame tối thiểu trong một đoạn nói để coi là hợp lệ
# Tránh gửi noise ngắn tới Whisper gây hallucination (4 frames = 0.2s)
MIN_SPEECH_FRAMES: int = 4

# VAD: Giới hạn tối đa speech trước khi force transcribe
# 40 frames × 50ms = 2 giây — tránh buffer quá dài gây chậm
MAX_SPEECH_FRAMES: int = 40

# Cooldown: Thời gian chờ giữa 2 lần kích hoạt lệnh (giây)
COOLDOWN_SECONDS: float = 1.5

# AGC: Mức RMS mục tiêu sau khi boost
AGC_TARGET_RMS: float = 1800.0

# AGC: Hệ số gain tối đa (tránh khuếch đại noise quá mức)
AGC_MAX_GAIN: float = 8.0

# Volume: Giá trị RMS tối đa dùng để tính phần trăm volume bar
VOLUME_MAX_RMS: float = 2500.0


# ─── Resample ───────────────────────────────────────────────────────────────

def resample_pcm16(data_bytes: bytes, orig_rate: int, target_rate: int = 16000) -> bytes:
    """Resample dữ liệu PCM16 mono từ orig_rate sang target_rate bằng linear interpolation.

    Nếu orig_rate == target_rate hoặc data rỗng, trả về nguyên bản.
    """
    if orig_rate == target_rate or not data_bytes:
        return data_bytes

    count = len(data_bytes) // 2
    if count == 0:
        return data_bytes

    shorts = struct.unpack(f"{count}h", data_bytes)
    target_count = int(count * target_rate / orig_rate)
    if target_count == 0:
        return b""

    step = orig_rate / target_rate
    resampled = []
    for i in range(target_count):
        idx = i * step
        idx_low = int(idx)
        idx_high = min(idx_low + 1, count - 1)
        frac = idx - idx_low
        val = int((1 - frac) * shorts[idx_low] + frac * shorts[idx_high])
        resampled.append(max(-32768, min(32767, val)))

    return struct.pack(f"{target_count}h", *resampled)


# ─── AGC (Automatic Gain Control) ──────────────────────────────────────────

def apply_software_agc(
    data_bytes: bytes,
    target_rms: float = AGC_TARGET_RMS,
    max_gain: float = AGC_MAX_GAIN,
) -> bytes:
    """Áp dụng Software AGC lên dữ liệu PCM16.

    Tự động tăng/giảm gain dựa trên RMS hiện tại so với target_rms.
    Chỉ boost khi RMS nằm trong khoảng hợp lệ (5 < rms < 2500),
    tránh khuếch đại noise khi quá yên hoặc clipping khi quá to.
    """
    if not data_bytes:
        return data_bytes

    count = len(data_bytes) // 2
    if count == 0:
        return data_bytes

    shorts = struct.unpack(f"{count}h", data_bytes)
    rms = compute_rms_from_shorts(shorts)

    if 5 < rms < 2500:
        dynamic_gain = min(max_gain, max(1.5, target_rms / (rms + 1e-5)))
    else:
        dynamic_gain = 1.0

    boosted = [max(-32767, min(32767, int(s * dynamic_gain))) for s in shorts]
    return struct.pack(f"{count}h", *boosted)


# ─── RMS & Volume ──────────────────────────────────────────────────────────

def compute_rms_from_shorts(shorts: list | tuple) -> float:
    """Tính RMS từ list/tuple các giá trị int16."""
    count = len(shorts)
    if count == 0:
        return 0.0
    sum_sq = sum(s * s for s in shorts)
    return math.sqrt(sum_sq / count)


def compute_rms(data_bytes: bytes) -> float:
    """Tính RMS từ raw PCM16 bytes."""
    count = len(data_bytes) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", data_bytes)
    return compute_rms_from_shorts(shorts)


def compute_volume_level(rms: float, max_rms: float = VOLUME_MAX_RMS) -> int:
    """Chuyển đổi RMS thành mức volume 0-100 với thang logarithmic.

    Sử dụng hàm sqrt để tăng độ nhạy ở mức âm lượng thấp,
    cho trải nghiệm volume bar tự nhiên hơn.
    """
    if rms <= 1:
        return 0
    clamped = min(max_rms, rms)
    return min(100, int(math.pow(clamped / max_rms, 0.5) * 100))
