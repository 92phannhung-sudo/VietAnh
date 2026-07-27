import os
import json
import logging
import math
import struct
import urllib.request
import zipfile
from pathlib import Path
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("PatientApp")

def get_real_physical_microphones():
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
                    # Exclude truncated duplicates of existing QMediaDevices names
                    already_covered = any(name in r or r in name for r in raw_mics)
                    if not already_covered:
                        raw_mics.append(name)
        pa.terminate()
    except Exception:
        pass
    return raw_mics

def get_available_microphones():
    mics = ["Mặc định hệ thống"]
    raw_mics = get_real_physical_microphones()
    for name in raw_mics:
        if name not in mics:
            mics.append(name)
    return mics

class VoiceDetectorThread(QThread):
    capture_signal = Signal()
    keyword_signal = Signal(str)  # Emits: 'chụp', 'xóa', 'tiếp', 'xem'
    status_signal = Signal(str)
    volume_signal = Signal(int)  # 0 to 100
    log_signal = Signal(str)     # Emits live speech events and recognized text
    error_signal = Signal(str)
    download_progress = Signal(int) # 0 to 100

    def __init__(self, mic_name="default"):
        super().__init__()
        self.mic_name = mic_name
        self._stop = False
        self.pyaudio_stream = None
        self.pyaudio_instance = None
        self.last_trigger_time = 0
        self.cooldown_active = False

    def stop(self):
        self._stop = True
        if self.pyaudio_stream:
            try:
                if self.pyaudio_stream.is_active():
                    self.pyaudio_stream.stop_stream()
                self.pyaudio_stream.close()
                self.pyaudio_stream = None
            except Exception:
                pass
        self.wait(400)
        if self.isRunning():
            self.terminate()

    def download_model(self, dest_path):
        import config
        app_config = config.load_config()
        url = app_config.get("vosk_model_url", "http://192.168.1.100/models/vosk-model-small-vn-0.22.zip")
        zip_path = Path(dest_path).parent / "model.zip"
        
        try:
            self.status_signal.emit("Downloading Model from Intranet...")
            
            if url.startswith("http://") or url.startswith("https://"):
                def report_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = int(block_num * block_size * 100 / total_size)
                        self.download_progress.emit(min(100, percent))
                
                urllib.request.urlretrieve(url, zip_path, reporthook=report_hook)
            else:
                # Copy directly from local Intranet network share
                import shutil
                shutil.copy(url, zip_path)
                self.download_progress.emit(100)

            self.status_signal.emit("Extracting Model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(Path(dest_path).parent)
            
            if zip_path.exists():
                zip_path.unlink()
                
            self.status_signal.emit("Model Installed")
            return True
        except Exception as e:
            logger.error(f"Error downloading Vosk model: {str(e)}", exc_info=True)
            self.error_signal.emit(f"Download failed: {str(e)}")
            self.status_signal.emit("Model missing")
            if zip_path.exists():
                zip_path.unlink()
            return False

    def run(self):
        self._stop = False
        import config
        app_config = config.load_config()
        model_path = Path(app_config["vosk_model_path"])
        
        # Check and download model if missing
        if not model_path.exists():
            self.status_signal.emit("Model missing")
            return

        try:
            import vosk
            import pyaudio
        except ImportError as e:
            logger.error(f"Required voice libs not imported: {str(e)}")
            self.error_signal.emit(f"Library missing: {str(e)}")
            self.status_signal.emit("Error")
            return

        try:
            self.status_signal.emit("Initializing Voice Model...")
            model = vosk.Model(str(model_path))
            grammar_str = '["chụp", "xóa", "tiếp", "xem", "[unk]"]'
            rec = vosk.KaldiRecognizer(model, 16000, grammar_str)
            
            import time
            last_partial = ""
            current_vol = 0
            
            while not self._stop:
                try:
                    if not self.pyaudio_instance:
                        self.pyaudio_instance = pyaudio.PyAudio()
                        
                    # Select input device based on self.mic_name or config
                    device_index = None
                    mic_target = self.mic_name if (self.mic_name and self.mic_name != "default" and self.mic_name != "Mặc định hệ thống") else app_config.get("microphone_name", "default")
                    
                    if mic_target and mic_target != "default" and mic_target != "Mặc định hệ thống":
                        for i in range(self.pyaudio_instance.get_device_count()):
                            try:
                                dev_info = self.pyaudio_instance.get_device_info_by_index(i)
                                dev_n = dev_info.get("name", "")
                                if dev_info.get("maxInputChannels", 0) > 0 and (mic_target in dev_n or dev_n in mic_target):
                                    device_index = i
                                    break
                            except Exception:
                                pass

                    if device_index is None:
                        try:
                            default_dev = self.pyaudio_instance.get_default_input_device_info()
                            device_index = default_dev.get("index")
                        except Exception:
                            for i in range(self.pyaudio_instance.get_device_count()):
                                try:
                                    dev_info = self.pyaudio_instance.get_device_info_by_index(i)
                                    if dev_info.get("maxInputChannels", 0) > 0:
                                        device_index = i
                                        break
                                except Exception:
                                    pass

                    if device_index is None:
                        self.status_signal.emit("Không có Microphone")
                        time.sleep(2.0)
                        continue

                    # Attempt stream opening
                    try:
                        self.pyaudio_stream = self.pyaudio_instance.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=800
                        )
                        self.pyaudio_stream.start_stream()
                        self.status_signal.emit("Listening")
                        logger.info(f"Vosk voice detector started listening on device index {device_index}.")
                    except Exception as open_err:
                        logger.warning(f"[MIC_HOTPLUG] Cannot open mic device index {device_index}: {open_err}. Retrying in 2s...")
                        self.cleanup_stream()
                        time.sleep(2.0)
                        continue

                    # Stream reading loop
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
                            logger.warning(f"[MIC_STREAM_LOST] Audio read error ({read_err}). Auto-reconnecting mic in 1.5s...")
                            self.log_signal.emit("⚠️ [CẢNH BÁO]: Mất kết nối Microphone. Đang tự động kết nối lại...")
                            time.sleep(1.5)
                            break # Break inner loop to re-open stream and re-detect device
                        
                        # Calculate Volume RMS for visual feedback
                        count = len(data) / 2
                        format_str = f"{int(count)}h"
                        shorts = struct.unpack(format_str, data)
                        sum_squares = sum(s * s for s in shorts)
                        rms = math.sqrt(sum_squares / count) if count > 0 else 0
                        raw_vol = min(100, int((rms / 1200.0) * 100))
                        current_vol = max(raw_vol, int(current_vol * 0.8))
                        self.volume_signal.emit(current_vol)
                        
                        # Check recognizer
                        keywords = ["chụp", "xóa", "tiếp", "xem"]
                        if rec.AcceptWaveform(data):
                            res = json.loads(rec.Result())
                            text = res.get("text", "").lower().strip()
                            if text:
                                self.log_signal.emit(f"💬 [LỜI NÓI THỜI GIAN THẬT]: \"{text}\"")
                            for kw in keywords:
                                if kw in text and not self.cooldown_active:
                                    logger.info(f"[VOICE_KEYWORD] Detected keyword in final result: '{kw}'")
                                    self.log_signal.emit(f"✅ [ĐÃ KHỚP LỆNH CHUẨN]: \"{kw.upper()}\"")
                                    self.keyword_signal.emit(kw)
                                    self.capture_signal.emit()
                                    self.cooldown_active = True
                                    self.last_trigger_time = time.time()
                                    break
                        else:
                            partial_res = json.loads(rec.PartialResult())
                            partial_text = partial_res.get("partial", "").lower().strip()
                            if partial_text and partial_text != last_partial:
                                self.log_signal.emit(f"🎙️ [ĐANG LẮNG NGHE]: \"{partial_text}\"...")
                                for kw in keywords:
                                    if kw in partial_text and not self.cooldown_active:
                                        logger.info(f"[VOICE_KEYWORD] Detected keyword in partial result: '{kw}'")
                                        self.log_signal.emit(f"✅ [ĐÃ KHỚP LỆNH CHUẨN]: \"{kw.upper()}\"")
                                        self.keyword_signal.emit(kw)
                                        self.capture_signal.emit()
                                        self.cooldown_active = True
                                        self.last_trigger_time = time.time()
                                        break
                                last_partial = partial_text
                        
                        # Reset cooldown after 2.0 seconds
                        if self.cooldown_active and (time.time() - self.last_trigger_time > 2.0):
                            self.cooldown_active = False
                            last_partial = ""

                    self.cleanup_stream()

                except Exception as loop_err:
                    logger.warning(f"[MIC_AUTO_RECONNECT] Host error/device change ({loop_err}). Auto-reconnecting in 2.0s...")
                    self.cleanup_stream()
                    time.sleep(2.0)
                    
        except Exception as e:
            logger.error(f"Error in voice detector thread: {str(e)}", exc_info=True)
            self.status_signal.emit("Error")
        finally:
            self.cleanup()

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
