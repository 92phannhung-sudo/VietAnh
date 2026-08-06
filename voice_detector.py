"""
Voice Detector Thread — sherpa-onnx Streaming ASR (Vietnamese Zipformer INT8)
Replaces legacy Vosk engine with sherpa-onnx for better Vietnamese recognition
and noise resistance. Cross-platform: Windows (WASAPI) + macOS (CoreAudio).
"""

import json
import logging
import math
import struct
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("PatientApp")

# ---------- Model path resolution ----------

SHERPA_MODEL_DIR_NAME = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"


def _find_sherpa_model_dir() -> Path | None:
    """Search for the sherpa-onnx model in standard locations."""
    import sys
    candidates = []

    # 1. Bundled with app (PyInstaller frozen or dev)
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    candidates.append(app_dir / "models" / SHERPA_MODEL_DIR_NAME)
    candidates.append(app_dir / SHERPA_MODEL_DIR_NAME)

    # 2. %APPDATA% / user data
    import os
    appdata = os.getenv("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "PatientCaptureApp" / SHERPA_MODEL_DIR_NAME)

    # 3. macOS ~/Library fallback
    home = Path.home()
    candidates.append(home / "Library" / "Application Support" / "PatientCaptureApp" / SHERPA_MODEL_DIR_NAME)

    for p in candidates:
        if p.exists() and (p / "tokens.txt").exists():
            logger.info(f"[VOICE] Found model directory at: {p}")
            return p
    logger.warning(f"[VOICE] Model directory not found in candidate paths: {[str(c) for c in candidates]}")
    return None


def _auto_download_sherpa_model() -> Path | None:
    """Attempt to download and extract sherpa-onnx model if missing."""
    import urllib.request
    import tarfile
    import shutil

    app_dir = Path(__file__).parent
    models_dir = app_dir / "models"
    models_dir.mkdir(exist_ok=True)
    target_dir = models_dir / SHERPA_MODEL_DIR_NAME
    url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2"
    archive_path = models_dir / "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2"

    try:
        logger.info(f"[VOICE] Auto-downloading sherpa-onnx model from {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response, open(archive_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=models_dir)
        
        if archive_path.exists():
            archive_path.unlink()
        
        if target_dir.exists() and (target_dir / "tokens.txt").exists():
            logger.info(f"[VOICE] Auto-downloaded model successfully to {target_dir}")
            return target_dir
    except Exception as e:
        logger.warning(f"[VOICE] Auto-download model failed: {e}")
        if archive_path.exists():
            try:
                archive_path.unlink()
            except Exception:
                pass
    return None


# ---------- Microphone discovery (cross-platform) ----------

def get_real_physical_microphones():
    """Discover real input devices via QMediaDevices + PyAudio fallback."""
    raw_mics = []
    try:
        from PySide6.QtMultimedia import QMediaDevices
        for mic in QMediaDevices.audioInputs():
            desc = mic.description().strip()
            if desc and desc not in raw_mics:
                raw_mics.append(desc)
    except Exception:
        pass
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                name = dev.get("name", "").strip()
                if name and "Primary" not in name and "Mapper" not in name:
                    already_covered = any(name in r or r in name for r in raw_mics)
                    if not already_covered:
                        raw_mics.append(name)
        pa.terminate()
    except Exception:
        pass
    return raw_mics


def get_available_microphones():
    mics = ["Mặc định hệ thống"]
    for name in get_real_physical_microphones():
        if name not in mics:
            mics.append(name)
    return mics


# ---------- Voice Detector Thread ----------

class VoiceDetectorThread(QThread):
    """Streaming ASR using sherpa-onnx Zipformer Vietnamese INT8 model."""

    capture_signal = Signal()
    keyword_signal = Signal(str)   # Emits matched keyword: 'chụp', 'xóa', 'tiếp', etc.
    status_signal = Signal(str)
    volume_signal = Signal(int)    # 0-100
    log_signal = Signal(str)
    error_signal = Signal(str)
    download_progress = Signal(int)
    comparison_signal = Signal(str, str, float) # local_text, google_text, similarity_percent
    patient_info_signal = Signal(dict)          # Emits parsed patient demographic dict

    # Vietnamese clinical voice commands
    KEYWORDS = [
        "chụp", "chụp ảnh",
        "xóa hết", "xóa tất cả",  # Must be before "xóa" for longest-match-first
        "xóa", "xóa ảnh",
        "tiếp", "bệnh nhân tiếp",
        "xem",
        "tìm", "tìm kiếm", "tra cứu",
        "bắt đầu", "tạo phiên", "bắt đầu phiên",
        "hoàn thành",
    ]

    def __init__(self, mic_name="default"):
        super().__init__()
        self.mic_name = mic_name
        self._stop = False
        self.pyaudio_stream = None
        self.pyaudio_instance = None
        self.last_trigger_time = 0
        self.cooldown_active = False
        self._pending_field = None      # e.g. 'full_name', 'birth_year', 'gender'
        self._pending_field_time = 0    # timestamp when pending was set (expires after 8s)

    def stop(self):
        self._stop = True
        self.cleanup_stream()
        self.wait(1500)

    # ---------- sherpa-onnx recognizer factory ----------

    def _create_recognizer(self, model_dir: Path):
        """Create a sherpa_onnx.OfflineRecognizer from local Zipformer Transducer model."""
        import sherpa_onnx

        encoder = str(model_dir / "encoder.int8.onnx")
        decoder = str(model_dir / "decoder.onnx")
        joiner = str(model_dir / "joiner.int8.onnx")
        tokens = str(model_dir / "tokens.txt")

        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            num_threads=2,
            sample_rate=16000,
            feature_dim=80,
            provider="cpu",
        )
        return recognizer

    # ---------- Main thread loop ----------

    def run(self):
        self._stop = False

        # 1. Find model
        model_dir = _find_sherpa_model_dir()
        if model_dir is None:
            logger.info("[VOICE] Model directory missing, attempting auto-download...")
            self.status_signal.emit("Đang tải model Voice AI...")
            model_dir = _auto_download_sherpa_model()

        if model_dir is None:
            self.status_signal.emit("Model missing")
            self.error_signal.emit(f"Không tìm thấy thư mục model '{SHERPA_MODEL_DIR_NAME}' trong models/ hoặc %APPDATA%.")
            logger.error(f"[VOICE] sherpa-onnx model directory not found: {SHERPA_MODEL_DIR_NAME}")
            return

        # 2. Import dependencies
        try:
            import sherpa_onnx
            import pyaudio
            import numpy as np
        except ImportError as e:
            logger.error(f"Required voice libs not imported: {e}")
            self.error_signal.emit(f"Library missing: {e}")
            self.status_signal.emit("Error")
            return

        # 3. Create recognizer
        try:
            self.status_signal.emit("Initializing sherpa-onnx...")
            recognizer = self._create_recognizer(model_dir)
            logger.info(f"[VOICE] sherpa-onnx recognizer created from {model_dir}")
        except Exception as e:
            logger.error(f"[VOICE] Failed to create sherpa-onnx recognizer: {e}", exc_info=True)
            self.error_signal.emit(f"Model load error: {e}")
            self.status_signal.emit("Error")
            return

        # 4. Main reconnect loop
        current_vol = 0
        while not self._stop:
            try:
                # Open mic
                if not self.pyaudio_instance:
                    self.pyaudio_instance = pyaudio.PyAudio()

                device_index = self._resolve_mic_device()
                if device_index is None:
                    self.status_signal.emit("Không có Microphone")
                    time.sleep(2.0)
                    continue

                try:
                    self.pyaudio_stream = self.pyaudio_instance.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=800,
                    )
                    self.pyaudio_stream.start_stream()
                    self.status_signal.emit("Listening (sherpa-onnx)")
                    logger.info(f"[VOICE] Streaming ASR started on mic device {device_index}")
                except Exception as open_err:
                    logger.warning(f"[MIC_HOTPLUG] Cannot open mic {device_index}: {open_err}. Retrying 2s...")
                    self.cleanup_stream()
                    time.sleep(2.0)
                    continue

                # Audio buffer for streaming decode (16kHz samples)
                audio_buffer = []
                silence_chunks = 0
                has_speech = False

                # 5. Read audio loop
                while not self._stop:
                    try:
                        avail = self.pyaudio_stream.get_read_available()
                        if avail < 800:
                            time.sleep(0.01)
                            if current_vol > 0:
                                current_vol = max(0, int(current_vol * 0.7))
                                self.volume_signal.emit(current_vol)
                            continue

                        data = self.pyaudio_stream.read(800, exception_on_overflow=False)
                        if len(data) == 0:
                            continue
                    except Exception as read_err:
                        logger.warning(f"[MIC_STREAM_LOST] {read_err}. Reconnecting 1.5s...")
                        self.log_signal.emit("⚠️ [CẢNH BÁO]: Mất kết nối Microphone. Đang kết nối lại...")
                        time.sleep(1.5)
                        break

                    # Volume meter
                    count = len(data) // 2
                    shorts = struct.unpack(f"{count}h", data)
                    rms = math.sqrt(sum(s * s for s in shorts) / count) if count > 0 else 0
                    raw_vol = min(100, int((rms / 1200.0) * 100))
                    current_vol = max(raw_vol, int(current_vol * 0.8))
                    self.volume_signal.emit(current_vol)

                    # Feed audio buffer (float32 [-1, 1])
                    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    audio_buffer.extend(samples)

                    if raw_vol < 10:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0
                        has_speech = True

                    # Decode ONLY when actual speech occurred and silence boundary or max buffer reached
                    if len(audio_buffer) >= 12000 and (silence_chunks >= 4 or len(audio_buffer) >= 48000):
                        try:
                            if has_speech:
                                stream = recognizer.create_stream()
                                stream.accept_waveform(16000, np.array(audio_buffer, dtype=np.float32))
                                recognizer.decode_stream(stream)
                                text = stream.result.text.strip().lower()
                                
                                # Filter out noise hallucinations (common single-syllable noise artifacts)
                                if text and text not in ("đấy", "đây", "ừ", "à", "ơi", "thấy", "tái"):
                                    logger.info(f"[VOICE_TEXT] Recognized raw text: '{text}'")
                                    self.log_signal.emit(f"💬 [sherpa-onnx]: \"{text}\"")
                                    kw_matched = self._match_keywords(text)
                                    self._async_compare_google_voice(list(audio_buffer), text)
                                    if not kw_matched:
                                        self._process_voice_for_patient(text)
                                else:
                                    logger.debug(f"[VOICE_HALLUCINATION_FILTERED] Discarded noise artifact: '{text}'")
                        except Exception as dec_err:
                            logger.warning(f"[VOICE_DECODE_ERR] {dec_err}")
                        finally:
                            audio_buffer.clear()
                            silence_chunks = 0
                            has_speech = False

                    # Cooldown reset
                    if self.cooldown_active and (time.time() - self.last_trigger_time > 2.0):
                        self.cooldown_active = False

                self.cleanup_stream()

            except Exception as loop_err:
                logger.warning(f"[MIC_AUTO_RECONNECT] {loop_err}. Reconnecting 2s...")
                self.cleanup_stream()
                time.sleep(2.0)

        self.cleanup()

    # ---------- Patient voice processing with pending field state ----------

    def _process_voice_for_patient(self, text: str):
        """
        Process recognized text for patient demographic input.
        Supports 2-step input: keyword first (e.g. "họ và tên"), then value (e.g. "Lương Thế Vinh").
        """
        try:
            from src.patient_voice_parser import (
                parse_patient_speech, detect_pending_field, fill_pending_field,
                _viet_words_to_digits
            )

            # Convert Vietnamese digit words to numbers
            converted_text = _viet_words_to_digits(text)

            # Step A: Check if there's a pending field from a previous keyword-only utterance
            if self._pending_field and (time.time() - self._pending_field_time < 8.0):
                pending = self._pending_field
                self._pending_field = None  # Clear pending state
                p_info = fill_pending_field(pending, converted_text)
                if p_info:
                    logger.info(f"[VOICE_PENDING_FILLED] Field '{pending}' filled with '{converted_text}': {p_info}")
                    self.log_signal.emit(f"✅ [ĐIỀN TRƯỜNG]: {pending} ← \"{converted_text}\"")
                    self.patient_info_signal.emit(p_info)
                    return
                else:
                    logger.info(f"[VOICE_PENDING_MISMATCH] Pending '{pending}' but text '{converted_text}' doesn't fit. Trying normal parse...")
                    # Fall through to normal parsing
            else:
                # Clear expired pending
                self._pending_field = None

            # Step B: Try normal parse (single-field keyword+data or full sentence)
            p_info = parse_patient_speech(converted_text)
            if p_info:
                logger.info(f"[VOICE_PATIENT_PARSED] Extracted Patient Info: {p_info}")
                self.patient_info_signal.emit(p_info)
                return

            # Step C: Check if this is a keyword-only utterance → set pending field
            pending = detect_pending_field(converted_text)
            if pending:
                self._pending_field = pending
                self._pending_field_time = time.time()
                logger.info(f"[VOICE_PENDING_SET] Waiting for next utterance to fill field: '{pending}'")
                self.log_signal.emit(f"⏳ [CHỜ NHẬP]: {pending.upper().replace('_', ' ')}... (nói tiếp nội dung)")
                return

        except Exception as p_err:
            logger.warning(f"[PATIENT_VOICE_PARSE_ERR] {p_err}")

    # ---------- Keyword matching ----------

    def _match_keywords(self, text: str) -> bool:
        """Match recognized text against Vietnamese command keywords."""
        if self.cooldown_active:
            return False

        # Try exact substring match (longest match first)
        sorted_kw = sorted(self.KEYWORDS, key=len, reverse=True)
        for kw in sorted_kw:
            if kw in text:
                logger.info(f"[VOICE_KEYWORD] Matched: '{kw}' in '{text}'")
                self.log_signal.emit(f"✅ [ĐÃ KHỚP LỆNH]: \"{kw.upper()}\"")
                self.keyword_signal.emit(kw)
                self.cooldown_active = True
                self.last_trigger_time = time.time()
                return True

        # Optional: fuzzy match fallback (requires rapidfuzz)
        try:
            from rapidfuzz import fuzz
            for kw in sorted_kw:
                # Short keywords (<= 4 chars) require exact match or ratio >= 85 to prevent noise mis-triggers
                if len(kw) <= 4:
                    if kw in text.split():
                        score = 100
                    else:
                        score = fuzz.ratio(kw, text)
                else:
                    score = max(fuzz.ratio(kw, text), fuzz.partial_ratio(kw, text))
                    
                if score >= 85:
                    logger.info(f"[VOICE_KEYWORD_FUZZY] Fuzzy matched: '{kw}' ~ '{text}' (score: {score})")
                    self.log_signal.emit(f"✅ [KHỚP GẦN ĐÚNG]: \"{kw.upper()}\" ({score}%)")
                    self.keyword_signal.emit(kw)
                    self.cooldown_active = True
                    self.last_trigger_time = time.time()
                    return True
        except ImportError:
            pass  # rapidfuzz optional — exact match only
        return False

    def _async_compare_google_voice(self, pcm_float32_samples: list, local_text: str):
        """Asynchronously send audio buffer to Google Speech API for ASR comparison."""
        import threading

        def run_google():
            try:
                import io
                import wave
                import numpy as np
                import speech_recognition as sr
                from rapidfuzz import fuzz

                pcm_int16 = (np.array(pcm_float32_samples) * 32767).clip(-32768, 32767).astype(np.int16)
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(pcm_int16.tobytes())
                wav_io.seek(0)

                r = sr.Recognizer()
                with sr.AudioFile(wav_io) as source:
                    audio = r.record(source)

                google_text = r.recognize_google(audio, language="vi-VN").strip().lower()
                similarity = float(fuzz.ratio(local_text, google_text))
                logger.info(f"[VOICE_COMPARE] Offline: '{local_text}' | Google Voice: '{google_text}' | Accuracy Match: {similarity:.1f}%")
                self.log_signal.emit(f"🌐 [Google Voice]: \"{google_text}\" (Tương đồng: {similarity:.0f}%)")
                self.comparison_signal.emit(local_text, google_text, similarity)
            except Exception as e:
                logger.debug(f"[GOOGLE_VOICE_SKIP] {e}")

        threading.Thread(target=run_google, daemon=True).start()

    # ---------- Mic resolution ----------

    def _resolve_mic_device(self) -> int | None:
        """Resolve PyAudio device index from mic_name or config."""
        if not self.pyaudio_instance:
            return None

        import config
        app_config = config.load_config()
        mic_target = self.mic_name if (self.mic_name and self.mic_name not in ("default", "Mặc định hệ thống")) else app_config.get("microphone_name", "default")

        # Search by name
        if mic_target and mic_target not in ("default", "Mặc định hệ thống"):
            for i in range(self.pyaudio_instance.get_device_count()):
                try:
                    dev = self.pyaudio_instance.get_device_info_by_index(i)
                    if dev.get("maxInputChannels", 0) > 0:
                        dev_name = dev.get("name", "")
                        if mic_target in dev_name or dev_name in mic_target:
                            return i
                except Exception:
                    pass

        # System default
        try:
            return self.pyaudio_instance.get_default_input_device_info().get("index")
        except Exception:
            pass

        # First available
        for i in range(self.pyaudio_instance.get_device_count()):
            try:
                dev = self.pyaudio_instance.get_device_info_by_index(i)
                if dev.get("maxInputChannels", 0) > 0:
                    return i
            except Exception:
                pass
        return None

    # ---------- Cleanup ----------

    def cleanup_stream(self):
        try:
            if self.pyaudio_stream:
                if self.pyaudio_stream.is_active():
                    self.pyaudio_stream.stop_stream()
                self.pyaudio_stream.close()
                self.pyaudio_stream = None
        except Exception as e:
            logger.error(f"Error cleaning up pyaudio_stream: {e}")

    def cleanup(self):
        self.cleanup_stream()
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
        except Exception as e:
            logger.error(f"Error cleaning up pyaudio_instance: {e}")
