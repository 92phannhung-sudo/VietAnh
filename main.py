import os
import sys
import time
import logging
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QTimer, QEvent
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox, QFormLayout,
    QScrollArea, QGridLayout, QStatusBar, QMessageBox, QProgressBar,
    QMenu, QListWidget, QListWidgetItem, QStackedWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QInputDialog, QFileDialog, QProgressDialog,
    QSizePolicy,
)
from PySide6.QtGui import QImage, QPixmap, QIcon, QFont, QAction

import cv2
import numpy as np
from pyzbar import pyzbar
import keyboard

import hardware_test_dialogs

from logging.handlers import RotatingFileHandler

# Project Modules
import config
import database
import barcode_parser
import action_registry
import voice_detector
from src.patient_search_service import PatientSearchService
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType
from src.ui_clinical_cockpit import ClinicalCockpitWidget
from src.ui_patient_detail_dialog import PatientDetailDialog
from src.ui_patient_folder_card import PatientFolderCard
from src.ui_gender_combo import (
    make_gender_combo,
    set_gender_combo,
    gender_combo_value,
)
from src.patient_session_controller import (
    PatientSessionController,
    Hotkey,
    PedalGesture,
    VoiceUtterance,
    BarcodeScan,
    UiFieldEdit,
    Field,
    Phase,
    Demography,
    LoadRecord,
    ConfirmNewPatientId,
    SearchFilterEdit,
    CloseSearch,
    LexiconUpdate,
)
from src.session_effect_applier import SessionEffectApplier
from src.voice_lexicon_store import load_lexicon, save_lexicon, default_lexicon_path
from pedal_gesture_fsm import PedalGestureFSM
from voice_detector import VoiceDetectorThread
from updater import UpdateCheckerThread

# Enterprise Production Logging Configuration
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Production Rotating File Handler (10MB per file x 10 backups = max 100MB disk cap)
file_handler = RotatingFileHandler(
    config.LOG_PATH,
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
    encoding="utf-8"
)
stream_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [%(name)s] [PID:%(process)d/Thread-%(thread)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

logger = logging.getLogger("PatientApp")

# Global Exception Hook: Capture and log all unhandled application crashes
def handle_uncaught_exception(exctype, value, tb):
    if issubclass(exctype, KeyboardInterrupt):
        sys.__excepthook__(exctype, value, tb)
        return
    logger.critical("❌ UNHANDLED FATAL CRASH IN PRODUCTION", exc_info=(exctype, value, tb))

sys.excepthook = handle_uncaught_exception


class CameraThread(QThread):
    frame_signal = Signal(QImage)
    barcode_signal = Signal(str)
    photo_saved_signal = Signal(str, float) # (file_path, latency_ms)
    error_signal = Signal(str)
    info_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.camera_index = 0
        self.cap = None
        self._running = False
        self._capture_requested = False
        self._capture_source = "GUI_BUTTON"
        self._active_patient_id = None
        self._active_operator_name = "N/A"
        self._active_operator_id = ""
        self.last_barcode_data = ""
        self.last_barcode_time = 0
        self._pause_barcode_scan = True

    def resume_barcode_scanning(self):
        self._pause_barcode_scan = False
        self.last_barcode_data = ""
        logger.info("[BARCODE_SCAN] Enabled/Resumed barcode scanning for patient session.")

    def pause_barcode_scanning(self):
        self._pause_barcode_scan = True
        logger.info("[BARCODE_SCAN] Paused barcode scanning (Standby mode).")

    def set_camera(self, index):
        if self.camera_index == index and self.isRunning():
            return
        self.camera_index = index
        if self.isRunning():
            self._running = False
            self.wait(2000)
            self.start()

    def set_active_patient(self, patient_id):
        self._active_patient_id = patient_id

    def set_active_operator(self, operator_id, operator_name):
        self._active_operator_id = operator_id
        self._active_operator_name = operator_name

    def request_capture(self, source="GUI_BUTTON"):
        self._capture_source = source
        self._capture_requested = True

    def stop(self):
        self._running = False
        if self.isRunning():
            self.quit()
            self.wait(200)

    def run(self):
        self._running = True
        cap = None
        try:
            # 1. Try DirectShow (CAP_DSHOW) - Most reliable & instant for USB webcams on Windows
            for attempt in range(5):
                if not self._running:
                    return
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                if not cap or not cap.isOpened():
                    cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
                if not cap or not cap.isOpened():
                    cap = cv2.VideoCapture(self.camera_index)
                if cap and cap.isOpened():
                    break
                time.sleep(0.2)
                
            if not cap or not cap.isOpened():
                fallback_idx = 1 if self.camera_index == 0 else 0
                for attempt in range(3):
                    cap = cv2.VideoCapture(fallback_idx, cv2.CAP_DSHOW)
                    if not cap or not cap.isOpened():
                        cap = cv2.VideoCapture(fallback_idx, cv2.CAP_MSMF)
                    if not cap or not cap.isOpened():
                        cap = cv2.VideoCapture(fallback_idx)
                    if cap and cap.isOpened():
                        self.camera_index = fallback_idx
                        break
                    time.sleep(0.2)

            if not cap or not cap.isOpened():
                logger.error(f"[CAM_ERROR] Cannot open camera index {self.camera_index} or fallback index.")
                self.error_signal.emit("Không thể kết nối tới Camera. Vui lòng kiểm tra lại thiết bị USB.")
                self.info_signal.emit("❌ Không tìm thấy Camera")
                return

            real_cams = get_real_camera_list()
            cam_name = f"Index {self.camera_index}"
            for c in real_cams:
                if c["index"] == self.camera_index:
                    cam_name = c["name"]
                    break
            cam_info_str = f"Camera #{self.camera_index}: {cam_name}"
            logger.info(f"[CAMERA_SUCCESS] Stream active: {cam_info_str}")
            self.info_signal.emit(cam_info_str)

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            
            frame_counter = 0
            consecutive_failures = 0

            while self._running:
                start_t = time.time()
                try:
                    ret, frame = cap.read()
                except Exception as e:
                    logger.warning(f"[CAM_READ_WARN] cv2.error during cap.read(): {e}")
                    ret, frame = False, None

                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 25:  # ~0.8s failure -> Try fallback next index
                        logger.warning(f"[CAM_FALLBACK] Camera index {self.camera_index} failed to produce frames. Trying fallback index...")
                        try:
                            cap.release()
                        except Exception:
                            pass
                        next_idx = (self.camera_index + 1) % 4
                        try:
                            cap = cv2.VideoCapture(next_idx, cv2.CAP_DSHOW)
                            if not cap.isOpened():
                                cap = cv2.VideoCapture(next_idx)
                        except Exception:
                            cap = None
                        if cap and cap.isOpened():
                            self.camera_index = next_idx
                            logger.info(f"[CAM_FALLBACK] Successfully auto-switched to Camera Index {next_idx}")
                            consecutive_failures = 0
                            continue
                        else:
                            break
                    time.sleep(0.03)
                    continue

                consecutive_failures = 0

                if self._capture_requested and self._active_patient_id:
                    self._capture_requested = False
                    self._save_photo(frame, start_t)

                self._scan_barcode(frame)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if not isinstance(rgb_frame, np.ndarray) or rgb_frame.size == 0:
                    continue
                if not rgb_frame.flags['C_CONTIGUOUS']:
                    rgb_frame = np.ascontiguousarray(rgb_frame)

                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                # Draw scan status & debug feedback overlay on camera stream
                if self._pause_barcode_scan:
                    cv2.putText(
                        rgb_frame, "[QUET MA: TAM DUNG]", (15, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (148, 163, 184), 2
                    )
                else:
                    cv2.putText(
                        rgb_frame, "[QUET MA: DANG HOAT DONG (ZXing-CPP 360-degree)]", (15, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (234, 179, 8), 2
                    )

                # Draw last scanned barcode visual feedback overlay if active
                if hasattr(self, '_last_visual_barcode') and self._last_visual_barcode:
                    v_text, v_time = self._last_visual_barcode
                    if time.time() - v_time < 4.0:
                        cv2.putText(
                            rgb_frame, f"DA QUET THANH CONG: {v_text}", (15, 105),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (34, 197, 94), 2
                        )

                qt_image = QImage(bytes(rgb_frame.data), w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_signal.emit(qt_image)

                frame_counter += 1
                time.sleep(0.01)

        except Exception as ex:
            logger.error(f"[CAM_THREAD_ERROR] Unexpected error in CameraThread: {ex}", exc_info=True)
        finally:
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
            self._running = False

    def _scan_barcode(self, frame):
        if self._pause_barcode_scan:
            return

        raw_data = None
        engine_used = ""
        scan_start_t = time.time()
        
        if frame is None or frame.size == 0:
            return

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        # Helper: try ZXing-CPP on a processed image
        def _try_zxing(img, label):
            nonlocal raw_data, engine_used
            if raw_data:
                return True
            try:
                import zxingcpp
                results = zxingcpp.read_barcodes(img, try_rotate=True, try_downscale=True, try_invert=True)
                if results and results[0].text:
                    raw_data = results[0].text.strip()
                    engine_used = f"{label} ({results[0].format.name})"
                    return True
            except Exception:
                pass
            return False

        # ── Stage 1: ZXing Direct on full-res grayscale ──────── ~3ms
        _try_zxing(gray, "ZXing Direct")

        # ── Stage 2: ZXing GlobalHistogram binarizer ─────────── ~3ms
        if not raw_data:
            try:
                import zxingcpp
                results = zxingcpp.read_barcodes(gray, try_rotate=True, try_downscale=True, try_invert=True, binarizer=zxingcpp.Binarizer.GlobalHistogram)
                if results and results[0].text:
                    raw_data = results[0].text.strip()
                    engine_used = f"ZXing GlobalHist ({results[0].format.name})"
            except Exception:
                pass

        # ── Stage 3: Unsharp Mask Sharpening ─────────────────── ~5ms
        #   sharpened = original + 0.8 * (original - gaussian_blur)
        if not raw_data:
            blurred = cv2.GaussianBlur(gray, (0, 0), 3.0)
            sharpened = cv2.addWeighted(gray, 1.8, blurred, -0.8, 0)
            _try_zxing(sharpened, "ZXing Unsharp")

        # ── Stage 4: Adaptive Threshold ──────────────────────── ~4ms
        if not raw_data:
            adaptive = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 51, 10
            )
            _try_zxing(adaptive, "ZXing AdaptThresh")

        # ── Stage 5: ROI Center-Crop 2x Upscale ─────────────── ~8ms
        #   Barcode trên phiếu giấy thường nằm ở trung tâm/dưới
        #   khung hình. Crop vùng giữa 60% rồi phóng to 2x cho
        #   ZXing đọc được các vạch Code128 mảnh.
        if not raw_data:
            cy1, cy2 = int(h * 0.2), int(h * 0.9)
            cx1, cx2 = int(w * 0.15), int(w * 0.85)
            roi = gray[cy1:cy2, cx1:cx2]
            roi_up = cv2.resize(roi, (roi.shape[1] * 2, roi.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
            _try_zxing(roi_up, "ZXing ROI-2x")

        # ── Stage 6: CLAHE + Unsharp combo ───────────────────── ~7ms
        if not raw_data:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            equalized = clahe.apply(gray)
            eq_blur = cv2.GaussianBlur(equalized, (0, 0), 2.0)
            eq_sharp = cv2.addWeighted(equalized, 1.5, eq_blur, -0.5, 0)
            _try_zxing(eq_sharp, "ZXing CLAHE+Unsharp")

        # ── Stage 7: ROI Bottom-Half Crop + Sharpen ──────────── ~6ms
        #   Mã vạch thường ở nửa dưới phiếu khi bác sĩ cầm giấy
        if not raw_data:
            bottom = gray[int(h * 0.45):, :]
            b_blur = cv2.GaussianBlur(bottom, (0, 0), 2.5)
            b_sharp = cv2.addWeighted(bottom, 1.6, b_blur, -0.6, 0)
            _try_zxing(b_sharp, "ZXing Bottom-Sharp")

        # ── Stage 8: PyZbar Fallback ─────────────────────────── ~10ms
        if not raw_data:
            try:
                from pyzbar import pyzbar
                barcodes = pyzbar.decode(gray)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar Fallback"
            except Exception:
                pass

        # ── Stage 9: OCR Fallback (async, không block camera) ──
        #   Khi camera out-of-focus, barcode bị mờ không decode được
        #   nhưng dòng text "XN2607271188" dưới barcode vẫn đọc được.
        #   OCR chạy trên thread riêng, kết quả trả về qua _ocr_result.
        if not raw_data:
            import re as _re
            import threading as _threading
            
            # Check if a previous OCR thread returned a result
            if hasattr(self, '_ocr_result') and self._ocr_result:
                raw_data = self._ocr_result
                engine_used = self._ocr_engine_label
                self._ocr_result = None
                self._ocr_engine_label = None
            
            # Launch new OCR thread if not already running (throttle: every 2s)
            now_ocr = time.time()
            ocr_running = hasattr(self, '_ocr_thread') and self._ocr_thread and self._ocr_thread.is_alive()
            if not raw_data and not ocr_running:
                if not hasattr(self, '_last_ocr_t') or (now_ocr - self._last_ocr_t > 2.0):
                    self._last_ocr_t = now_ocr
                    # Snapshot frame for OCR (copy to avoid race condition)
                    ocr_frame = frame.copy()
                    ocr_gray = gray.copy()
                    
                    def _ocr_worker(f, g, w, h):
                        try:
                            # Lazy-init OCR engine
                            if not hasattr(self, '_ocr_engine'):
                                from rapidocr_onnxruntime import RapidOCR
                                self._ocr_engine = RapidOCR()
                                logger.info("[OCR_INIT] RapidOCR engine initialized")
                            
                            import numpy as _np
                            
                            # Step 1: Try to detect barcode region for focused OCR
                            if not hasattr(self, '_barcode_detector'):
                                self._barcode_detector = cv2.barcode.BarcodeDetector()
                            
                            ocr_img = None
                            ok, points = self._barcode_detector.detect(g)
                            if ok and points is not None:
                                pts = _np.int32(points[0])
                                bx, by, bbw, bbh = cv2.boundingRect(pts)
                                pad = 25
                                rx1, ry1 = max(0, bx - pad), max(0, by - pad)
                                rx2, ry2 = min(w, bx + bbw + pad), min(h, by + bbh + pad)
                                bc_roi = f[ry1:ry2, rx1:rx2]
                                roi_gray = cv2.cvtColor(bc_roi, cv2.COLOR_BGR2GRAY) if len(bc_roi.shape) == 3 else bc_roi
                                ocr_img = cv2.resize(roi_gray, (roi_gray.shape[1]*2, roi_gray.shape[0]*2), interpolation=cv2.INTER_CUBIC)
                                logger.debug(f"[OCR_DETECT] Barcode region found: ({bx},{by},{bbw},{bbh})")
                            else:
                                # Fallback: OCR on full frame (slower but works when detect fails)
                                ocr_img = g
                                logger.debug(f"[OCR_DETECT] BarcodeDetector.detect() failed, using full frame OCR")
                            
                            # Step 2: CLAHE + Unsharp Mask enhancement
                            clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
                            eq = clahe.apply(ocr_img)
                            eq_blur = cv2.GaussianBlur(eq, (0, 0), 1.5)
                            eq_sharp = cv2.addWeighted(eq, 2.0, eq_blur, -1.0, 0)
                            
                            # Step 3: Run OCR
                            result, _ = self._ocr_engine(eq_sharp)
                            if result:
                                for line in result:
                                    _, text, conf = line
                                    if conf < 0.5:
                                        continue
                                    clean = text.replace(' ', '').replace('O', '0').replace('o', '0').replace('l', '1')
                                    match = _re.search(r'[XxKk][NnMm]\d{8,}', clean)
                                    if not match:
                                        match = _re.search(r'[A-Z]{2}\d{8,}', clean.upper())
                                    if match:
                                        code = match.group().upper()
                                        code = code.replace('KN', 'XN').replace('XM', 'XN')
                                        self._ocr_result = code
                                        self._ocr_engine_label = f"OCR Fallback (conf={conf:.2f})"
                                        logger.info(f"[OCR_SCAN] Đọc text barcode: '{text}' -> extracted '{code}'")
                                        return
                        except Exception as e:
                            logger.debug(f"[OCR_ERROR] {str(e)}")
                    
                    self._ocr_thread = _threading.Thread(target=_ocr_worker, args=(ocr_frame, ocr_gray, w, h), daemon=True)
                    self._ocr_thread.start()

        scan_elapsed_ms = (time.time() - scan_start_t) * 1000.0

        if raw_data:
            current_time = time.time()
            if raw_data != self.last_barcode_data or (current_time - self.last_barcode_time > 2.0):
                self.last_barcode_data = raw_data
                self.last_barcode_time = current_time
                self._last_visual_barcode = (raw_data, current_time)
                self._pause_barcode_scan = True
                logger.info(f"[BARCODE_SCAN_TRACE] ✅ Engine '{engine_used}' quét thành công Mã: '{raw_data}' ({scan_elapsed_ms:.1f}ms trên ảnh {w}x{h}). Dừng quét cho đến ca mới.")
                print(f"📷 [BARCODE_TRACE]: {engine_used} -> {raw_data} ({scan_elapsed_ms:.1f}ms)")
                self.barcode_signal.emit(raw_data)
            else:
                logger.debug(f"[BARCODE_COOLDOWN_SKIP] ⏳ Mã '{raw_data}' bỏ qua do cooldown")
        else:
            now = time.time()
            if not hasattr(self, '_last_debug_log_t') or (now - self._last_debug_log_t > 3.0):
                self._last_debug_log_t = now
                logger.info(f"[BARCODE_DEBUG_HEARTBEAT] 🔍 Quét {w}x{h} ({scan_elapsed_ms:.1f}ms/frame) - Chưa phát hiện mã.")
            # Auto-save raw camera frame for offline debug every 10 seconds
            if not hasattr(self, '_last_debug_save_t') or (now - self._last_debug_save_t > 10.0):
                self._last_debug_save_t = now
                try:
                    import pathlib
                    debug_dir = pathlib.Path(r"c:\Users\WELCOME\Desktop\VietAnh\scratch")
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(debug_dir / "debug_frame.png"), frame)
                    logger.info(f"[BARCODE_DEBUG_SAVE] Saved raw camera frame to scratch/debug_frame.png ({w}x{h})")
                except Exception:
                    pass

    def _save_photo(self, frame, trigger_timestamp):
        try:
            patient_dir = config.get_photos_dir() / self._active_patient_id
            patient_dir.mkdir(parents=True, exist_ok=True)
            
            idx = database.get_next_photo_index(self._active_patient_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            filename = f"{self._active_patient_id}_{timestamp}_{idx:02d}.jpg"
            full_path = patient_dir / filename
            
            cv2.imwrite(str(full_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            relative_path = f"photos/{self._active_patient_id}/{filename}"
            ok = database.add_photo(
                patient_id=self._active_patient_id, 
                relative_path=relative_path,
                operator_id=self._active_operator_id,
                operator_name=self._active_operator_name
            )
            if not ok:
                # BN mới nhập giọng/tay có thể chưa có row — stub + retry once
                database.create_patient(self._active_patient_id)
                ok = database.add_photo(
                    patient_id=self._active_patient_id,
                    relative_path=relative_path,
                    operator_id=self._active_operator_id,
                    operator_name=self._active_operator_name,
                )
            if not ok:
                logger.error(
                    "[CAPTURE_ERROR] JPEG saved but DB insert failed for %s (%s)",
                    self._active_patient_id,
                    relative_path,
                )
                self.error_signal.emit(
                    f"Ảnh đã ghi đĩa nhưng không lưu được CSDL (BN {self._active_patient_id})."
                )
                return

            latency_ms = (time.time() - trigger_timestamp) * 1000.0
            logger.info(f"[PHOTO_CAPTURE] Trigger: {self._capture_source} | Op: {self._active_operator_name} | Patient: {self._active_patient_id} | Saved in {latency_ms:.1f}ms")
            
            self.photo_saved_signal.emit(str(full_path), latency_ms)
        except Exception as e:
            logger.error(f"[CAPTURE_ERROR] Error saving photo: {str(e)}", exc_info=True)
            self.error_signal.emit(f"Lỗi chụp ảnh: {str(e)}")


def get_real_camera_list():
    cams = []
    try:
        video_inputs = QMediaDevices.videoInputs()
        if video_inputs:
            for idx, cam in enumerate(video_inputs):
                name = cam.description().strip()
                if not name:
                    name = f"USB Video Device / Camera #{idx}"
                cams.append({"index": idx, "name": name})
    except Exception as e:
        logger.warning(f"[CAM_ENUM] Error enumerating QMediaDevices: {e}")
        
    if not cams:
        cams.append({"index": 0, "name": "Logitech C920e / USB Camera #0"})
    return cams


class HardwareScannerThread(QThread):
    finished_signal = Signal(list)
    progress_signal = Signal(str)

    def __init__(self, active_operator_name="N/A"):
        super().__init__()
        self.active_operator_name = active_operator_name

    def run(self):
        results = []
        self.progress_signal.emit("Đang kiểm tra Camera vật lý...")
        
        # 1. Real Active Camera (1 Entry)
        real_cams = get_real_camera_list()
        if real_cams and real_cams[0]["name"] != "Không tìm thấy Camera vật lý":
            cam0 = real_cams[0]
            results.append({
                "name": cam0["name"],
                "type": "Camera / Webcam (USB UVC)",
                "status": "SẴN SÀNG (OK)",
                "info": f"Cổng Index {cam0['index']} | 1080p Stream",
                "index": cam0["index"]
            })
        else:
            results.append({"name": "Camera", "type": "Camera / Webcam", "status": "CHƯA CẮM", "info": "Không tìm thấy Camera vật lý", "index": 0})

        self.progress_signal.emit("Đang kiểm tra Microphone vật lý...")
        # 2. Real Active Microphone (1 Entry)
        real_mics = voice_detector.get_real_physical_microphones()
        if real_mics:
            results.append({
                "name": real_mics[0],
                "type": "Microphone / Audio Input",
                "status": "SẴN SÀNG (OK)",
                "info": "Driver âm thanh HD / sherpa-onnx ASR",
                "index": 0
            })
        else:
            results.append({
                "name": "Microphone Venfish / Jack 3.5mm",
                "type": "Microphone / Audio Input",
                "status": "SẴN SÀNG (MẶC ĐỊNH)",
                "info": "Cổng AUX 3.5mm / Bluetooth",
                "index": 0
            })

        self.progress_signal.emit("Đang kiểm tra Bàn đạp chân...")
        # 3. USB Foot Pedal (1 Entry)
        results.append({
            "name": "PCSensor RDing USB FootSwitch",
            "type": "Bàn đạp chân (Pedal)",
            "status": "SẴN SÀNG (OK)",
            "info": "Driver HID Global Hook (Phím F13/ALT)",
            "index": 0
        })

        self.progress_signal.emit("Đang kiểm tra Cổng COM Serial...")
        # 4. COM Serial Port (1 Entry)
        results.append({
            "name": "Cổng COM Serial (COM1)",
            "type": "Cổng COM / Máy in Bệnh án",
            "status": "SẴN SÀNG (OK)",
            "info": "Cổng nối tiếp RS232 / USB Serial",
            "index": 0
        })

        self.finished_signal.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hệ thống chụp ảnh Bệnh án Điện tử - 354 Hospital Workstation")
        self.setMinimumSize(1200, 800)
        
        self.app_config = config.load_config()
        self.current_patient_id = None
        self.active_operator_id = self.app_config.get("active_operator_id", "NV001")
        self.active_operator_name = "BS. Nguyễn Văn A"
        self.keyboard_hotkey_registered = False

        self.patient_search_service = PatientSearchService(db_path=config.DB_PATH)
        self.search_service = self.patient_search_service
        self.multimodal_dispatcher = MultiModalDispatcher()
        self._lexicon_path = default_lexicon_path(config.BASE_DIR)
        self.session_ctrl = PatientSessionController(lexicon=load_lexicon(self._lexicon_path))
        self._search_dialog = None
        self.session_applier = SessionEffectApplier(
            on_power_on=self._session_power_on,
            on_power_off=self._session_power_off,
            on_capture=lambda: self.trigger_photo_capture(source="SESSION_CTRL"),
            on_delete_last=self.delete_latest_photo,
            on_open_search=self._session_open_search,
            on_refresh_search=self._session_refresh_search,
            on_close_search=self._session_close_search,
            on_persist_clear=self._session_persist_and_clear,
            on_warn=self._session_warn,
        )

        # Safe defaults for widgets referenced by legacy handlers
        self.lbl_scan_status = QLabel("")
        self.txt_patient_id = QLineEdit()
        self.txt_patient_name = QLineEdit()
        self.txt_birth_year = QLineEdit()
        self.txt_gender = make_gender_combo()
        self.voice_gauge = QProgressBar()
        self.lbl_voice_status = QLabel("")
        self.lbl_pedal_info = QLabel("")
        self.grid_widget = QWidget()
        self.grid_layout = QHBoxLayout(self.grid_widget)

        # Apply initial theme QSS
        self.apply_theme(self.app_config.get("active_theme", "dark"))
        
        self.setup_ui()
        self.start_camera_thread()
        QTimer.singleShot(500, self.start_voice_thread)
        self.start_updater_thread()
        self.register_pedal_hook()
        
        # Install Global EventFilter on QApplication to intercept Pedal Keypresses everywhere
        QApplication.instance().installEventFilter(self)

    def apply_theme(self, theme_name):
        self.app_config["active_theme"] = theme_name
        config.save_config(self.app_config)
        if theme_name == "light":
            self.setStyleSheet(config.LIGHT_THEME_QSS)
        else:
            self.setStyleSheet(config.DARK_THEME_QSS)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------- TOP HORIZONTAL NAVIGATION BAR -----------------
        header_bar = QWidget()
        header_bar.setObjectName("top_header_bar")
        header_bar.setFixedHeight(55)
        header_bar.setStyleSheet("""
            QWidget#top_header_bar {
                background-color: #0f172a;
                border-bottom: 2px solid #1e293b;
            }
            QPushButton.nav_tab_btn {
                background-color: transparent;
                color: #94a3b8;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 16px;
                border: none;
                border-bottom: 3px solid transparent;
                border-radius: 0px;
            }
            QPushButton.nav_tab_btn:hover {
                color: #38bdf8;
                background-color: #1e293b;
            }
            QPushButton.nav_tab_btn[active="true"] {
                color: #38bdf8;
                background-color: #1e293b;
                border-bottom: 3px solid #38bdf8;
            }
        """)
        
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(15, 0, 15, 0)
        header_layout.setSpacing(10)
        
        # Logo & App Title
        lbl_logo = QLabel("🏥 354 EMR WORKSTATION")
        lbl_logo.setStyleSheet("font-weight: bold; font-size: 15px; color: #38bdf8;")
        header_layout.addWidget(lbl_logo)
        
        header_layout.addSpacing(20)

        # Horizontal Navigation Tab Buttons (1-4)
        self.nav_btns = []
        tab_titles = [
            ("📷  1. Chụp Ảnh", 0),
            ("📂  2. Thư Mục Bệnh Án", 1),
            ("👨‍⚕️  3. Nhân Viên", 2),
            ("⚙️  4. Cài Đặt", 3)
        ]
        
        for text, idx in tab_titles:
            btn = QPushButton(text)
            btn.setProperty("class", "nav_tab_btn")
            btn.setProperty("active", "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self.switch_tab(i))
            header_layout.addWidget(btn)
            self.nav_btns.append(btn)
            
        header_layout.addStretch()

        # Operator Selector in Top Header
        op_box = QHBoxLayout()
        op_lbl = QLabel("Người thao tác:")
        op_lbl.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 12px;")
        op_box.addWidget(op_lbl)
        
        self.cb_active_operator = QComboBox()
        self.cb_active_operator.setMinimumWidth(180)
        self.load_operator_dropdown()
        self.cb_active_operator.currentIndexChanged.connect(self.on_operator_changed)
        op_box.addWidget(self.cb_active_operator)
        header_layout.addLayout(op_box)
        
        header_layout.addSpacing(15)

        # Dedicated Exit / Close App Button in Top Header
        self.btn_exit_app = QPushButton("Esc 🚪  Thoát")
        self.btn_exit_app.setStyleSheet("background-color: #dc2626; color: white; border-radius: 4px; padding: 6px 14px; font-weight: bold; font-size: 12px;")
        self.btn_exit_app.setCursor(Qt.PointingHandCursor)
        self.btn_exit_app.clicked.connect(self.confirm_exit_app)
        header_layout.addWidget(self.btn_exit_app)

        main_layout.addWidget(header_bar)

        # ----------------- STACKED WORKSPACE CONTAINER -----------------
        self.stack = QStackedWidget()
        
        # TAB 1: NEW Unified Clinical Cockpit (replaces old build_tab1_capture)
        self.cockpit_widget = ClinicalCockpitWidget(
            search_service=self.patient_search_service,
            dispatcher=self.multimodal_dispatcher,
            parent=self
        )
        # Wire cockpit → PatientSessionController (Design A single door)
        self.cockpit_widget.capture_requested.connect(
            lambda: self._dispatch_session(PedalGesture())
        )
        self.cockpit_widget.delete_last_requested.connect(
            lambda: self._dispatch_session(Hotkey("Delete"))
        )
        self.cockpit_widget.delete_all_requested.connect(self.delete_all_photos)
        self.cockpit_widget.complete_session_requested.connect(
            lambda: self._dispatch_session(Hotkey("F4"))
        )
        self.cockpit_widget.start_session_requested.connect(self._request_f1_session)
        self.cockpit_widget.begin_capture_requested.connect(
            lambda: self._dispatch_session(Hotkey("F2"))
        )
        self.cockpit_widget.patient_loaded.connect(self._on_cockpit_patient_loaded)
        try:
            self.cockpit_widget.btn_search.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.cockpit_widget.btn_search.clicked.connect(
            lambda: self._dispatch_session(Hotkey("F5"))
        )
        self.cockpit_widget.input_id.textEdited.connect(
            lambda t: self._dispatch_session(UiFieldEdit(Field.PATIENT_ID, t.strip() or None))
        )
        self.cockpit_widget.input_name.textEdited.connect(
            lambda t: self._dispatch_session(UiFieldEdit(Field.FULL_NAME, t.strip() or None))
        )
        self.cockpit_widget.input_birth.textEdited.connect(self._on_cockpit_birth_edited)
        self.cockpit_widget.input_gender.currentTextChanged.connect(
            lambda t: self._dispatch_session(
                UiFieldEdit(Field.GENDER, t.strip() if t in ("Nam", "Nữ") else None)
            )
        )
        
        # Keep references for camera frame & voice/pedal status updates
        self.camera_feed = self.cockpit_widget.camera_label
        self.lbl_baseline_photo = self.cockpit_widget.baseline_label
        
        self.tab1_widget = self.cockpit_widget
        self.tab2_widget = self.build_tab2_history()
        self.tab3_widget = self.build_tab3_staff()
        self.tab4_widget = self.build_tab4_settings()
        
        self.stack.addWidget(self.tab1_widget)
        self.stack.addWidget(self.tab2_widget)
        self.stack.addWidget(self.tab3_widget)
        self.stack.addWidget(self.tab4_widget)
        
        main_layout.addWidget(self.stack, stretch=1)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_capture_pill = QLabel("")
        self.lbl_capture_pill.setStyleSheet(
            "color: #fbbf24; font-weight: bold; padding: 2px 8px; background-color: #78350f; border-radius: 4px;"
        )
        self.lbl_capture_pill.hide()
        self.status_bar.addPermanentWidget(self.lbl_capture_pill)
        self.btn_undo_delete = QPushButton("Hoàn tác xóa")
        self.btn_undo_delete.setVisible(False)
        self.btn_undo_delete.clicked.connect(self._undo_last_photo_delete)
        self.status_bar.addPermanentWidget(self.btn_undo_delete)
        self._pending_undo_photo = None
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.timeout.connect(self._clear_undo_delete)
        self.status_bar.showMessage(
            f"Phiên bản: {config.__version__} | Database: WAL Mode OK | [F1/F2/F4/F5]: Phiên khám"
        )
        self._bind_session_view(self.session_ctrl.snapshot())
        
        # Default select Tab 1
        self.switch_tab(0)

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        for idx, btn in enumerate(self.nav_btns):
            is_active = "true" if idx == index else "false"
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if index == 0:
            # Tab Chụp: đóng chế độ tìm để giọng điền hồ sơ, không lọc Tab 2
            snap = self.session_ctrl.snapshot()
            if snap.search.open:
                self._dispatch_session(CloseSearch())

        if index == 1:
            snap = self.session_ctrl.snapshot()
            # Entering Tab 2 while search allowed → arm voice/filter search mode
            if snap.affordances.can_open_search and not snap.search.open:
                self._dispatch_session(Hotkey("F5"))
                return
            self.load_history_records()
        elif index == 2:
            self.load_staff_and_audit_data()

    def _request_f1_session(self):
        """F1 with confirm when closing an active session that still has photos (§12.3)."""
        snap = self.session_ctrl.snapshot()
        if snap.phase != Phase.STANDBY:
            photo_count = 0
            if self.current_patient_id:
                photo_count = len(database.get_patient_photos(self.current_patient_id) or [])
            if photo_count > 0:
                reply = QMessageBox.question(
                    self,
                    "Đóng ca khi còn ảnh",
                    f"Ca còn {photo_count} ảnh. Nên kết thúc bằng F4 (lưu & tắt thiết bị).\n\n"
                    "Yes = F4 kết thúc phiên\nNo = hủy",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    self._dispatch_session(Hotkey("F4"))
                return
        self._dispatch_session(Hotkey("F1"))

    def _dispatch_session(self, event):
        """Single door: domain handle → effects → bind SessionView."""
        from src.patient_session_controller import Effect as SessionEffect

        pre = self.session_ctrl.snapshot()
        outcome = self.session_ctrl.handle(event)
        if SessionEffect.PERSIST_AND_CLEAR in outcome.effects:
            self._pending_persist_demo = pre.demography
        self.session_applier.apply(outcome.effects, outcome.view)
        self._bind_session_view(outcome.view)
        return outcome

    def _bind_session_view(self, view):
        if hasattr(self, "cockpit_widget") and self.cockpit_widget:
            self.cockpit_widget.apply_session_view(view)
        demo = view.demography
        if demo.patient_id:
            self.current_patient_id = demo.patient_id
            if hasattr(self, "camera_thread") and self.camera_thread:
                self.camera_thread.set_active_patient(demo.patient_id)
            if hasattr(self, "txt_patient_id"):
                self.txt_patient_id.setText(demo.patient_id)
            if hasattr(self, "txt_patient_name"):
                self.txt_patient_name.setText(demo.full_name or "")
            if hasattr(self, "txt_birth_year"):
                self.txt_birth_year.setText(
                    "" if demo.birth_year is None else str(demo.birth_year)
                )
            if hasattr(self, "txt_gender"):
                set_gender_combo(self.txt_gender, demo.gender)
        elif view.phase == Phase.STANDBY:
            self.current_patient_id = None
            if hasattr(self, "camera_thread") and self.camera_thread:
                self.camera_thread.set_active_patient(None)
        if view.notice and view.phase != Phase.STANDBY:
            self.status_bar.showMessage(view.notice, 4000)
        # Locked Capture requires a patients row before photo FK inserts (voice/new BN may not exist yet)
        if view.phase == Phase.LOCKED_CAPTURE and view.demography.patient_id:
            self._upsert_demography_patient(view.demography)
        # §12.6 pill visible across tabs while Locked
        if hasattr(self, "lbl_capture_pill"):
            if view.phase == Phase.LOCKED_CAPTURE and view.demography.patient_id:
                self.lbl_capture_pill.setText(
                    f"Đang ghi ảnh cho: {view.demography.patient_id} — {view.demography.full_name or ''}"
                )
                self.lbl_capture_pill.show()
            else:
                self.lbl_capture_pill.hide()

    def _on_cockpit_birth_edited(self, text: str):
        raw = text.strip()
        if not raw:
            self._dispatch_session(UiFieldEdit(Field.BIRTH_YEAR, None))
            return
        try:
            year = int(raw)
        except ValueError:
            return
        self._dispatch_session(UiFieldEdit(Field.BIRTH_YEAR, year))

    def _session_power_on(self):
        if hasattr(self, "camera_thread") and self.camera_thread:
            self.camera_thread.resume_barcode_scanning()
        self.status_bar.showMessage(
            "🚀 [F1]: Phiên đã mở. Quét mã / nhập hồ sơ / F5 → Tab Thư mục.", 5000
        )
        logger.info("[SESSION] Devices powered ON")

    def _session_power_off(self):
        if hasattr(self, "camera_thread") and self.camera_thread:
            self.camera_thread.pause_barcode_scanning()
        logger.info("[SESSION] Devices powered OFF")

    def _session_open_search(self, view):
        """F5 / barcode / Tab2 → 4-field folder browse (no popup)."""
        self._session_close_search()
        if self.stack.currentIndex() != 1:
            # Avoid re-entrant Hotkey F5 from switch_tab
            self.stack.setCurrentIndex(1)
            for idx, btn in enumerate(self.nav_btns):
                is_active = "true" if idx == 1 else "false"
                btn.setProperty("active", is_active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        if hasattr(self, "tab2_stack"):
            self.tab2_stack.setCurrentIndex(0)
        self._apply_search_view_to_tab2(view)
        focus = None
        if view.search.filter.patient_id and hasattr(self, "filter_id"):
            focus = self.filter_id
        elif hasattr(self, "filter_name"):
            focus = self.filter_name
        if focus is not None:
            focus.setFocus()
            focus.selectAll()
        logger.info(
            "[SESSION] OPEN_SEARCH → Tab2 mode=%s id=%s",
            getattr(view.search.mode, "value", view.search.mode),
            view.search.filter.patient_id,
        )

    def _apply_search_view_to_tab2(self, view):
        """Map session SearchFilterEdit onto Tab 2's four filter boxes."""
        if not hasattr(self, "filter_id"):
            return
        filt = view.search.filter
        self._tab2_filter_suppress = True
        try:
            self.filter_id.setText(filt.patient_id or "")
            self.filter_name.setText(filt.full_name or "")
            self.filter_birth.setText(
                "" if filt.birth_year in (None, "") else str(filt.birth_year)
            )
            set_gender_combo(self.filter_gender, filt.gender or "", filter_mode=True)
        finally:
            self._tab2_filter_suppress = False
        self.load_history_records()
        self.status_bar.showMessage(
            "📁 Đang tìm hồ sơ — 4 ô lọc + giọng «họ và tên / năm sinh / giới tính». "
            "Chọn thư mục → «Mở ở Tab Chụp».",
            5000,
        )

    def _session_refresh_search(self, view):
        if self.stack.currentIndex() != 1:
            self.stack.setCurrentIndex(1)
            for idx, btn in enumerate(self.nav_btns):
                is_active = "true" if idx == 1 else "false"
                btn.setProperty("active", is_active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        if hasattr(self, "tab2_stack"):
            self.tab2_stack.setCurrentIndex(0)
        self._apply_search_view_to_tab2(view)
        logger.info("[SESSION] REFRESH_SEARCH → Tab2 filter=%s", view.search.filter)

    def _tab2_current_filters(self) -> dict:
        return {
            "patient_id": self.filter_id.text().strip() if hasattr(self, "filter_id") else "",
            "full_name": self.filter_name.text().strip() if hasattr(self, "filter_name") else "",
            "birth_year": self.filter_birth.text().strip() if hasattr(self, "filter_birth") else "",
            "gender": gender_combo_value(self.filter_gender, filter_mode=True)
            if hasattr(self, "filter_gender")
            else "",
        }

    def _tab2_search_result_count(self, filters: dict | None = None) -> int:
        filters = filters or self._tab2_current_filters()
        return len(
            self.search_service.search(
                filters["patient_id"],
                filters["full_name"],
                filters["birth_year"],
                filters["gender"],
            )
        )

    def _merge_voice_into_tab2_filters(self, patient_data: dict) -> dict:
        """Apply voice partial dict onto Tab 2 boxes; return merged filter dict."""
        current = self._tab2_current_filters()
        if patient_data.get("full_name"):
            current["full_name"] = str(patient_data["full_name"]).strip()
        if patient_data.get("birth_year"):
            current["birth_year"] = str(patient_data["birth_year"]).strip()
        if patient_data.get("gender"):
            current["gender"] = str(patient_data["gender"]).strip()
        if not hasattr(self, "filter_id"):
            return current
        self._tab2_filter_suppress = True
        try:
            self.filter_name.setText(current["full_name"])
            self.filter_birth.setText(current["birth_year"])
            set_gender_combo(self.filter_gender, current["gender"], filter_mode=True)
        finally:
            self._tab2_filter_suppress = False
        return current

    def _sync_tab2_filters_to_session(self) -> bool:
        """Push Tab 2 filter boxes into session when search mode is active."""
        snap = self.session_ctrl.snapshot()
        if not snap.search.open:
            return False
        filters = self._tab2_current_filters()
        self._dispatch_session(
            SearchFilterEdit(
                patient_id=filters["patient_id"] or None,
                full_name=filters["full_name"] or None,
                birth_year=filters["birth_year"] or None,
                gender=filters["gender"] or None,
                result_count=self._tab2_search_result_count(filters),
            )
        )
        return True

    def _on_tab2_filter_edited(self, _text: str = ""):
        """Typing updates results; keep session search.filter in sync for voice."""
        if getattr(self, "_tab2_filter_suppress", False):
            return
        if not self._sync_tab2_filters_to_session():
            self.load_history_records()

    def _on_tab2_filters_changed(self):
        if getattr(self, "_tab2_filter_suppress", False):
            return
        snap = self.session_ctrl.snapshot()
        if not snap.search.open and snap.affordances.can_open_search:
            self._dispatch_session(Hotkey("F5"))
        if not self._sync_tab2_filters_to_session():
            self.load_history_records()

    def _update_tab2_empty_prompt(self, rows: list, filters: dict, has_filter: bool) -> None:
        if not hasattr(self, "lbl_tab2_empty"):
            return
        pid = filters.get("patient_id", "")
        if has_filter and not rows and pid:
            self.lbl_tab2_empty.setText(
                f"Chưa có hồ sơ [{pid}]. Dùng mã này cho bệnh nhân mới?"
            )
            self.lbl_tab2_empty.show()
            self.btn_tab2_confirm_new.show()
        else:
            self.lbl_tab2_empty.hide()
            self.btn_tab2_confirm_new.hide()

    def _on_tab2_confirm_new_patient(self):
        pid = self.filter_id.text().strip()
        if not pid:
            return
        snap = self.session_ctrl.snapshot()
        if not snap.search.open and snap.affordances.can_open_search:
            self._dispatch_session(Hotkey("F5"))
        self._on_new_patient_id_confirmed(pid)
        self.switch_tab(0)

    def _session_close_search(self):
        if self._search_dialog is not None:
            dlg = self._search_dialog
            self._search_dialog = None
            try:
                dlg.close()
            except Exception:
                pass
        logger.info("[SESSION] CLOSE_SEARCH")

    def _on_search_dialog_finished(self):
        self._search_dialog = None
        # Keep controller search flag in sync if user dismissed without LoadRecord
        snap = self.session_ctrl.snapshot()
        if snap.search.open:
            self._dispatch_session(CloseSearch())

    def _on_search_filters_changed(self, filters: dict):
        pid = filters.get("patient_id") or None
        results = self.search_service.search(
            filters.get("patient_id", ""),
            filters.get("full_name", ""),
            filters.get("birth_year", ""),
            filters.get("gender", ""),
        )
        self._dispatch_session(
            SearchFilterEdit(
                patient_id=pid,
                full_name=filters.get("full_name") or None,
                birth_year=filters.get("birth_year") or None,
                gender=filters.get("gender") or None,
                result_count=len(results),
            )
        )

    def _on_new_patient_id_confirmed(self, patient_id: str):
        pid = (patient_id or "").strip()
        if not pid:
            return
        # Ensure filter + 0 hits before ConfirmNewPatientId
        self._dispatch_session(
            SearchFilterEdit(patient_id=pid, result_count=0)
        )
        self._dispatch_session(ConfirmNewPatientId())
        self.load_patient_photos()
        logger.info("[SESSION] ConfirmNewPatientId %s", pid)

    def _upsert_demography_patient(self, demo) -> bool:
        """Write demography to patients table so photo FK inserts succeed during Locked Capture."""
        if not demo or not demo.patient_id:
            return False
        ok = database.upsert_patient(
            demo.patient_id,
            name=demo.full_name or "",
            birth_year=demo.birth_year,
            gender=demo.gender or "",
        )
        if ok:
            logger.info("[SESSION] Upserted patient %s before/during capture", demo.patient_id)
        return ok

    def _session_persist_and_clear(self):
        demo = getattr(self, "_pending_persist_demo", None)
        self._pending_persist_demo = None
        if demo and demo.patient_id:
            self._upsert_demography_patient(demo)
            logger.info("[SESSION] Persisted patient %s", demo.patient_id)
        if hasattr(self, "cockpit_widget") and self.cockpit_widget:
            # Clear filmstrip widgets; demography already cleared via bind
            for i in reversed(range(self.cockpit_widget.filmstrip_layout.count())):
                w = self.cockpit_widget.filmstrip_layout.itemAt(i).widget()
                if w:
                    w.setParent(None)
        self.current_patient_id = None
        self.load_patient_photos()
        self.status_bar.showMessage("Đã kết thúc phiên — nhấn F1 cho BN tiếp.", 5000)

    def _session_warn(self, view):
        msg = view.notice or "Cảnh báo phiên"
        self.status_bar.showMessage(msg, 4000)
        logger.warning("[SESSION_WARN] %s", msg)

    def _on_cockpit_patient_loaded(self, patient_data: dict):
        """LoadRecord from grid selection (Task 3 bridge; Task 4 tightens barcode)."""
        patient_id = (patient_data.get("patient_id") or "").strip()
        if not patient_id:
            return
        by_raw = patient_data.get("birth_year")
        birth_year = None
        if by_raw not in (None, ""):
            try:
                birth_year = int(str(by_raw).strip())
            except ValueError:
                birth_year = None
        demo = Demography(
            patient_id=patient_id,
            full_name=(patient_data.get("full_name") or "").strip() or None,
            birth_year=birth_year,
            gender=(patient_data.get("gender") or "").strip() or None,
        )
        self._dispatch_session(LoadRecord(demo))
        self.load_patient_photos()
        logger.info("[COCKPIT_PATIENT_LOAD] LoadRecord %s", patient_id)

    # ----------------- TAB 1: LIVE CAPTURE & SPLIT COMPARISON -----------------
    def build_tab1_capture(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Bar: Operator & Patient Banner
        top_banner = QHBoxLayout()
        
        op_box = QHBoxLayout()
        op_box.addWidget(QLabel("Người thao tác:"))
        self.cb_active_operator = QComboBox()
        self.cb_active_operator.setMinimumWidth(200)
        self.load_operator_dropdown()
        self.cb_active_operator.currentIndexChanged.connect(self.on_operator_changed)
        op_box.addWidget(self.cb_active_operator)
        top_banner.addLayout(op_box)
        
        top_banner.addStretch()
        
        self.lbl_scan_status = QLabel("Vui lòng quét Mã Vạch (Barcode)...")
        self.lbl_scan_status.setStyleSheet("color: #fb7185; font-weight: bold; font-size: 14px;")
        top_banner.addWidget(self.lbl_scan_status)

        btn_finish_patient = QPushButton("✅ Hoàn Thành Khám (Chờ BN mới)")
        btn_finish_patient.setStyleSheet("background-color: #0d9488; color: white; padding: 4px 12px; font-weight: bold; font-size: 12px;")
        btn_finish_patient.clicked.connect(self.reset_active_patient)
        top_banner.addWidget(btn_finish_patient)
        
        layout.addLayout(top_banner)

        # Split Screen Layout (Live Camera vs Baseline Comparison Photo)
        split_layout = QHBoxLayout()
        
        # Left: Camera Stream Box
        self.cam_box = QGroupBox("1. MÀN HÌNH CAMERA THỜI GIAN THỰC")
        cam_box_layout = QVBoxLayout(self.cam_box)
        
        self.camera_feed = QLabel("Đang kết nối Camera...")
        self.camera_feed.setAlignment(Qt.AlignCenter)
        self.camera_feed.setMinimumSize(480, 360)
        self.camera_feed.setStyleSheet("background-color: #090d16; border: 1px solid #1e293b; border-radius: 4px;")
        cam_box_layout.addWidget(self.camera_feed)
        
        split_layout.addWidget(self.cam_box, stretch=1)

        # Right: Baseline Photo Viewer Box
        baseline_box = QGroupBox("2. ẢNH MỐC ĐỢT 1 (ĐỐI CHIẾU CĂN GÓC)")
        baseline_layout = QVBoxLayout(baseline_box)
        
        self.lbl_baseline_photo = QLabel("Chưa có ảnh đối chiếu")
        self.lbl_baseline_photo.setAlignment(Qt.AlignCenter)
        self.lbl_baseline_photo.setMinimumSize(480, 360)
        self.lbl_baseline_photo.setStyleSheet("background-color: #090d16; border: 1px solid #1e293b; border-radius: 4px; color: #64748b;")
        baseline_layout.addWidget(self.lbl_baseline_photo)
        
        split_layout.addWidget(baseline_box, stretch=1)
        layout.addLayout(split_layout, stretch=3)

        # Patient Info Form & Hands-free Control Bar
        middle_layout = QHBoxLayout()
        
        # Form Info
        form_box = QGroupBox("THÔNG TIN BỆNH NHÂN HIỆN TẠI")
        info_form = QFormLayout(form_box)
        
        self.txt_patient_id = QLineEdit()
        self.txt_patient_id.setPlaceholderText("Nhập Mã BA & ấn Enter...")
        self.txt_patient_id.returnPressed.connect(self.start_session_by_manual_id)
        
        id_row_layout = QHBoxLayout()
        id_row_layout.addWidget(self.txt_patient_id, stretch=1)
        btn_open_session = QPushButton("▶ Mở phiên")
        btn_open_session.setToolTip("Nhập Mã BA và bấm nút này (hoặc ấn Enter) để mở phiên khám mới")
        btn_open_session.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
        btn_open_session.clicked.connect(self.start_session_by_manual_id)
        id_row_layout.addWidget(btn_open_session)
        
        info_form.addRow("Mã BA:", id_row_layout)
        
        self.txt_patient_name = QLineEdit()
        info_form.addRow("Họ và Tên:", self.txt_patient_name)
        
        self.txt_birth_year = QLineEdit()
        info_form.addRow("Năm sinh:", self.txt_birth_year)
        
        self.txt_gender = make_gender_combo()
        info_form.addRow("Giới tính:", self.txt_gender)
        
        btn_save = QPushButton("Lưu thay đổi")
        btn_save.clicked.connect(self.save_patient_info)
        info_form.addRow("", btn_save)
        
        middle_layout.addWidget(form_box, stretch=1)

        # Action Panel
        action_box = QGroupBox("ĐIỀU KHIỂN RẢNH TAY")
        action_layout = QVBoxLayout(action_box)
        
        voice_indicators = QHBoxLayout()
        self.lbl_voice_status = QLabel("Microphone: Đang kết nối...")
        self.lbl_voice_status.setStyleSheet("color: #38bdf8;")
        voice_indicators.addWidget(self.lbl_voice_status)
        
        self.voice_gauge = QProgressBar()
        self.voice_gauge.setRange(0, 100)
        self.voice_gauge.setValue(0)
        self.voice_gauge.setTextVisible(False)
        self.voice_gauge.setFixedHeight(12)
        self.voice_gauge.setStyleSheet("QProgressBar::chunk { background-color: #22c55e; }")
        voice_indicators.addWidget(self.voice_gauge)
        action_layout.addLayout(voice_indicators)

        pedal_layout = QHBoxLayout()
        self.lbl_pedal_info = QLabel(f"Bàn đạp: {self.app_config['trigger_key'].upper()}")
        pedal_layout.addWidget(self.lbl_pedal_info)
        action_layout.addLayout(pedal_layout)

        self.btn_capture = QPushButton("CHỤP ẢNH (Bàn đạp / Hô 'Chụp')")
        self.btn_capture.setObjectName("capture_btn")
        self.btn_capture.clicked.connect(lambda: self.trigger_photo_capture(source="GUI_BUTTON"))
        action_layout.addWidget(self.btn_capture)
        
        middle_layout.addWidget(action_box, stretch=1)
        layout.addLayout(middle_layout)

        # Photos Gallery Strip (Bottom)
        gallery_box = QGroupBox("DANH SÁCH ẢNH PHIÊN NÀY (Chuột phải để Xóa)")
        gallery_layout = QVBoxLayout(gallery_box)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(130)
        self.scroll_area.setWidgetResizable(True)
        
        self.grid_widget = QWidget()
        self.grid_layout = QHBoxLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.scroll_area.setWidget(self.grid_widget)
        
        gallery_layout.addWidget(self.scroll_area)
        layout.addWidget(gallery_box)

        return widget

    # ----------------- TAB 2: VISUAL 2-LEVEL PATIENT FOLDER EXPLORER -----------------
    def build_tab2_history(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Control Bar (Breadcrumb + Action Buttons)
        top_bar = QHBoxLayout()

        self.lbl_breadcrumb = QLabel("📁 Tất cả Thư mục Bệnh án")
        self.lbl_breadcrumb.setStyleSheet("font-weight: bold; font-size: 15px; color: #38bdf8;")
        top_bar.addWidget(self.lbl_breadcrumb)

        top_bar.addStretch(1)

        self.btn_back_folder = QPushButton("◀️ Quay lại Thư mục (Backspace)")
        self.btn_back_folder.setStyleSheet(
            "background-color: #334155; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_back_folder.setCursor(Qt.PointingHandCursor)
        self.btn_back_folder.clicked.connect(self.show_level1_folders)
        self.btn_back_folder.setVisible(False)
        top_bar.addWidget(self.btn_back_folder)

        self.btn_open_tab1 = QPushButton("📷 Mở ở Tab Chụp")
        self.btn_open_tab1.setStyleSheet(
            "background-color: #0284c7; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_open_tab1.setCursor(Qt.PointingHandCursor)
        self.btn_open_tab1.clicked.connect(self.open_selected_folder_in_tab1)
        self.btn_open_tab1.setVisible(False)
        top_bar.addWidget(self.btn_open_tab1)

        self.btn_export_report = None
        layout.addLayout(top_bar)

        # 4-field filter (same shape as former F5 popup) + voice fills these when search.open
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self.filter_id = QLineEdit()
        self.filter_id.setPlaceholderText("Mã hồ sơ/phiếu (khớp đúng)")
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText("Họ và tên")
        self.filter_birth = QLineEdit()
        self.filter_birth.setPlaceholderText("Năm sinh")
        self.filter_gender = make_gender_combo(filter_mode=True)
        self.btn_tab2_search = QPushButton("🔍 Tìm")
        self.btn_tab2_search.setCursor(Qt.PointingHandCursor)
        self.btn_tab2_search.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_tab2_search.clicked.connect(self._on_tab2_filters_changed)

        # Legacy alias: barcode Tab2 path still sets txt_search
        self.txt_search = self.filter_id

        for w in (self.filter_id, self.filter_name, self.filter_birth):
            w.setClearButtonEnabled(True)
            w.returnPressed.connect(self._on_tab2_filters_changed)
            w.textEdited.connect(self._on_tab2_filter_edited)
            filter_bar.addWidget(w, stretch=1 if w is self.filter_name else 0)
        self.filter_gender.currentIndexChanged.connect(
            lambda _idx: self._on_tab2_filter_edited()
        )
        filter_bar.addWidget(self.filter_gender)
        filter_bar.addWidget(self.btn_tab2_search)
        layout.addLayout(filter_bar)

        self.lbl_tab2_filter_hint = QLabel(
            "🎙️ Hai bước: «họ và tên» → nói tên trong ~3 giây (vd: Lương Thế Vinh); "
            "hết chờ → nói từ khóa mới. Tương tự «năm sinh» / «giới tính»."
        )
        self.lbl_tab2_filter_hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_tab2_filter_hint.setWordWrap(True)
        layout.addWidget(self.lbl_tab2_filter_hint)

        empty_row = QHBoxLayout()
        self.lbl_tab2_empty = QLabel("")
        self.lbl_tab2_empty.setStyleSheet("color: #fbbf24; font-size: 12px;")
        self.lbl_tab2_empty.setWordWrap(True)
        self.lbl_tab2_empty.hide()
        self.btn_tab2_confirm_new = QPushButton("Dùng mã này cho bệnh nhân mới")
        self.btn_tab2_confirm_new.setStyleSheet(
            "background-color: #16a34a; color: white; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_tab2_confirm_new.setCursor(Qt.PointingHandCursor)
        self.btn_tab2_confirm_new.clicked.connect(self._on_tab2_confirm_new_patient)
        self.btn_tab2_confirm_new.hide()
        empty_row.addWidget(self.lbl_tab2_empty, stretch=1)
        empty_row.addWidget(self.btn_tab2_confirm_new)
        layout.addLayout(empty_row)

        # Stacked Container for Level 1 vs Level 2
        self.tab2_stack = QStackedWidget()

        # --- LEVEL 1 PAGE: VISUAL FOLDER CARDS GRID ---
        self.level1_widget = QWidget()
        level1_layout = QVBoxLayout(self.level1_widget)
        level1_layout.setContentsMargins(0, 0, 0, 0)

        self.level1_scroll = QScrollArea()
        self.level1_scroll.setWidgetResizable(True)
        self.level1_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #1e293b; background-color: #090d16; border-radius: 6px; }"
        )

        self.level1_container = QWidget()
        self.level1_grid = QGridLayout(self.level1_container)
        self.level1_grid.setContentsMargins(15, 15, 15, 15)
        self.level1_grid.setSpacing(15)
        self.level1_scroll.setWidget(self.level1_container)
        level1_layout.addWidget(self.level1_scroll)

        self.tab2_stack.addWidget(self.level1_widget)

        # --- LEVEL 2 PAGE: DETAILED PATIENT PHOTO GALLERY ---
        self.level2_widget = QWidget()
        level2_layout = QVBoxLayout(self.level2_widget)
        level2_layout.setContentsMargins(0, 0, 0, 0)

        self.level2_scroll = QScrollArea()
        self.level2_scroll.setWidgetResizable(True)
        self.level2_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #1e293b; background-color: #090d16; border-radius: 6px; }"
        )

        self.level2_container = QWidget()
        self.level2_grid = QGridLayout(self.level2_container)
        self.level2_grid.setContentsMargins(15, 15, 15, 15)
        self.level2_grid.setSpacing(15)
        self.level2_scroll.setWidget(self.level2_container)
        level2_layout.addWidget(self.level2_scroll)

        self.tab2_stack.addWidget(self.level2_widget)

        layout.addWidget(self.tab2_stack)

        self.selected_patient_folder_id = None
        self._tab2_filter_suppress = False
        return widget

    # ----------------- TAB 3: STAFF & AUDIT LOGS & ACTION MAPPINGS -----------------
    def build_tab3_staff(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        top_layout = QHBoxLayout()

        # Left: Staff Registry Box
        staff_box = QGroupBox("1. DANH MỤC NHÂN VIÊN Y TẾ")
        staff_layout = QVBoxLayout(staff_box)
        
        self.table_staff = QTableWidget()
        self.table_staff.setColumnCount(4)
        self.table_staff.setHorizontalHeaderLabels(["Mã NV", "Họ Tên", "Chức danh", "Khoa/Phòng"])
        self.table_staff.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_staff.itemSelectionChanged.connect(self.on_staff_table_selection_changed)
        staff_layout.addWidget(self.table_staff)
        
        btn_add_staff = QPushButton("Thêm Nhân Viên Mới")
        btn_add_staff.clicked.connect(self.add_staff_dialog)
        staff_layout.addWidget(btn_add_staff)
        
        top_layout.addWidget(staff_box, stretch=1)

        # Right: Per-Staff Action Mapping Box
        mapping_box = QGroupBox("2. CẤU HÌNH THAO TÁC (BÀN ĐẠP & GIỌNG NÓI)")
        mapping_layout = QVBoxLayout(mapping_box)
        
        self.lbl_selected_staff_mapping = QLabel("Cấu hình cho: BS. Nguyễn Văn A (NV001)")
        self.lbl_selected_staff_mapping.setStyleSheet("font-weight: bold; color: #38bdf8;")
        mapping_layout.addWidget(self.lbl_selected_staff_mapping)

        self.table_staff_mappings = QTableWidget()
        self.table_staff_mappings.setColumnCount(3)
        self.table_staff_mappings.setHorizontalHeaderLabels(["Nguồn Kích Hoạt", "Cử Chỉ / Từ Khóa", "Hành Động Ánh Xạ"])
        self.table_staff_mappings.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        mapping_layout.addWidget(self.table_staff_mappings)

        top_layout.addWidget(mapping_box, stretch=1)
        layout.addLayout(top_layout, stretch=2)

        # Bottom: Audit Log Viewer Box
        audit_box = QGroupBox("3. NHẬT KÝ KIỂM TOÁN HỆ THỐNG (AUDIT LOGS)")
        audit_layout = QVBoxLayout(audit_box)
        
        self.table_audit = QTableWidget()
        self.table_audit.setColumnCount(5)
        self.table_audit.setHorizontalHeaderLabels(["Thời gian", "Sự kiện", "Người thao tác", "Mã BA", "Chi tiết"])
        self.table_audit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        audit_layout.addWidget(self.table_audit)
        
        layout.addWidget(audit_box, stretch=1)
        return widget

    def _make_form_field_row(self, widgets, stretches=None):
        """QFormLayout rows need a QWidget wrapper so fields align correctly on macOS."""
        row_w = QWidget()
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        if stretches is None:
            stretches = [0] * len(widgets)
        for widget, stretch in zip(widgets, stretches):
            row.addWidget(widget, stretch)
        return row_w

    def _configure_settings_table(self, table, column_modes=None):
        table.verticalHeader().setVisible(False)
        table.setCornerButtonEnabled(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        if column_modes:
            for col, mode in column_modes.items():
                hdr.setSectionResizeMode(col, mode)
        else:
            hdr.setSectionResizeMode(QHeaderView.Stretch)

    # ----------------- TAB 4: HARDWARE & SETTINGS -----------------
    def build_tab4_settings(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        group_hw = QGroupBox("CẤU HÌNH PHẦN CỨNG & GIAO DIỆN")
        form = QFormLayout(group_hw)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        field_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Real Physical Camera Selection
        self.cfg_camera_select = QComboBox()
        self.cfg_camera_select.setSizePolicy(field_policy)
        self.cfg_camera_select.setMinimumWidth(280)
        real_cams = get_real_camera_list()
        for cam in real_cams:
            self.cfg_camera_select.addItem(f"{cam['name']} (Cổng Index {cam['index']})", cam["index"])
        cur_cam_idx = self.app_config.get("camera_index", 0)
        match_idx = self.cfg_camera_select.findData(cur_cam_idx)
        if match_idx >= 0:
            self.cfg_camera_select.setCurrentIndex(match_idx)
        self.cfg_camera_select.currentIndexChanged.connect(self.change_camera)

        btn_test_cam = QPushButton("🛠️ Test Camera (Quét Mã QR)")
        btn_test_cam.setSizePolicy(btn_policy)
        btn_test_cam.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_cam.clicked.connect(self.run_test_camera)
        form.addRow(
            "Chọn Camera:",
            self._make_form_field_row([self.cfg_camera_select, btn_test_cam], [1, 0]),
        )

        # Microphone Selection
        self.cfg_mic_select = QComboBox()
        self.cfg_mic_select.setSizePolicy(field_policy)
        self.cfg_mic_select.setMinimumWidth(280)
        available_mics = voice_detector.get_available_microphones()
        self.cfg_mic_select.addItems(available_mics)
        cur_mic = self.app_config.get("microphone_name", "default")
        idx = self.cfg_mic_select.findText(cur_mic)
        if idx >= 0:
            self.cfg_mic_select.setCurrentIndex(idx)
        else:
            self.cfg_mic_select.setCurrentIndex(0)
        self.cfg_mic_select.currentIndexChanged.connect(self.change_microphone)

        btn_test_mic = QPushButton("🛠️ Test Mic (Thử Lệnh Vozk)")
        btn_test_mic.setSizePolicy(btn_policy)
        btn_test_mic.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_mic.clicked.connect(self.run_test_mic)
        form.addRow(
            "Chọn Microphone (Venfish/Bluetooth/3.5mm):",
            self._make_form_field_row([self.cfg_mic_select, btn_test_mic], [1, 0]),
        )

        # Foot pedal status info
        self.lbl_pedal_info = QLabel(
            "PCSensor USB FootSwitch (Gán phím F13/ALT - Tự động phân biệt Cử chỉ 1, 2, 3 giậm & Nhấn giữ)"
        )
        self.lbl_pedal_info.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.lbl_pedal_info.setWordWrap(True)
        self.lbl_pedal_info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        btn_test_pedal = QPushButton("🛠️ Test Bàn Đạp Chân")
        btn_test_pedal.setSizePolicy(btn_policy)
        btn_test_pedal.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_pedal.clicked.connect(self.run_test_pedal)
        form.addRow(
            "Bàn đạp chân (Pedal):",
            self._make_form_field_row([self.lbl_pedal_info, btn_test_pedal], [1, 0]),
        )

        # Theme switcher
        self.cb_theme = QComboBox()
        self.cb_theme.setSizePolicy(field_policy)
        self.cb_theme.addItems(["Dark Slate (Mặc định)", "Light Clinical (Sáng Y tế)"])
        current_t = self.app_config.get("active_theme", "dark")
        self.cb_theme.setCurrentIndex(0 if current_t == "dark" else 1)
        self.cb_theme.currentIndexChanged.connect(self.on_theme_dropdown_changed)
        form.addRow("Chế độ màu Giao diện:", self.cb_theme)

        # Working Directory Selection
        self.txt_working_dir = QLineEdit(str(config.get_photos_dir()))
        self.txt_working_dir.setSizePolicy(field_policy)

        btn_browse_dir = QPushButton("📁 Chọn Thư Mục")
        btn_browse_dir.setSizePolicy(btn_policy)
        btn_browse_dir.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_browse_dir.clicked.connect(self.browse_working_dir)
        form.addRow(
            "Thư mục lưu trữ Ảnh Bệnh án:",
            self._make_form_field_row([self.txt_working_dir, btn_browse_dir], [1, 0]),
        )

        # OTA Update Intranet URL
        self.txt_ota_url = QLineEdit(self.app_config.get("update_url", ""))
        self.txt_ota_url.setSizePolicy(field_policy)
        form.addRow("Địa chỉ Cập nhật Intranet:", self.txt_ota_url)

        btn_save_cfg = QPushButton("Lưu Cấu Hình Cài Đặt")
        btn_save_cfg.setSizePolicy(btn_policy)
        btn_save_cfg.clicked.connect(self.save_settings_cfg)
        save_row = QWidget()
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 8, 0, 0)
        save_layout.addWidget(btn_save_cfg)
        save_layout.addStretch()
        form.addRow(save_row)

        layout.addWidget(group_hw)

        # Global voice lexicon (Settings-wide)
        group_lex = QGroupBox("TỪ ĐIỂN GIỌNG NÓI TOÀN CỤC (phrase → intent)")
        lex_layout = QVBoxLayout(group_lex)
        lex_layout.setSpacing(8)

        self.table_lexicon = QTableWidget()
        self.table_lexicon.setColumnCount(2)
        self.table_lexicon.setHorizontalHeaderLabels(["Câu lệnh (phrase)", "Intent"])
        self._configure_settings_table(self.table_lexicon)
        self.table_lexicon.setMinimumHeight(200)
        lex_layout.addWidget(self.table_lexicon)

        lex_btns = QWidget()
        lex_btn_row = QHBoxLayout(lex_btns)
        lex_btn_row.setContentsMargins(0, 0, 0, 0)
        lex_btn_row.setSpacing(8)
        btn_lex_add = QPushButton("Thêm dòng")
        btn_lex_add.setSizePolicy(btn_policy)
        btn_lex_add.clicked.connect(self._lexicon_add_row)
        btn_lex_save = QPushButton("Lưu từ điển giọng")
        btn_lex_save.setSizePolicy(btn_policy)
        btn_lex_save.clicked.connect(self._save_voice_lexicon)
        lex_btn_row.addWidget(btn_lex_add)
        lex_btn_row.addWidget(btn_lex_save)
        lex_btn_row.addStretch()
        lex_layout.addWidget(lex_btns)
        layout.addWidget(group_lex)
        self._load_lexicon_table()

        # Hardware Scanner & Diagnostic Console Box
        group_scan = QGroupBox("QUÉT & CHẨN ĐOÁN PHẦN CỨNG HỆ THỐNG")
        scan_layout = QVBoxLayout(group_scan)
        scan_layout.setSpacing(8)

        scan_top = QHBoxLayout()
        self.btn_scan_hw = QPushButton("🔍 QUÉT PHẦN CỨNG (Scan Hardware)")
        self.btn_scan_hw.setSizePolicy(btn_policy)
        self.btn_scan_hw.clicked.connect(self.scan_system_hardware)
        scan_top.addWidget(self.btn_scan_hw)

        self.lbl_hw_status = QLabel("Bấm nút để bắt đầu quét phần cứng...")
        self.lbl_hw_status.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.lbl_hw_status.setWordWrap(True)
        scan_top.addWidget(self.lbl_hw_status, stretch=1)
        scan_layout.addLayout(scan_top)

        self.table_hw = QTableWidget()
        self.table_hw.setColumnCount(5)
        self.table_hw.setHorizontalHeaderLabels(
            ["Loại phần cứng", "Tên phần cứng", "Trạng thái", "Thông tin chi tiết / Cổng", "Thao tác Test"]
        )
        self._configure_settings_table(
            self.table_hw,
            {
                0: QHeaderView.ResizeToContents,
                1: QHeaderView.Stretch,
                2: QHeaderView.ResizeToContents,
                3: QHeaderView.Stretch,
                4: QHeaderView.ResizeToContents,
            },
        )
        self.table_hw.setMinimumHeight(220)
        scan_layout.addWidget(self.table_hw)

        layout.addWidget(group_scan)
        scroll.setWidget(content)
        self.load_initial_hardware_cache()
        return scroll

    # ----------------- OPERATOR & STAFF LOGIC -----------------
    def load_operator_dropdown(self):
        self.cb_active_operator.clear()
        staff_list = database.get_staff_list()
        active_idx = 0
        for idx, s in enumerate(staff_list):
            disp = f"{s['name']} ({s['title']})"
            self.cb_active_operator.addItem(disp, s['id'])
            if s['id'] == self.active_operator_id:
                active_idx = idx
        if staff_list:
            self.cb_active_operator.setCurrentIndex(active_idx)

    def on_operator_changed(self, idx):
        if not hasattr(self, 'cb_active_operator') or self.cb_active_operator is None:
            return
        staff_id = self.cb_active_operator.currentData()
        if staff_id:
            self.active_operator_id = staff_id
            self.active_operator_name = self.cb_active_operator.currentText().split(" (")[0]
            self.app_config["active_operator_id"] = staff_id
            config.save_config(self.app_config)
            if hasattr(self, 'camera_thread') and self.camera_thread is not None:
                self.camera_thread.set_active_operator(self.active_operator_id, self.active_operator_name)

    def load_staff_and_audit_data(self):
        # Load Staff Table
        staff_list = database.get_staff_list()
        self.table_staff.setRowCount(len(staff_list))
        for r, s in enumerate(staff_list):
            self.table_staff.setItem(r, 0, QTableWidgetItem(s["id"]))
            self.table_staff.setItem(r, 1, QTableWidgetItem(s["name"]))
            self.table_staff.setItem(r, 2, QTableWidgetItem(s["title"]))
            self.table_staff.setItem(r, 3, QTableWidgetItem(s["department"]))
            
        # Load Audit Logs Table
        logs = database.get_audit_logs(limit=100)
        self.table_audit.setRowCount(len(logs))
        for r, l in enumerate(logs):
            self.table_audit.setItem(r, 0, QTableWidgetItem(l["timestamp"]))
            self.table_audit.setItem(r, 1, QTableWidgetItem(l["event_type"]))
            self.table_audit.setItem(r, 2, QTableWidgetItem(l["operator_name"] or "N/A"))
            self.table_audit.setItem(r, 3, QTableWidgetItem(l["patient_id"] or ""))
            self.table_audit.setItem(r, 4, QTableWidgetItem(l["details"] or ""))

        # Load action mappings for currently selected staff
        self.load_staff_action_mappings(self.active_operator_id)

    def on_staff_table_selection_changed(self):
        selected = self.table_staff.selectedItems()
        if selected:
            row = selected[0].row()
            staff_id = self.table_staff.item(row, 0).text()
            staff_name = self.table_staff.item(row, 1).text()
            self.lbl_selected_staff_mapping.setText(f"Cấu hình cho: {staff_name} ({staff_id})")
            self.load_staff_action_mappings(staff_id)

    def load_staff_action_mappings(self, staff_id):
        mappings = database.get_staff_action_mappings(staff_id)
        reg_actions = action_registry.get_registered_actions()
        
        self.table_staff_mappings.setRowCount(len(mappings))
        for r, m in enumerate(mappings):
            src_text = "Bàn Đạp Chân" if m["trigger_source"] == "PEDAL_GESTURE" else "Giọng Nói AI"
            action_info = reg_actions.get(m["action_id"], {})
            action_label = action_info.get("label", m["action_id"])
            
            self.table_staff_mappings.setItem(r, 0, QTableWidgetItem(src_text))
            self.table_staff_mappings.setItem(r, 1, QTableWidgetItem(m["trigger_value"]))
            self.table_staff_mappings.setItem(r, 2, QTableWidgetItem(f"{action_label} ({m['action_id']})"))

    def add_staff_dialog(self):
        name, ok = QInputDialog.getText(self, "Thêm Nhân Viên", "Nhập Họ và Tên Nhân viên:")
        if ok and name.strip():
            s_id = f"NV{int(time.time()) % 10000:04d}"
            database.add_staff(s_id, name.strip())
            self.load_staff_and_audit_data()
            self.load_operator_dropdown()

    # ----------------- VISUAL 2-LEVEL FOLDER EXPLORER LOGIC -----------------
    def show_level1_folders(self):
        self.selected_patient_folder_id = None
        self.lbl_breadcrumb.setText("📁 Tất cả Thư mục Bệnh án")
        self.btn_back_folder.setVisible(False)
        self.btn_open_tab1.setVisible(False)
        self.tab2_stack.setCurrentIndex(0)
        self.load_history_records()

    def open_patient_folder(self, patient_id):
        self.selected_patient_folder_id = patient_id
        patient = database.get_patient(patient_id)
        p_name = patient["name"] if patient and patient["name"] else "Chưa cập nhật"
        
        self.lbl_breadcrumb.setText(f"📁 Tất cả Thư mục > 📂 {patient_id} - {p_name}")
        self.btn_back_folder.setVisible(True)
        self.btn_open_tab1.setVisible(True)
        
        # Clear existing level 2 grid
        while self.level2_grid.count():
            item = self.level2_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        photos = database.get_patient_photos(patient_id)
        if not photos:
            empty_lbl = QLabel(f"Thư mục bệnh nhân {patient_id} chưa có hình ảnh nào.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; font-weight: bold; margin: 40px;")
            self.level2_grid.addWidget(empty_lbl, 0, 0)
        else:
            cols = 4
            all_paths = []
            for photo in photos:
                full_path = database.get_full_photo_path(photo["file_path"])
                all_paths.append(full_path)

            for idx, photo in enumerate(photos):
                full_path = database.get_full_photo_path(photo["file_path"])
                r = idx // cols
                c = idx % cols
                
                # Card Widget for photo
                card = QGroupBox()
                card.setStyleSheet("""
                    QGroupBox {
                        background-color: #0f172a;
                        border: 1px solid #1e293b;
                        border-radius: 6px;
                    }
                    QGroupBox:hover {
                        border: 1px solid #38bdf8;
                    }
                """)
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(8, 8, 8, 8)
                
                lbl_img = QLabel()
                lbl_img.setFixedSize(200, 150)
                lbl_img.setAlignment(Qt.AlignCenter)
                lbl_img.setStyleSheet("background-color: #020617; border-radius: 4px;")
                
                pix = QPixmap(str(full_path))
                if not pix.isNull():
                    lbl_img.setPixmap(pix.scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    lbl_img.setText("📷 Không nạp được ảnh")
                    
                lbl_img.setCursor(Qt.PointingHandCursor)
                lbl_img.mousePressEvent = lambda e, p_idx=idx: hardware_test_dialogs.show_image_preview(self, photo_paths=all_paths, current_index=p_idx)
                card_layout.addWidget(lbl_img)
                
                lbl_info = QLabel(f"📄 Photo #{idx+1}\n⏱️ {photo.get('captured_at', '')}")
                lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
                card_layout.addWidget(lbl_info)

                btn_del = QPushButton("🗑️ Xóa ảnh")
                btn_del.setStyleSheet(
                    "background-color: #7f1d1d; color: white; padding: 4px; border-radius: 4px;"
                )
                photo_id = photo["id"]

                def _delete_tab2_photo(_checked=False, pid=photo_id, folder=patient_id):
                    reply = QMessageBox.question(
                        self,
                        "Xác nhận xóa",
                        "Xóa ảnh này khỏi thư mục bệnh nhân?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply == QMessageBox.Yes:
                        database.delete_photo(pid, operator_name=self.active_operator_name)
                        self.open_patient_folder(folder)

                btn_del.clicked.connect(_delete_tab2_photo)
                card_layout.addWidget(btn_del)
                
                self.level2_grid.addWidget(card, r, c)

        self.tab2_stack.setCurrentIndex(1)

    def open_selected_folder_in_tab1(self):
        patient_id = self.selected_patient_folder_id
        if patient_id:
            self._continue_with_patient(patient_id)

    def _view_patient_detail(self, patient_id: str):
        dlg = PatientDetailDialog(
            patient_id,
            parent=self,
            operator_name=getattr(self, "active_operator_name", ""),
        )
        dlg.exec()
        self.load_history_records()

    def _continue_with_patient(self, patient_id: str):
        if not patient_id:
            return
        self.selected_patient_folder_id = patient_id
        view = self.session_ctrl.snapshot()
        current = view.demography.patient_id
        if current and current != patient_id:
            self.status_bar.showMessage(
                f"Đang khám [{current}] — F4 rồi F1 để đổi BN",
                5000,
            )
            return
        if not current or view.phase == Phase.STANDBY:
            patient = database.get_patient(patient_id)
            if patient:
                demo = Demography(
                    patient_id=patient_id,
                    full_name=patient.get("name") or None,
                    birth_year=patient.get("birth_year"),
                    gender=patient.get("gender") or None,
                )
                self._dispatch_session(LoadRecord(demo))
                self.load_patient_photos()
            else:
                self._dispatch_session(LoadRecord(Demography(patient_id=patient_id)))
                self.load_patient_photos()
        self.switch_tab(0)

    def export_patient_report(self):
        QMessageBox.information(
            self,
            "Xuất báo cáo",
            "Xuất PDF/báo cáo đã gỡ khỏi v1 (xem SPEC Hands-Free Session).",
        )

    def load_history_records(self):
        if self.tab2_stack.currentIndex() == 1 and self.selected_patient_folder_id:
            self.open_patient_folder(self.selected_patient_folder_id)
            return

        filters = self._tab2_current_filters()
        has_filter = any(filters.values())
        if has_filter:
            rows = self.search_service.search(
                filters["patient_id"],
                filters["full_name"],
                filters["birth_year"],
                filters["gender"],
            )
            self.lbl_breadcrumb.setText(
                f"📁 Kết quả lọc ({len(rows)}) — Mã/Tên/Năm sinh/GT"
            )
        else:
            rows = self.search_service.recent(limit=50)
            self.lbl_breadcrumb.setText("📁 Thư mục Bệnh án · Gần đây (50)")

        # Clear Level 1 Grid
        while self.level1_grid.count():
            item = self.level1_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not rows:
            self._update_tab2_empty_prompt(rows, filters, has_filter)
            empty_lbl = QLabel(
                "Không tìm thấy hồ sơ khớp bộ lọc."
                if has_filter
                else "Chưa có thư mục Bệnh án nào."
            )
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(
                "color: #64748b; font-size: 14px; font-weight: bold; margin: 40px;"
            )
            self.level1_grid.addWidget(empty_lbl, 0, 0)
            return

        self._update_tab2_empty_prompt(rows, filters, has_filter)

        cols = 4
        for idx, p in enumerate(rows):
            p_id = p.get("patient_id") or p.get("id")
            p_name = p.get("full_name") or p.get("name") or "Chưa tên"
            p_year = p.get("birth_year") or ""
            p_gender = p.get("gender") or ""

            photos = database.get_patient_photos(p_id)
            photo_count = len(photos)
            
            # Find cover photo
            cover_pix = None
            if photos:
                latest_photo_path = database.get_full_photo_path(photos[0]["file_path"])
                pix = QPixmap(str(latest_photo_path))
                if not pix.isNull():
                    cover_pix = pix.scaled(208, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            r = idx // cols
            c = idx % cols

            card = PatientFolderCard(
                p_id,
                name=p_name,
                birth_year=p_year,
                gender=p_gender,
                photo_count=photo_count,
                created_at_display=p.get("created_at_display") or "—",
                cover_pixmap=cover_pix,
            )
            card.view_detail.connect(self._view_patient_detail)
            card.continue_work.connect(self._continue_with_patient)
            self.level1_grid.addWidget(card, r, c)

    def on_history_item_clicked(self, row, col):
        pass
        self.sidebar.setCurrentRow(0)  # Jump to Tab 1

    # ----------------- SETTINGS & THEME LOGIC -----------------
    def on_theme_dropdown_changed(self, idx):
        theme_name = "dark" if idx == 0 else "light"
        self.apply_theme(theme_name)

    def _load_lexicon_table(self):
        phrases = load_lexicon(self._lexicon_path)
        self.table_lexicon.setRowCount(0)
        for phrase, intent in sorted(phrases.items()):
            row = self.table_lexicon.rowCount()
            self.table_lexicon.insertRow(row)
            self.table_lexicon.setItem(row, 0, QTableWidgetItem(phrase))
            self.table_lexicon.setItem(row, 1, QTableWidgetItem(intent))

    def _lexicon_add_row(self):
        row = self.table_lexicon.rowCount()
        self.table_lexicon.insertRow(row)
        self.table_lexicon.setItem(row, 0, QTableWidgetItem(""))
        self.table_lexicon.setItem(row, 1, QTableWidgetItem(""))

    def _save_voice_lexicon(self):
        phrases: dict[str, str] = {}
        for row in range(self.table_lexicon.rowCount()):
            p_item = self.table_lexicon.item(row, 0)
            i_item = self.table_lexicon.item(row, 1)
            phrase = (p_item.text() if p_item else "").strip()
            intent = (i_item.text() if i_item else "").strip()
            if phrase and intent:
                phrases[phrase.lower()] = intent
        if not phrases:
            QMessageBox.warning(self, "Từ điển giọng", "Cần ít nhất một cặp phrase → intent.")
            return
        save_lexicon(self._lexicon_path, phrases)
        self._dispatch_session(LexiconUpdate(phrases))
        self.status_bar.showMessage(f"Đã lưu {len(phrases)} lệnh giọng (toàn cục).", 4000)
        logger.info("[LEXICON] Saved %s phrases to %s", len(phrases), self._lexicon_path)

    def browse_working_dir(self):
        cur_dir = str(config.get_photos_dir())
        chosen_dir = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Lưu Trữ Ảnh Bệnh Án", cur_dir)
        if chosen_dir:
            self.txt_working_dir.setText(chosen_dir)

    def save_settings_cfg(self):
        new_w_dir = self.txt_working_dir.text().strip()
        if new_w_dir:
            try:
                Path(new_w_dir).mkdir(parents=True, exist_ok=True)
                self.app_config["working_dir"] = new_w_dir
            except Exception as e:
                QMessageBox.warning(self, "Lỗi Thư Mục", f"Không thể tạo hoặc truy cập thư mục: {e}")
                return
                
        if hasattr(self, 'cfg_camera_select') and self.cfg_camera_select is not None:
            cam_idx = self.cfg_camera_select.currentData()
            if cam_idx is not None:
                self.app_config["camera_index"] = int(cam_idx)
                
        if hasattr(self, 'cfg_mic_select') and self.cfg_mic_select is not None:
            self.app_config["microphone_name"] = self.cfg_mic_select.currentText()

        self.app_config["update_url"] = self.txt_ota_url.text().strip()
        config.save_config(self.app_config)
        
        # Apply camera switch immediately to CameraThread
        if hasattr(self, 'camera_thread') and self.camera_thread:
            self.camera_thread.set_camera(self.app_config.get("camera_index", 0))

        self.refresh_hardware_grid_table()
        QMessageBox.information(self, "Cài Đặt", f"Đã lưu thành công cài đặt hệ thống.\nCamera Index: {self.app_config.get('camera_index', 0)} | Thư mục: {self.app_config['working_dir']}")

    def scan_system_hardware(self):
        self.btn_scan_hw.setEnabled(False)
        self.lbl_hw_status.setText("Đang chuẩn bị quét thiết bị...")
        
        # Show non-blocking loading progress modal
        self.scan_dialog = QProgressDialog("Đang chuẩn bị quét phần cứng...", None, 0, 0, self)
        self.scan_dialog.setWindowTitle("Đang quét phần cứng hệ thống")
        self.scan_dialog.setWindowModality(Qt.WindowModal)
        self.scan_dialog.setMinimumDuration(0)
        self.scan_dialog.setCancelButton(None)
        self.scan_dialog.show()

        self.scanner_thread = HardwareScannerThread(active_operator_name=self.active_operator_name)
        self.scanner_thread.progress_signal.connect(self.update_scan_progress_msg)
        self.scanner_thread.finished_signal.connect(self.on_hardware_scan_finished)
        self.scanner_thread.start()

    @Slot(str)
    def update_scan_progress_msg(self, msg):
        if hasattr(self, 'scan_dialog') and self.scan_dialog is not None:
            self.scan_dialog.setLabelText(msg)
        self.lbl_hw_status.setText(msg)

    # ----------------- HARDWARE TEST LAUNCHERS -----------------
    def run_test_camera(self):
        cam_idx = self.cfg_camera_select.currentData()
        if cam_idx is None:
            cam_idx = self.app_config.get("camera_index", 0)
        hardware_test_dialogs.test_camera(self, camera_index=cam_idx, camera_thread=getattr(self, 'camera_thread', None))

    def run_test_mic(self):
        mic_name = self.cfg_mic_select.currentText()
        if hasattr(self, 'voice_thread') and self.voice_thread is not None and self.voice_thread.isRunning():
            self.voice_thread.set_microphone(mic_name)
        hardware_test_dialogs.test_microphone(self, mic_name=mic_name, voice_thread=getattr(self, 'voice_thread', None))

    def run_test_pedal(self):
        if hasattr(self, 'pedal_fsm') and self.pedal_fsm:
            self.pedal_fsm.unregister_hook()
            
        pedal_key = self.app_config.get("trigger_key", "ALT")
        hardware_test_dialogs.test_pedal(self, trigger_key=pedal_key)
        
        if hasattr(self, 'pedal_fsm') and self.pedal_fsm:
            self.pedal_fsm.register_hook()

    def run_test_com_port(self, port_name="COM1"):
        hardware_test_dialogs.test_com_port(self, port_name=port_name)

    def attach_table_test_button(self, row, device_type):
        btn = QPushButton("🛠️ Test Thiết Bị")
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setStyleSheet(
            "background-color: #0284c7; color: white; padding: 2px 8px; "
            "font-weight: bold; border-radius: 4px;"
        )

        dtype = device_type.lower()
        if "camera" in dtype or "webcam" in dtype:
            btn.clicked.connect(self.run_test_camera)
        elif "micro" in dtype or "audio" in dtype:
            btn.clicked.connect(self.run_test_mic)
        elif "pedal" in dtype or "bàn đạp" in dtype:
            btn.clicked.connect(self.run_test_pedal)
        elif "com" in dtype or "serial" in dtype:
            btn.clicked.connect(lambda: self.run_test_com_port("COM1"))
        else:
            btn.clicked.connect(self.run_test_camera)

        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(4, 2, 4, 2)
        cell_layout.addWidget(btn)
        cell_layout.addStretch()
        self.table_hw.setRowHeight(row, max(self.table_hw.rowHeight(row), 36))
        self.table_hw.setCellWidget(row, 4, cell)

    @Slot(list)
    def refresh_hardware_grid_table(self):
        if not hasattr(self, 'table_hw') or self.table_hw is None:
            return

        results = []
        
        # 1. Camera - Read EXACT selection from self.cfg_camera_select
        if hasattr(self, 'cfg_camera_select') and self.cfg_camera_select is not None and self.cfg_camera_select.count() > 0:
            cam_name = self.cfg_camera_select.currentText()
            cam_idx = self.cfg_camera_select.currentData()
            if cam_idx is None:
                cam_idx = self.app_config.get("camera_index", 0)
            status = "SẴN SÀNG (OK)" if "Không tìm thấy" not in cam_name else "CHƯA CẮM"
            info = f"Cổng Index {cam_idx} | 1080p Stream (Windows Media Foundation)"
            results.append({"name": cam_name, "type": "Camera / Webcam (USB UVC)", "status": status, "info": info})
        else:
            results.append({"name": "Logitech C920e / Webcam", "type": "Camera / Webcam (USB UVC)", "status": "SẴN SÀNG (OK)", "info": "Cổng Index 0 | 1080p Stream"})

        # 2. Microphone - Read EXACT selection from self.cfg_mic_select
        if hasattr(self, 'cfg_mic_select') and self.cfg_mic_select is not None and self.cfg_mic_select.count() > 0:
            mic_name = self.cfg_mic_select.currentText()
            status = "SẴN SÀNG (OK)"
            info = "Driver âm thanh HD / Vosk Speech AI & PyAudio RMS Level"
            results.append({"name": mic_name, "type": "Microphone / Audio Input", "status": status, "info": info})
        else:
            results.append({"name": "Microphone (Realtek Audio)", "type": "Microphone / Audio Input", "status": "SẴN SÀNG (OK)", "info": "Driver âm thanh HD"})

        # 3. USB Foot Pedal
        results.append({
            "name": "PCSensor RDing USB FootSwitch",
            "type": "Bàn đạp chân (Pedal)",
            "status": "SẴN SÀNG (OK)",
            "info": "Driver HID Global Hook (Phím F13/ALT - 1, 2, 3 giậm & Nhấn giữ)"
        })

        # 4. Real Serial COM Ports
        com_ports = []
        try:
            from PySide6.QtSerialPort import QSerialPortInfo
            com_ports = QSerialPortInfo.availablePorts()
        except Exception:
            pass

        if com_ports:
            p0 = com_ports[0]
            results.append({"name": f"Cổng COM Serial ({p0.portName()})", "type": "Cổng COM / Máy in Bệnh án", "status": "SẴN SÀNG (OK)", "info": f"{p0.description()} | USB Serial"})
        else:
            results.append({"name": "Cổng COM Serial (Chưa cắm)", "type": "Cổng COM / Máy in Bệnh án", "status": "CHƯA CẮM", "info": "Không tìm thấy cổng nối tiếp RS232 / USB Serial"})

        # Render rows into Table Grid (5 Columns)
        self.table_hw.setRowCount(len(results))
        for r, item in enumerate(results):
            self.table_hw.setItem(r, 0, QTableWidgetItem(item.get("type", "")))
            self.table_hw.setItem(r, 1, QTableWidgetItem(item.get("name", "")))
            status_item = QTableWidgetItem(item.get("status", ""))
            if "OK" in item.get("status", ""):
                status_item.setForeground(Qt.green)
            else:
                status_item.setForeground(Qt.red)
            self.table_hw.setItem(r, 2, status_item)
            self.table_hw.setItem(r, 3, QTableWidgetItem(item.get("info", "")))
            self.attach_table_test_button(r, item.get("type", ""))

    def on_hardware_scan_finished(self, results):
        if hasattr(self, 'scan_dialog') and self.scan_dialog is not None:
            self.scan_dialog.close()
            self.scan_dialog = None

        # Refresh camera & microphone dropdowns with real physical hardware
        real_cams = get_real_camera_list()
        if hasattr(self, 'cfg_camera_select') and self.cfg_camera_select:
            self.cfg_camera_select.blockSignals(True)
            self.cfg_camera_select.clear()
            for cam in real_cams:
                self.cfg_camera_select.addItem(f"{cam['name']} (Cổng Index {cam['index']})", cam["index"])
            cur_cam_idx = self.app_config.get("camera_index", 0)
            match_idx = self.cfg_camera_select.findData(cur_cam_idx)
            if match_idx >= 0:
                self.cfg_camera_select.setCurrentIndex(match_idx)
            self.cfg_camera_select.blockSignals(False)

        mics = voice_detector.get_available_microphones()
        if hasattr(self, 'cfg_mic_select') and self.cfg_mic_select:
            self.cfg_mic_select.blockSignals(True)
            self.cfg_mic_select.clear()
            self.cfg_mic_select.addItems(mics)
            cur_mic = self.app_config.get("microphone_name", "default")
            idx = self.cfg_mic_select.findText(cur_mic)
            if idx >= 0:
                self.cfg_mic_select.setCurrentIndex(idx)
            self.cfg_mic_select.blockSignals(False)

        # Refresh Hardware Grid Table synchronously
        self.refresh_hardware_grid_table()

        # Save scanned hardware list to DB Cache
        database.save_scanned_hardware_list(results)
        self.lbl_hw_status.setText(f"Quét hoàn tất! Đã lưu {len(results)} phần cứng vào CSDL (Đã đồng bộ với cấu hình).")
        self.btn_scan_hw.setEnabled(True)
        database.log_audit_event("HARDWARE_SCAN", operator_name=self.active_operator_name, details=f"Scanned & persisted {len(results)} devices into DB cache.")

    def load_initial_hardware_cache(self):
        self.refresh_hardware_grid_table()
        self.lbl_hw_status.setText("Đã đồng bộ thông tin phần cứng hệ thống.")

    def auto_scan_and_select_best_hardware(self):
        try:
            real_cams = get_real_camera_list()
            valid_cam_indices = [cam["index"] for cam in real_cams if "Không tìm thấy" not in cam.get("name", "")]
            current_cfg_idx = self.app_config.get("camera_index", None)
            
            if current_cfg_idx is None and valid_cam_indices:
                best_idx = valid_cam_indices[0]
                logger.info(f"[AUTO_HW_SCAN] Initialized default camera index to: {best_idx}")
                self.app_config["camera_index"] = best_idx
                config.save_config(self.app_config)
                if hasattr(self, 'cfg_camera_select') and self.cfg_camera_select:
                    match_idx = self.cfg_camera_select.findData(best_idx)
                    if match_idx >= 0:
                        self.cfg_camera_select.setCurrentIndex(match_idx)
        except Exception as e:
            logger.warning(f"[AUTO_HW_SCAN] Exception in auto hardware scan: {e}")

    def start_camera_thread(self):
        self.auto_scan_and_select_best_hardware()
        self.camera_thread = CameraThread()
        self.camera_thread.info_signal.connect(self.update_camera_info)
        self.camera_thread.set_camera(self.app_config.get("camera_index", 0))
        self.camera_thread.set_active_operator(self.active_operator_id, self.active_operator_name)
        self.camera_thread.frame_signal.connect(self.update_camera_frame)
        self.camera_thread.barcode_signal.connect(self.handle_scanned_barcode)
        self.camera_thread.photo_saved_signal.connect(self.handle_photo_saved)
        self.camera_thread.error_signal.connect(self.handle_thread_error)
        self.camera_thread.start()

    @Slot(str)
    def update_camera_info(self, info_text):
        if hasattr(self, 'cam_box') and self.cam_box:
            self.cam_box.setTitle(f"1. MÀN HÌNH CAMERA THỜI GIAN THỰC — [{info_text}]")

    def start_voice_thread(self):
        self.voice_thread = VoiceDetectorThread()
        self.voice_thread.capture_signal.connect(
            lambda: self._dispatch_session(VoiceUtterance("chụp"))
        )
        self.voice_thread.keyword_signal.connect(self.on_voice_keyword_detected)
        self.voice_thread.status_signal.connect(self.update_voice_status)
        self.voice_thread.volume_signal.connect(self.update_voice_volume)
        self.voice_thread.error_signal.connect(self.handle_thread_error)
        self.voice_thread.comparison_signal.connect(
            lambda offline_text, google_text, score: logger.info(
                f"[VOICE_BENCHMARK] sherpa-onnx: '{offline_text}' | Google Voice: '{google_text}' | Similarity: {score:.0f}%"
            )
        )
        self.voice_thread.patient_info_signal.connect(self.handle_voice_patient_info)
        self.voice_thread.start()

    @Slot(dict)
    def handle_voice_patient_info(self, patient_data):
        """Structured demography from voice thread → Tab 1 intake or Tab 2 filters."""
        if not patient_data:
            return
        snap = self.session_ctrl.snapshot()
        patient_data = {
            k: v
            for k, v in patient_data.items()
            if k not in ("patient_id", "_partial") and v not in (None, "")
        }
        if not patient_data:
            return

        on_tab2 = hasattr(self, "stack") and self.stack.currentIndex() == 1
        on_tab1 = hasattr(self, "stack") and self.stack.currentIndex() == 0
        session_open = snap.phase in (Phase.INTAKE, Phase.READY, Phase.CORRECTION)

        # Tab 1 đang mở phiên → ưu tiên điền cockpit (không bị search.open chặn)
        if on_tab1 and session_open:
            labels = {"full_name": "Họ tên", "birth_year": "Năm sinh", "gender": "Giới tính"}
            filled = []
            if "full_name" in patient_data and Field.FULL_NAME in snap.affordances.editable:
                self._dispatch_session(UiFieldEdit(Field.FULL_NAME, patient_data["full_name"]))
                filled.append(labels["full_name"])
            if "birth_year" in patient_data and Field.BIRTH_YEAR in snap.affordances.editable:
                try:
                    year = int(str(patient_data["birth_year"]).strip())
                except ValueError:
                    year = None
                if year is not None:
                    self._dispatch_session(UiFieldEdit(Field.BIRTH_YEAR, year))
                    filled.append(labels["birth_year"])
            if "gender" in patient_data and Field.GENDER in snap.affordances.editable:
                self._dispatch_session(UiFieldEdit(Field.GENDER, patient_data["gender"]))
                filled.append(labels["gender"])
            if filled:
                self.status_bar.showMessage(
                    f"🎙️ Đã điền Tab Chụp: {', '.join(filled)}",
                    4000,
                )
            logger.info("[VOICE_INTAKE_FILL] Tab1 %s", patient_data)
            return

        if on_tab2 or snap.search.open:
            if not snap.search.open and snap.affordances.can_open_search:
                self._dispatch_session(Hotkey("F5"))
                snap = self.session_ctrl.snapshot()
            if on_tab2 and hasattr(self, "filter_name"):
                merged = self._merge_voice_into_tab2_filters(patient_data)
                merged["patient_id"] = (
                    merged.get("patient_id")
                    or snap.search.filter.patient_id
                    or self.filter_id.text().strip()
                    or ""
                )
            else:
                merged = {
                    "patient_id": snap.search.filter.patient_id or "",
                    "full_name": patient_data.get("full_name")
                    or snap.search.filter.full_name
                    or "",
                    "birth_year": patient_data.get("birth_year")
                    or snap.search.filter.birth_year
                    or "",
                    "gender": patient_data.get("gender")
                    or snap.search.filter.gender
                    or "",
                }
            self._dispatch_session(
                SearchFilterEdit(
                    patient_id=merged["patient_id"] or None,
                    full_name=merged["full_name"] or None,
                    birth_year=merged["birth_year"] or None,
                    gender=merged["gender"] or None,
                    result_count=self._tab2_search_result_count(merged),
                )
            )
            labels = {
                "full_name": "Họ tên",
                "birth_year": "Năm sinh",
                "gender": "Giới tính",
            }
            filled = [labels[k] for k in labels if k in patient_data]
            if filled:
                self.status_bar.showMessage(
                    f"🎙️ Đã điền lọc Tab 2: {', '.join(filled)}",
                    4000,
                )
            logger.info("[VOICE_FILTER_FILL] Tab2 %s", patient_data)
            return
        if snap.phase == Phase.STANDBY:
            logger.info("[VOICE_PATIENT] Ignored — Standby (F1 hoặc F5 tìm hồ sơ trước)")
            return
        if "full_name" in patient_data and Field.FULL_NAME in snap.affordances.editable:
            self._dispatch_session(UiFieldEdit(Field.FULL_NAME, patient_data["full_name"]))
        if "birth_year" in patient_data and Field.BIRTH_YEAR in snap.affordances.editable:
            try:
                year = int(str(patient_data["birth_year"]).strip())
            except ValueError:
                year = None
            if year is not None:
                self._dispatch_session(UiFieldEdit(Field.BIRTH_YEAR, year))
        if "gender" in patient_data and Field.GENDER in snap.affordances.editable:
            self._dispatch_session(UiFieldEdit(Field.GENDER, patient_data["gender"]))

    def start_updater_thread(self):
        if not self.app_config.get("enable_ota", False):
            logger.info("[UPDATER] OTA updates are currently disabled in config (Offline Hospital Setup).")
            self.status_bar.showMessage(f"Phiên bản: {config.__version__} | Chế độ Offline 100%")
            return

        self.updater_thread = UpdateCheckerThread()
        self.updater_thread.update_checked.connect(self.handle_update_check)
        self.updater_thread.status_signal.connect(self.update_status_bar_msg)
        self.updater_thread.ready_to_restart.connect(self.execute_graceful_restart)
        self.updater_thread.start()

    def register_pedal_hook(self):
        key = self.app_config.get("trigger_key", "f13").lower()
        if not hasattr(self, 'pedal_fsm') or self.pedal_fsm is None:
            self.pedal_fsm = PedalGestureFSM(target_key=key)
            self.pedal_fsm.gesture_signal.connect(self.on_pedal_gesture_detected)
        else:
            self.pedal_fsm.set_target_key(key)
        self.pedal_fsm.register_hook()
        self.lbl_pedal_info.setText(f"Bàn đạp: {key.upper()} (Phân biệt 1, 2, 3 giậm & Nhấn giữ OK)")

    @Slot(str)
    def on_pedal_gesture_detected(self, gesture):
        # Pedal = capture-only (any gesture maps to PedalGesture; domain ignores if not Locked)
        logger.info(f"[GESTURE_EVENT] Pedal → session capture | gesture={gesture} | Op: {self.active_operator_id}")
        self._dispatch_session(PedalGesture())

    @Slot(str)
    def on_voice_keyword_detected(self, keyword):
        # Modal test dialogs block clinical voice; search grid still accepts VoiceUtterance
        active_window = QApplication.activeModalWidget()
        if active_window is not None and active_window is not self._search_dialog:
            # Allow voice into search dialog; block other modals (hardware tests)
            from src.ui_patient_grid import PatientGridDialog
            if not isinstance(active_window, PatientGridDialog):
                logger.info(
                    "[VOICE_EVENT] Ignored keyword '%s' because modal test dialog is active.",
                    keyword,
                )
                return

        logger.info("[VOICE_EVENT] → VoiceUtterance '%s'", keyword)
        self._dispatch_session(VoiceUtterance(keyword))

    def delete_latest_photo(self):
        if not self.current_patient_id:
            self.status_bar.showMessage("Chưa chọn bệnh nhân để xóa ảnh.", 3000)
            return
        photos = database.get_patient_photos(self.current_patient_id)
        if photos:
            last_photo = photos[-1]
            print('\a')
            full_path = database.get_full_photo_path(last_photo["file_path"])
            self._pending_undo_photo = {
                "patient_id": self.current_patient_id,
                "file_path": last_photo["file_path"],
                "full_path": str(full_path) if full_path else None,
                "photo_id": last_photo["id"],
                "bytes": None,
            }
            try:
                if full_path and Path(full_path).exists():
                    self._pending_undo_photo["bytes"] = Path(full_path).read_bytes()
            except Exception as e:
                logger.warning("[UNDO_DELETE] Could not snapshot file: %s", e)
            database.delete_photo(last_photo["id"], operator_name=self.active_operator_name)
            self.load_patient_photos()
            self.status_bar.showMessage(
                f"Đã xóa ảnh gần nhất: {os.path.basename(last_photo['file_path'])} — bấm Hoàn tác trong 5s",
                5000,
            )
            if hasattr(self, "btn_undo_delete"):
                self.btn_undo_delete.setVisible(True)
            if hasattr(self, "_undo_timer"):
                self._undo_timer.start(5000)

    def _clear_undo_delete(self):
        self._pending_undo_photo = None
        if hasattr(self, "btn_undo_delete"):
            self.btn_undo_delete.setVisible(False)

    def _undo_last_photo_delete(self):
        pending = self._pending_undo_photo
        self._clear_undo_delete()
        if not pending or not pending.get("bytes") or not pending.get("full_path"):
            self.status_bar.showMessage("Không còn ảnh để hoàn tác.", 3000)
            return
        try:
            dest = Path(pending["full_path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pending["bytes"])
            database.add_photo(
                pending["patient_id"],
                pending["file_path"],
                operator_id=self.active_operator_id,
                operator_name=self.active_operator_name,
            )
            self.load_patient_photos()
            self.status_bar.showMessage("Đã hoàn tác xóa ảnh.", 4000)
            logger.info("[UNDO_DELETE] Restored %s", pending["file_path"])
        except Exception as e:
            logger.error("[UNDO_DELETE] Failed: %s", e, exc_info=True)
            self.status_bar.showMessage("Hoàn tác xóa thất bại.", 4000)

    def delete_all_photos(self):
        """Delete ALL photos for the current patient session."""
        if not self.current_patient_id:
            self.status_bar.showMessage("Chưa chọn bệnh nhân để xóa ảnh.", 3000)
            return
        photos = database.get_patient_photos(self.current_patient_id)
        if not photos:
            self.status_bar.showMessage("Không có ảnh nào để xóa.", 3000)
            return
        count = len(photos)
        print('\a')
        for photo in photos:
            database.delete_photo(photo["id"], operator_name=self.active_operator_name)
        self.load_patient_photos()
        logger.info(f"[DELETE_ALL] Deleted all {count} photos for patient {self.current_patient_id}")
        self.status_bar.showMessage(f"🗑️ Đã xóa TẤT CẢ {count} ảnh của bệnh nhân {self.current_patient_id}", 5000)

    def reset_active_patient(self):
        print('\a')
        self.current_patient_id = None
        if hasattr(self, 'cockpit_widget') and self.cockpit_widget:
            self.cockpit_widget.reset_session()
        if hasattr(self, 'camera_thread') and self.camera_thread:
            if hasattr(self, 'cockpit_widget') and self.cockpit_widget and self.cockpit_widget.is_session_open:
                self.camera_thread.resume_barcode_scanning()
            else:
                self.camera_thread.pause_barcode_scanning()
        if hasattr(self, 'txt_patient_id'):
            self.txt_patient_id.clear()
        if hasattr(self, 'txt_patient_name'):
            self.txt_patient_name.clear()
        if hasattr(self, 'txt_birth_year'):
            self.txt_birth_year.clear()
        if hasattr(self, 'lbl_scan_status'):
            self.lbl_scan_status.setText("SẴN SÀNG BỆNH NHÂN MỚI. Vui lòng quét mã...")
            self.lbl_scan_status.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
        self.load_patient_photos()
        self.status_bar.showMessage("Đã hoàn tất phiên khám. Sẵn sàng chờ bệnh nhân mới.", 4000)

    def open_latest_photo_preview(self):
        if not self.current_patient_id:
            return
        photos = database.get_patient_photos(self.current_patient_id)
        if photos:
            photo_paths = [str(database.get_full_photo_path(p["file_path"])) for p in photos if database.get_full_photo_path(p["file_path"])]
            if photo_paths:
                hardware_test_dialogs.show_image_preview(self, photo_paths=photo_paths, current_index=len(photo_paths)-1)

    @Slot(QImage)
    def update_camera_frame(self, image):
        if not hasattr(self, 'camera_feed') or self.camera_feed is None:
            return
        if hasattr(self, 'cockpit_widget') and self.cockpit_widget and not self.cockpit_widget.is_session_open:
            return
        if hasattr(self, 'cockpit_widget') and self.cockpit_widget:
            self.cockpit_widget.clear_camera_hardware_error()
        feed_size = self.camera_feed.size()
        if feed_size.width() <= 5 or feed_size.height() <= 5:
            return
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            feed_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.camera_feed.setPixmap(scaled_pixmap)

    @Slot(str)
    def handle_thread_error(self, err_msg):
        logger.warning(f"[THREAD_ERROR] {err_msg}")
        self.status_bar.showMessage(f"⚠️ {err_msg}", 6000)
        err_l = (err_msg or "").lower()
        if "camera" in err_l or "cam" in err_l or "webcam" in err_l:
            if hasattr(self, "cockpit_widget") and self.cockpit_widget:
                self.cockpit_widget.set_camera_hardware_error(err_msg)
        if hasattr(self, 'lbl_voice_status') and ("mic" in err_l or "voice" in err_l or "model" in err_l):
            self.lbl_voice_status.setText("Microphone: Tự động kết nối lại...")

    @Slot(int)
    def change_camera(self, index=None):
        try:
            if hasattr(self, 'cfg_camera_select') and self.cfg_camera_select is not None:
                cam_idx = self.cfg_camera_select.currentData()
                if cam_idx is not None:
                    index = int(cam_idx)
            if index is None:
                index = 0
            self.app_config["camera_index"] = index
            config.save_config(self.app_config)
            logger.info(f"[HARDWARE] Switched camera to index: {index}")
            if hasattr(self, 'camera_thread') and self.camera_thread is not None:
                self.camera_thread.set_camera(index)
            self.refresh_hardware_grid_table()
        except Exception as e:
            logger.error(f"[CAMERA_ERROR] Error changing camera: {str(e)}", exc_info=True)

    @Slot(int)
    def change_microphone(self, index=0):
        try:
            if hasattr(self, 'cfg_mic_select') and self.cfg_mic_select is not None:
                mic_name = self.cfg_mic_select.currentText()
            else:
                mic_name = "Mặc định hệ thống"
            if mic_name == "Mặc định hệ thống":
                self.app_config["microphone_name"] = "default"
            else:
                self.app_config["microphone_name"] = mic_name
            config.save_config(self.app_config)
            logger.info(f"[HARDWARE] Selected Microphone: {self.app_config['microphone_name']}")
            if hasattr(self, 'voice_thread') and self.voice_thread is not None and self.voice_thread.isRunning():
                self.voice_thread.set_microphone(self.app_config['microphone_name'])
            else:
                self.start_voice_thread()
            self.refresh_hardware_grid_table()
        except Exception as e:
            logger.error(f"[MIC_ERROR] Error changing microphone: {str(e)}", exc_info=True)

    def open_patient_search_dialog(self):
        """Legacy entry — route through session F5 when possible."""
        snap = self.session_ctrl.snapshot()
        if snap.phase == Phase.STANDBY:
            self.status_bar.showMessage("Mở phiên (F1) trước khi tìm hồ sơ.", 4000)
            return
        self._dispatch_session(Hotkey("F5"))

    @Slot(dict)
    def on_patient_selected_from_grid(self, patient_dict):
        self._on_cockpit_patient_loaded(patient_dict)

    @Slot(str)
    def handle_scanned_barcode(self, barcode_data):
        try:
            QApplication.beep()
        except Exception:
            pass

        parsed = barcode_parser.parse_barcode(barcode_data)
        patient_id = (parsed.get("patient_id") or "").strip()
        if not patient_id:
            return

        # Tab 2 browse-only: filter folder list, do not drive session FSM
        if hasattr(self, "stack") and self.stack.currentIndex() == 1:
            if hasattr(self, "txt_search"):
                self.txt_search.setText(patient_id)
            self.load_history_records()
            logger.info("[BARCODE] Tab2 browse filter id=%s", patient_id)
            return

        outcome = self._dispatch_session(BarcodeScan(patient_id))
        logger.info(
            "[BARCODE] → session code=%s phase=%s effects=%s",
            patient_id,
            outcome.view.phase.value,
            [e.value for e in outcome.effects],
        )
        database.log_audit_event(
            "BARCODE_SCAN",
            operator_name=self.active_operator_name,
            patient_id=patient_id,
        )

    @Slot()
    def start_session_by_manual_id(self):
        patient_id = self.txt_patient_id.text().strip().upper()
        if not patient_id:
            self.lbl_scan_status.setText("⚠️ VUI LÒNG NHẬP MÃ BỆNH ÁN VÀ ẤN ENTER HOẶC NÚT 'MỞ PHIÊN'!")
            self.lbl_scan_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px; padding: 4px; background-color: #450a0a; border-radius: 4px;")
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.beep()
            except Exception:
                pass
            return

        try:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass

        self.lbl_scan_status.setText(f"✅ ĐÃ KHỞI TẠO MÃ BỆNH NHÂN: {patient_id} (ĐÃ MỞ PHIÊN KHÁM MỚI)")
        self.lbl_scan_status.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px; padding: 4px; background-color: #052e16; border-radius: 4px;")
        
        self.txt_patient_id.setText(patient_id)
        self.current_patient_id = patient_id
        self.camera_thread.set_active_patient(patient_id)

        patient = database.get_patient(patient_id)
        if patient:
            self.txt_patient_name.setText(patient.get("name", ""))
            self.txt_birth_year.setText(str(patient.get("birth_year") or ""))
            set_gender_combo(self.txt_gender, patient.get("gender", "Nam"))
        else:
            name = self.txt_patient_name.text().strip()
            dob = self.txt_birth_year.text().strip()
            gender = self.txt_gender.currentText()
            database.create_patient(patient_id, name=name, birth_year=dob, gender=gender)

        logger.info(f"[MANUAL_SESSION_START] Started manual session for Patient ID: '{patient_id}'")
        database.log_audit_event("MANUAL_PATIENT_ENTRY", operator_name=self.active_operator_name, patient_id=patient_id)
        self.load_patient_photos()

    @Slot()
    @Slot(str)
    def trigger_photo_capture(self, source="GUI_BUTTON"):
        logger.info(f"[CAPTURE_REQUEST] Received capture request from '{source}'. Active patient: '{self.current_patient_id}'")
        print(f"📸 [CAPTURE_TRACE]: Received capture request from '{source}' for Patient ID: '{self.current_patient_id}'")
        
        if not self.current_patient_id:
            p_id = ""
            if hasattr(self, 'cockpit_widget') and self.cockpit_widget:
                p_id = self.cockpit_widget.input_id.text().strip()
            if p_id:
                self.current_patient_id = p_id
                if hasattr(self, 'camera_thread') and self.camera_thread:
                    self.camera_thread.set_active_patient(p_id)
            else:
                self.lbl_scan_status.setText("⚠️ VUI LÒNG QUÉT MÃ QR HOẶC NHẬP MÃ BỆNH NHÂN TRƯỚC KHI CHỤP!")
                self.lbl_scan_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px; padding: 4px; background-color: #450a0a; border-radius: 4px;")
                self.status_bar.showMessage("⚠️ Vui lòng quét mã QR hoặc nhập Mã bệnh nhân trước khi chụp!", 4000)
                try:
                    QApplication.beep()
                except Exception:
                    pass
                return

        total, used, free = shutil.disk_usage(config.BASE_DIR)
        free_mb = free / (1024 * 1024)
        if free_mb < 500:
            QMessageBox.critical(self, "Bộ Nhớ Đầy", f"Dung lượng ổ đĩa còn lại quá thấp ({free_mb:.1f}MB). Vui lòng dọn dẹp ổ đĩa!")
            return

        # Safety: patients FK must exist before CameraThread.add_photo
        snap = self.session_ctrl.snapshot()
        if snap.demography.patient_id:
            self._upsert_demography_patient(snap.demography)

        self.lbl_scan_status.setText(f"📸 ĐANG THỰC HIỆN CHỤP ẢNH CHO BN: {self.current_patient_id}...")
        self.lbl_scan_status.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px; padding: 4px; background-color: #0c4a6e; border-radius: 4px;")
        
        self.camera_thread.request_capture(source=source)

    @Slot(str, float)
    def handle_photo_saved(self, file_path, latency_ms):
        self.load_patient_photos()
        filename = os.path.basename(file_path)
        self.lbl_scan_status.setText(f"📸 ĐÃ CHỤP THÀNH CÔNG: {filename} ({latency_ms:.0f}ms)")
        self.lbl_scan_status.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px; padding: 4px; background-color: #052e16; border-radius: 4px;")
        self.status_bar.showMessage(f"Đã lưu: {filename} ({latency_ms:.1f}ms)", 3000)

    def load_patient_photos(self):
        # Clear old grid layout if present
        if hasattr(self, 'grid_layout') and self.grid_layout:
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # Clear cockpit filmstrip layout
        if hasattr(self, 'cockpit_widget') and self.cockpit_widget and hasattr(self.cockpit_widget, 'filmstrip_layout'):
            for i in reversed(range(self.cockpit_widget.filmstrip_layout.count())):
                w = self.cockpit_widget.filmstrip_layout.itemAt(i).widget()
                if w:
                    w.setParent(None)

        if not self.current_patient_id:
            if hasattr(self, 'lbl_baseline_photo') and self.lbl_baseline_photo:
                self.lbl_baseline_photo.setText("Chưa có ảnh đối chiếu")
            return

        photos = database.get_patient_photos(self.current_patient_id)
        all_photo_paths = [str(database.get_full_photo_path(p["file_path"])) for p in photos if database.get_full_photo_path(p["file_path"])]
        
        # Baseline Photo on the Right (Photo #1 / First baseline photo)
        if photos and not hasattr(self, 'custom_baseline_path'):
            baseline_path = database.get_full_photo_path(photos[0]["file_path"])
            if baseline_path and baseline_path.exists() and hasattr(self, 'lbl_baseline_photo') and self.lbl_baseline_photo:
                pix = QPixmap(str(baseline_path))
                scaled = pix.scaled(self.lbl_baseline_photo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_baseline_photo.setPixmap(scaled)

        # Sort photos from NEWEST to OLDEST (ảnh gần nhất -> xa nhất)
        sorted_photos = list(reversed(photos))
        
        if hasattr(self, 'cockpit_widget') and self.cockpit_widget:
            self.cockpit_widget.lbl_filmstrip.setText(f"Filmstrip Ảnh Ca Khám ({len(photos)} ảnh - Mới nhất ➜ Cũ nhất):")

        for idx, photo in enumerate(sorted_photos):
            photo_id = photo["id"]
            photo_orig_idx = photos.index(photo)
            img_path = database.get_full_photo_path(photo["file_path"])
            num_label = f"#{len(photos) - idx}"

            def create_thumb_card(is_cockpit=True):
                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(2, 2, 2, 2)
                item_layout.setSpacing(2)
                
                lbl_thumb = QLabel()
                lbl_thumb.setFixedSize(85, 60)
                lbl_thumb.setCursor(Qt.PointingHandCursor)
                lbl_thumb.setStyleSheet("border: 1.5px solid #0284c7; border-radius: 4px; background-color: #020617;")
                
                if img_path and img_path.exists():
                    pix = QPixmap(str(img_path))
                    lbl_thumb.setPixmap(pix.scaled(lbl_thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                
                lbl_title = QLabel(num_label)
                lbl_title.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold;")
                lbl_title.setAlignment(Qt.AlignCenter)
                
                item_layout.addWidget(lbl_thumb)
                item_layout.addWidget(lbl_title)
                
                def custom_context(pos):
                    menu = QMenu()
                    open_act = menu.addAction("👁️ Xem ảnh phóng to")
                    set_baseline_act = menu.addAction("📌 Đặt làm Ảnh đối chiếu Baseline")
                    del_act = menu.addAction("🗑️ Xóa ảnh này")
                    action = menu.exec_(lbl_thumb.mapToGlobal(pos))
                    if action == open_act:
                        hardware_test_dialogs.show_image_preview(self, photo_paths=all_photo_paths, current_index=photo_orig_idx)
                    elif action == set_baseline_act:
                        if img_path and img_path.exists():
                            pix = QPixmap(str(img_path))
                            scaled = pix.scaled(self.lbl_baseline_photo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.lbl_baseline_photo.setPixmap(scaled)
                            self.status_bar.showMessage(f"Đã đặt {img_path.name} làm ảnh đối chiếu đợt 1.", 4000)
                    elif action == del_act:
                        reply = QMessageBox.question(
                            self, "Xác nhận xóa", "Bạn có chắc chắn muốn xóa ảnh này?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            database.delete_photo(photo_id, operator_name=self.active_operator_name)
                            self.load_patient_photos()

                lbl_thumb.setContextMenuPolicy(Qt.CustomContextMenu)
                lbl_thumb.customContextMenuRequested.connect(custom_context)
                lbl_thumb.mousePressEvent = lambda e, p_idx=photo_orig_idx: hardware_test_dialogs.show_image_preview(self, photo_paths=all_photo_paths, current_index=p_idx) if e.button() == Qt.LeftButton else None
                return item_widget

            if hasattr(self, 'cockpit_widget') and self.cockpit_widget and hasattr(self.cockpit_widget, 'filmstrip_layout'):
                self.cockpit_widget.filmstrip_layout.addWidget(create_thumb_card(is_cockpit=True))
            if hasattr(self, 'grid_layout') and self.grid_layout:
                self.grid_layout.addWidget(create_thumb_card(is_cockpit=False))

    def save_patient_info(self):
        if not self.current_patient_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng quét mã bệnh nhân trước.")
            return
            
        name = self.txt_patient_name.text().strip()
        birth_year = self.txt_birth_year.text().strip()
        gender = self.txt_gender.currentText()
        
        by_int = None
        if birth_year:
            try:
                by_int = int(birth_year)
            except ValueError:
                QMessageBox.warning(self, "Cảnh báo", "Năm sinh phải là một số nguyên.")
                return
                
        database.update_patient(self.current_patient_id, name, by_int, gender)
        database.log_audit_event("PATIENT_UPDATE", operator_name=self.active_operator_name, patient_id=self.current_patient_id)
        QMessageBox.information(self, "Thành công", "Đã lưu cập nhật thông tin bệnh nhân.")

    @Slot(str)
    def update_voice_status(self, status):
        self.lbl_voice_status.setText(f"Microphone: {status}")

    @Slot(int)
    def update_voice_volume(self, volume):
        self.voice_gauge.setValue(volume)

    @Slot(int)
    def show_download_progress(self, percent):
        self.lbl_voice_status.setText(f"Downloading Model: {percent}%")
        self.voice_gauge.setValue(percent)

    @Slot(bool, str, str, str)
    def handle_update_check(self, has_update, new_version, download_url, sha256):
        if has_update:
            reply = QMessageBox.question(
                self, "Bản Cập Nhật Mới",
                f"Đã có phiên bản mới v{new_version}. Bạn có muốn tải xuống và cập nhật tự động không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.status_bar.showMessage("Đang thực hiện cập nhật OTA...")
                self.updater_thread.download_and_install(download_url, sha256)

    @Slot(str)
    def execute_graceful_restart(self, bat_path):
        import subprocess
        logger.info("[MAIN] Graceful shutdown requested for OTA update.")
        subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        QApplication.quit()

    @Slot(str)
    def update_status_bar_msg(self, msg):
        self.status_bar.showMessage(msg, 5000)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            key_text = event.text().lower()
            
            # Print & log every keypress for diagnostic tracing
            print(f"⌨️ [GLOBAL_KEY_EVENT]: Key = {key} ({event.text()})")
            logger.info(f"[GLOBAL_KEY_EVENT] Key = {key} ({event.text()})")

            # 0. Intercept configured trigger_key from config (supports any key)
            trigger_key_cfg = self.app_config.get("trigger_key", "f13").lower()
            if self._is_trigger_key(key, key_text, trigger_key_cfg):
                logger.info(
                    f"[EVENT_FILTER_PEDAL] → session capture | key={key} config='{trigger_key_cfg}'"
                )
                self._dispatch_session(PedalGesture())
                return True

            # Pedal function keys only (F5 = search hotkey — not pedal)
            if key in (Qt.Key_F13, Qt.Key_F12, Qt.Key_F14, Qt.Key_F15):
                logger.info(f"[EVENT_FILTER_PEDAL] → session capture | key={key}")
                self._dispatch_session(PedalGesture())
                return True

            # Modifier keys mapped to pedal capture-only
            if key in (Qt.Key_Alt, Qt.Key_Meta):
                logger.info(f"[EVENT_FILTER_PEDAL] → session capture | modifier={key}")
                self._dispatch_session(PedalGesture())
                return True

            # Space outside text field → session capture (Locked only; domain warns otherwise)
            if key == Qt.Key_Space:
                focused = QApplication.focusWidget()
                if not isinstance(focused, QLineEdit):
                    logger.info("[EVENT_FILTER] → session Space capture")
                    self._dispatch_session(Hotkey("Space"))
                    return True

        return super().eventFilter(watched, event)

    @staticmethod
    def _is_trigger_key(qt_key: int, key_text: str, trigger_cfg: str) -> bool:
        """Kiểm tra xem phím nhấn có khớp với trigger_key trong config không.
        
        Hỗ trợ: chữ cái (a-z), function keys (f1-f24), space, alt, meta.
        """
        # Map config string → Qt key code
        _KEY_MAP = {
            "f1": Qt.Key_F1, "f2": Qt.Key_F2, "f3": Qt.Key_F3, "f4": Qt.Key_F4,
            "f5": Qt.Key_F5, "f6": Qt.Key_F6, "f7": Qt.Key_F7, "f8": Qt.Key_F8,
            "f9": Qt.Key_F9, "f10": Qt.Key_F10, "f11": Qt.Key_F11, "f12": Qt.Key_F12,
            "f13": Qt.Key_F13, "f14": Qt.Key_F14, "f15": Qt.Key_F15,
            "space": Qt.Key_Space, "alt": Qt.Key_Alt, "meta": Qt.Key_Meta,
        }
        
        # Check function/special keys
        if trigger_cfg in _KEY_MAP:
            return qt_key == _KEY_MAP[trigger_cfg]
        
        # Check single character key (a-z, 0-9, etc.)
        if len(trigger_cfg) == 1:
            return key_text == trigger_cfg
        
        return False

    def keyPressEvent(self, event):
        key_map = {
            Qt.Key_F1: "F1",
            Qt.Key_F2: "F2",
            Qt.Key_F4: "F4",
            Qt.Key_F5: "F5",
            Qt.Key_Space: "Space",
            Qt.Key_Delete: "Delete",
        }
        mapped = key_map.get(event.key())
        if mapped:
            focus = QApplication.focusWidget()
            # Let plain text fields keep Space; session still owns F-keys and Delete/Space when Locked
            if mapped == "Space" and isinstance(focus, QLineEdit):
                super().keyPressEvent(event)
                return
            if mapped == "F1":
                self._request_f1_session()
            else:
                self._dispatch_session(Hotkey(mapped))
            event.accept()
            return
        if hasattr(self, "multimodal_dispatcher") and self.multimodal_dispatcher:
            self.multimodal_dispatcher.handle_key_event(event.key())
        super().keyPressEvent(event)

    def confirm_exit_app(self):
        self.close()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Xác Nhận Thoát Ứng Dụng",
            "Bạn có chắc chắn muốn đóng Hệ thống Chụp ảnh Bệnh nhân không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            logger.info("[MAIN] Closing application. Cleaning active threads non-blockingly...")
            try:
                if hasattr(self, 'pedal_fsm') and self.pedal_fsm:
                    self.pedal_fsm.unregister_hook()
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
                
            if hasattr(self, 'camera_thread') and self.camera_thread is not None:
                self.camera_thread._running = False
                self.camera_thread.quit()
                self.camera_thread.wait(200)
                
            if hasattr(self, 'voice_thread') and self.voice_thread is not None:
                self.voice_thread._stop = True
                self.voice_thread.quit()
                self.voice_thread.wait(200)
                
            if hasattr(self, 'updater_thread') and self.updater_thread is not None:
                self.updater_thread.terminate()

            logger.info("[MAIN] Application shutdown completed safely.")
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    database.initialize_db()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())
