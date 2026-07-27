# voice_lib — Thư viện nhận dạng giọng nói tiếng Việt
# Dành cho dự án PatientCaptureApp (VietAnh)

from voice_lib.microphone import (
    is_valid_physical_microphone,
    get_real_physical_microphones,
    get_available_microphones,
    find_device_index,
    get_native_sample_rate,
)
from voice_lib.audio_processing import (
    resample_pcm16,
    apply_software_agc,
    compute_rms,
    compute_volume_level,
    VAD_RMS_THRESHOLD,
    VAD_RAW_RMS_THRESHOLD,
    SILENCE_FRAME_COUNT,
    COOLDOWN_SECONDS,
)
from voice_lib.speech_recognizer import (
    KEYWORD_SYNONYMS,
    match_vietnamese_keyword,
    WhisperRecognizer,
)

__all__ = [
    # microphone
    "is_valid_physical_microphone",
    "get_real_physical_microphones",
    "get_available_microphones",
    "find_device_index",
    "get_native_sample_rate",
    # audio_processing
    "resample_pcm16",
    "apply_software_agc",
    "compute_rms",
    "compute_volume_level",
    "VAD_RMS_THRESHOLD",
    "VAD_RAW_RMS_THRESHOLD",
    "SILENCE_FRAME_COUNT",
    "COOLDOWN_SECONDS",
    # speech_recognizer
    "KEYWORD_SYNONYMS",
    "match_vietnamese_keyword",
    "WhisperRecognizer",
]
