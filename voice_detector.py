"""
voice_detector — VoiceDetectorThread (Orchestrator)

Thread Qt chạy nền, lắng nghe microphone và phát lệnh giọng nói.
Logic thư viện nằm trong package voice_lib/.

Signals:
    capture_signal()   — Deprecated, giữ backward compatibility
    keyword_signal(str) — Lệnh đã khớp: "chụp", "xóa", "tiếp", "xem"
    status_signal(str)  — Trạng thái: "Listening", "Error", ...
    volume_signal(int)  — Mức âm lượng 0-100
    log_signal(str)     — Sự kiện nhận dạng để hiển thị UI
    error_signal(str)   — Thông báo lỗi
    download_progress(int) — Tiến trình tải model 0-100
"""

import logging
import time
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

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
    MIN_SPEECH_FRAMES,
    MAX_SPEECH_FRAMES,
    COOLDOWN_SECONDS,
)
from voice_lib.speech_recognizer import (
    match_vietnamese_keyword,
    WhisperRecognizer,
)

logger = logging.getLogger("PatientApp")


# ─── Re-exports cho backward compatibility với main.py ──────────────────────
# main.py gọi: voice_detector.get_available_microphones()
#               voice_detector.get_real_physical_microphones()
# Giữ nguyên để không cần sửa main.py.


class VoiceDetectorThread(QThread):
    """Thread Qt chạy nền: lắng nghe mic → VAD → Whisper → keyword matching → emit signal."""

    capture_signal = Signal()
    keyword_signal = Signal(str)     # "chụp", "xóa", "tiếp", "xem"
    status_signal = Signal(str)
    volume_signal = Signal(int)      # 0-100
    log_signal = Signal(str)
    error_signal = Signal(str)
    download_progress = Signal(int)  # 0-100

    def __init__(self, mic_name: str = "default"):
        super().__init__()
        self.mic_name = mic_name
        self.pending_mic_switch: str | None = None
        self._stop = False
        self.pyaudio_stream = None
        self.pyaudio_instance = None
        self.last_trigger_time: float = 0
        self.cooldown_active = False
        self.lib_status_msg: str = ""

    # ─── Public API ─────────────────────────────────────────────────────

    def set_microphone(self, mic_name: str):
        """Lên lịch chuyển mic an toàn (xử lý trên thread)."""
        if self.mic_name != mic_name:
            logger.info(f"[VOICE] Scheduled safe microphone switch to: '{mic_name}'")
            self.pending_mic_switch = mic_name

    def stop(self):
        """Dừng thread an toàn."""
        self._stop = True
        if self.isRunning():
            self.quit()
            self.wait(200)

    # ─── Main thread loop ───────────────────────────────────────────────

    def run(self):
        self._stop = False
        import config
        app_config = config.load_config()

        # Kiểm tra thư viện
        if not self._check_libraries():
            return

        # Khởi tạo Whisper recognizer
        recognizer = self._init_recognizer()

        # Main loop: mở mic → đọc audio → VAD → nhận dạng
        current_vol = 0
        while not self._stop:
            try:
                if not self.pyaudio_instance:
                    import pyaudio
                    self.pyaudio_instance = pyaudio.PyAudio()

                # Tìm device
                device_index = find_device_index(
                    self.pyaudio_instance,
                    self.mic_name,
                    app_config.get("microphone_name", "default"),
                )
                if device_index is None:
                    self.status_signal.emit("Không có Microphone")
                    time.sleep(2.0)
                    continue

                # Mở stream
                opened_rate, chunk_size = self._open_audio_stream(device_index)
                if opened_rate is None:
                    continue

                self.pyaudio_stream.start_stream()
                self.status_signal.emit("Listening")
                logger.info(f"Voice detector listening on device {device_index} ({opened_rate}Hz)")

                # Vòng lặp đọc audio + VAD
                current_vol = self._stream_loop(recognizer, opened_rate, chunk_size, current_vol)

                self.cleanup_stream()

            except Exception as loop_err:
                logger.warning(f"[MIC_AUTO_RECONNECT] Host error ({loop_err}). Reconnecting in 2s...")
                self.cleanup_stream()
                time.sleep(2.0)

        self.cleanup()

    # ─── Private helpers ────────────────────────────────────────────────

    def _check_libraries(self) -> bool:
        """Kiểm tra thư viện pyaudio có sẵn không."""
        try:
            import pyaudio  # noqa: F401
            return True
        except ImportError as e:
            logger.error(f"Required voice libs not imported: {e}")
            self.error_signal.emit(f"Library missing: {e}")
            self.log_signal.emit(f"❌ [THƯ VIỆN LỖI]: Không nạp được thư viện - {e}")
            self.status_signal.emit("Error")
            return False

    def _init_recognizer(self) -> WhisperRecognizer:
        """Khởi tạo WhisperRecognizer và emit trạng thái."""
        self.lib_status_msg = "📦 [THƯ VIỆN]: Đang nạp mô hình Whisper AI..."
        self.log_signal.emit(self.lib_status_msg)
        # "small" đã có cache local — beam_size=1 + vad_filter + max 2s speech cho real-time
        recognizer = WhisperRecognizer(model_size="small", device="cpu", compute_type="int8")

        if recognizer.is_available():
            self.lib_status_msg = "✅ [100% PURE WHISPER AI SMALL]: OpenAI Whisper AI Small (Real-Time Mode) ĐÃ SẴN SÀNG!"
        else:
            self.lib_status_msg = f"❌ [LỖI NẠP AI]: Không nạp được mô hình Whisper AI - {recognizer.load_error}"

        self.log_signal.emit(self.lib_status_msg)
        return recognizer

    def _open_audio_stream(self, device_index: int) -> tuple[int | None, int]:
        """Mở PyAudio stream. Thử native rate trước, fallback 16kHz.

        Returns:
            (opened_rate, chunk_size) hoặc (None, 0) nếu không mở được.
        """
        import pyaudio

        native_rate = get_native_sample_rate(self.pyaudio_instance, device_index)

        # Thử native rate
        try:
            chunk_size = int(native_rate * 0.05)  # 50ms per chunk
            self.pyaudio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=native_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk_size,
            )
            return native_rate, chunk_size
        except Exception:
            pass

        # Fallback 16kHz
        try:
            chunk_size = 800  # 50ms at 16kHz
            self.pyaudio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk_size,
            )
            return 16000, chunk_size
        except Exception as e:
            logger.warning(f"[MIC_HOTPLUG] Cannot open mic {device_index}: {e}. Retry in 2s...")
            self.cleanup_stream()
            time.sleep(2.0)
            return None, 0

    def _stream_loop(
        self,
        recognizer: WhisperRecognizer,
        opened_rate: int,
        chunk_size: int,
        current_vol: int,
    ) -> int:
        """Vòng lặp đọc audio stream, xử lý VAD, gửi tới Whisper khi kết thúc lời nói.

        Returns:
            current_vol cuối cùng (để truyền lại cho lần mở stream kế tiếp).
        """
        speech_frames: list[bytes] = []
        silence_counter = 0
        is_speaking = False

        while not self._stop:
            # Kiểm tra yêu cầu chuyển mic
            if self.pending_mic_switch:
                self.mic_name = self.pending_mic_switch
                self.pending_mic_switch = None
                logger.info(f"[VOICE] Safe mic switch to '{self.mic_name}'")
                self.cleanup_stream()
                break

            # Đọc audio chunk
            chunk_result = self._read_audio_chunk(opened_rate, chunk_size)
            if chunk_result is None:
                # Stream bị mất kết nối, cần mở lại
                break
            if not chunk_result:
                # Chưa đủ data, chờ tiếp
                if current_vol > 0:
                    current_vol = max(0, int(current_vol * 0.7))
                    self.volume_signal.emit(current_vol)
                continue

            raw_data, agc_data = chunk_result

            # Tính volume cho UI (dùng AGC data cho visual feedback đẹp hơn)
            rms_agc = compute_rms(agc_data)
            raw_vol = compute_volume_level(rms_agc)
            current_vol = max(raw_vol, int(current_vol * 0.8))  # Smooth decay
            self.volume_signal.emit(current_vol)

            # VAD: dùng RMS RAW (trước AGC) để tránh noise bị AGC boost
            rms_raw = compute_rms(raw_data)

            if rms_raw > VAD_RAW_RMS_THRESHOLD:
                if not is_speaking:
                    logger.info(f"[VAD] Speech START (rms_raw={rms_raw:.0f})")
                silence_counter = 0
                is_speaking = True
                speech_frames.append(agc_data)  # Lưu AGC data cho Whisper

                # ── Force transcribe nếu nói quá lâu (real-time) ──
                if len(speech_frames) >= MAX_SPEECH_FRAMES:
                    logger.info(f"[VAD] Force transcribe ({len(speech_frames)} frames = {len(speech_frames)*0.05:.1f}s)")
                    if recognizer.is_available():
                        self._handle_speech_end(recognizer, speech_frames)
                    speech_frames = []
                    is_speaking = False

            elif is_speaking:
                silence_counter += 1
                speech_frames.append(agc_data)

                # Kết thúc lời nói → nhận dạng
                if silence_counter >= SILENCE_FRAME_COUNT:
                    logger.info(f"[VAD] Speech END ({len(speech_frames)} frames)")
                    is_speaking = False
                    silence_counter = 0

                    if recognizer.is_available() and len(speech_frames) > MIN_SPEECH_FRAMES:
                        self._handle_speech_end(recognizer, speech_frames)

                    speech_frames = []

            # Reset cooldown
            if self.cooldown_active and (time.time() - self.last_trigger_time > COOLDOWN_SECONDS):
                self.cooldown_active = False

        return current_vol

    def _read_audio_chunk(self, opened_rate: int, chunk_size: int) -> tuple[bytes, bytes] | None:
        """Đọc 1 chunk audio từ stream, resample + AGC.

        Returns:
            tuple[bytes, bytes]: (raw_16k, agc_data) — raw dùng cho VAD, agc dùng cho Whisper
            False: Chưa đủ data (chờ tiếp)
            None: Lỗi stream (cần mở lại)
        """
        try:
            avail = self.pyaudio_stream.get_read_available()
            if avail < chunk_size:
                time.sleep(0.01)
                return False

            raw_bytes = self.pyaudio_stream.read(chunk_size, exception_on_overflow=False)
            if len(raw_bytes) == 0:
                return False

            data_16k = resample_pcm16(raw_bytes, opened_rate, 16000)
            data_agc = apply_software_agc(data_16k)
            return (data_16k, data_agc)

        except Exception as e:
            logger.warning(f"[MIC_STREAM_LOST] Audio read error ({e}). Reconnecting in 1.5s...")
            self.log_signal.emit("⚠️ [CẢNH BÁO]: Mất kết nối Microphone. Đang tự động kết nối lại...")
            time.sleep(1.5)
            return None

    def _handle_speech_end(self, recognizer: WhisperRecognizer, speech_frames: list[bytes]):
        """Xử lý khi VAD phát hiện kết thúc lời nói: gửi tới Whisper → khớp lệnh."""
        text = recognizer.transcribe(speech_frames)
        if not text:
            return

        logger.info(f"[WHISPER_AI_VAD] Decoded: '{text}'")
        self.log_signal.emit(f'🤖 [OpenAI Whisper AI]: "{text}"')

        matched_cmd = match_vietnamese_keyword(text)
        if matched_cmd and not self.cooldown_active:
            logger.info(f"[WHISPER_KEYWORD] Matched: '{matched_cmd}' from: '{text}'")
            self.log_signal.emit(f'✅ [ĐÃ KHỚP LỆNH WHISPER]: "{matched_cmd.upper()}" (từ: "{text}")')
            self.keyword_signal.emit(matched_cmd)
            self.cooldown_active = True
            self.last_trigger_time = time.time()

    # ─── Cleanup ────────────────────────────────────────────────────────

    def cleanup_stream(self):
        """Đóng PyAudio stream hiện tại."""
        try:
            if self.pyaudio_stream:
                if self.pyaudio_stream.is_active():
                    self.pyaudio_stream.stop_stream()
                self.pyaudio_stream.close()
                self.pyaudio_stream = None
        except Exception as e:
            logger.error(f"Error cleaning up pyaudio_stream: {e}")

    def cleanup(self):
        """Đóng stream + terminate PyAudio instance."""
        self.cleanup_stream()
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
        except Exception as e:
            logger.error(f"Error cleaning up pyaudio_instance: {e}")
