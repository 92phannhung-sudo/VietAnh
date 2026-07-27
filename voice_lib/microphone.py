"""
voice_lib.microphone — Phát hiện & quản lý thiết bị microphone vật lý

Cung cấp:
- Lọc bỏ virtual drivers, loopback, speakers
- Liệt kê microphone vật lý thực từ Qt & PyAudio
- Tìm device index phù hợp cho PyAudio stream
"""

import logging

logger = logging.getLogger("PatientApp")

# ─── Keywords để loại bỏ thiết bị ảo ────────────────────────────────────────

_INVALID_DEVICE_KEYWORDS = [
    "speaker", "pc speaker", "loa", "output", "tai nghe", "headphone", "line out",
    "stereo mix", "mix", "loopback", "wave out", "virtual", "cable", "soundflower",
    "steam", "obs", "primary", "mapper", "voice recorder",
]


def is_valid_physical_microphone(name: str) -> bool:
    """Kiểm tra tên thiết bị có phải là microphone vật lý thực hay không.

    Loại bỏ: virtual drivers, loopback, speakers, line-out, dummy recorders.
    """
    if not name or not name.strip():
        return False
    name_lower = name.lower().strip()

    for kw in _INVALID_DEVICE_KEYWORDS:
        if kw in name_lower:
            return False

    # Loại bỏ tên rỗng trong ngoặc, ví dụ: 'Microphone Array 1 ()'
    if name_lower.endswith("()") or name_lower.endswith("( )"):
        return False

    return True


def get_real_physical_microphones() -> list[str]:
    """Liệt kê tên các microphone vật lý thực từ Qt MultimediaDevices + PyAudio.

    Kết hợp cả hai nguồn để đảm bảo không bỏ sót thiết bị.
    Trả về danh sách tên duy nhất (không trùng lặp).
    """
    raw_mics: list[str] = []

    # Nguồn 1: Qt MultimediaDevices
    try:
        from PySide6.QtMultimedia import QMediaDevices
        for mic in QMediaDevices.audioInputs():
            desc = mic.description().strip()
            if is_valid_physical_microphone(desc) and desc not in raw_mics:
                raw_mics.append(desc)
    except Exception:
        pass

    # Nguồn 2: PyAudio
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                name = dev.get("name", "").strip()
                if is_valid_physical_microphone(name):
                    already_covered = any(name in r or r in name for r in raw_mics)
                    if not already_covered:
                        raw_mics.append(name)
        pa.terminate()
    except Exception:
        pass

    return raw_mics


def get_available_microphones() -> list[str]:
    """Trả về danh sách microphone khả dụng, bắt đầu bằng 'Mặc định hệ thống'."""
    mics = ["Mặc định hệ thống"]
    for name in get_real_physical_microphones():
        if name not in mics:
            mics.append(name)
    return mics


def find_device_index(pa_instance, mic_name: str, config_mic_name: str = "default") -> int | None:
    """Tìm PyAudio device index phù hợp nhất cho tên microphone.

    Chiến lược tìm kiếm (ưu tiên từ trên xuống):
    1. Khớp tên mic_name do người dùng chỉ định
    2. Khớp tên mic từ config
    3. Microphone vật lý đầu tiên trong danh sách
    4. Default input device của hệ thống (nếu là mic thật)
    5. Bất kỳ mic vật lý nào tìm được qua PyAudio

    Args:
        pa_instance: PyAudio instance đã khởi tạo
        mic_name: Tên mic người dùng chọn (có thể là "default" hoặc "Mặc định hệ thống")
        config_mic_name: Tên mic từ file config (fallback)

    Returns:
        Device index (int) hoặc None nếu không tìm thấy
    """
    # Xác định tên mic mục tiêu
    is_default = mic_name in (None, "", "default", "Mặc định hệ thống")
    mic_target = mic_name if not is_default else config_mic_name
    target_is_default = mic_target in (None, "", "default", "Mặc định hệ thống")

    # Bước 1: Tìm khớp tên cụ thể
    if not target_is_default:
        for i in range(pa_instance.get_device_count()):
            try:
                dev_info = pa_instance.get_device_info_by_index(i)
                dev_n = dev_info.get("name", "")
                if dev_info.get("maxInputChannels", 0) > 0 and (mic_target in dev_n or dev_n in mic_target):
                    logger.debug(f"[MIC] Matched device by name: '{dev_n}' (index={i})")
                    return i
            except Exception:
                pass

    # Bước 2: Microphone vật lý đầu tiên
    valid_physical_mics = get_real_physical_microphones()
    if valid_physical_mics:
        first_real = valid_physical_mics[0]
        for i in range(pa_instance.get_device_count()):
            try:
                dev_info = pa_instance.get_device_info_by_index(i)
                dev_n = dev_info.get("name", "")
                if dev_info.get("maxInputChannels", 0) > 0 and (first_real in dev_n or dev_n in first_real):
                    logger.debug(f"[MIC] Matched first physical mic: '{dev_n}' (index={i})")
                    return i
            except Exception:
                pass

    # Bước 3: Default input device (nếu là mic thật)
    try:
        default_dev = pa_instance.get_default_input_device_info()
        name = default_dev.get("name", "")
        if is_valid_physical_microphone(name):
            logger.debug(f"[MIC] Using system default: '{name}' (index={default_dev.get('index')})")
            return default_dev.get("index")
    except Exception:
        pass

    # Bước 4: Bất kỳ mic vật lý nào
    for i in range(pa_instance.get_device_count()):
        try:
            dev_info = pa_instance.get_device_info_by_index(i)
            name = dev_info.get("name", "")
            if dev_info.get("maxInputChannels", 0) > 0 and is_valid_physical_microphone(name):
                logger.debug(f"[MIC] Fallback to first valid mic: '{name}' (index={i})")
                return i
        except Exception:
            pass

    return None


def get_native_sample_rate(pa_instance, device_index: int) -> int:
    """Lấy sample rate gốc của thiết bị. Trả về 16000 nếu không lấy được."""
    try:
        dev_info = pa_instance.get_device_info_by_index(device_index)
        rate = int(dev_info.get("defaultSampleRate", 16000))
        return rate if rate > 0 else 16000
    except Exception:
        return 16000
