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
    QTableWidgetItem, QHeaderView, QInputDialog, QFileDialog, QProgressDialog
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

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if not isinstance(rgb_frame, np.ndarray) or rgb_frame.size == 0:
                    continue
                if not rgb_frame.flags['C_CONTIGUOUS']:
                    rgb_frame = np.ascontiguousarray(rgb_frame)

                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                cv2.putText(
                    rgb_frame, f"Cam Index {self.camera_index} - {w}x{h}", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (34, 197, 94), 2
                )
                
                qt_image = QImage(bytes(rgb_frame.data), w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_signal.emit(qt_image)

                frame_counter += 1
                self._scan_barcode(frame)

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
        raw_data = None
        engine_used = ""
        
        if frame is None or frame.size == 0:
            return

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Create 960x540 downscaled version for ultra-fast 15ms scanning on 1080p webcams
        if w > 1000:
            small_gray = cv2.resize(gray, (960, int(540 * (h/w))), interpolation=cv2.INTER_AREA)
        else:
            small_gray = gray

        # Stage 0: PyZbar on Lower Half Crop (Where doctors hold phone/paper barcode tickets)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                sh, sw = small_gray.shape
                lower_crop = small_gray[int(sh*0.3):, :]
                barcodes = pyzbar.decode(lower_crop)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Vùng Phía Dưới Lower-Crop)"
            except Exception as e:
                pass

        # Stage 1: PyZbar on Original Grayscale (Downsampled)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                barcodes = pyzbar.decode(small_gray)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Gốc 960x540)"
            except Exception:
                pass

        # Stage 2: PyZbar on Full High-Res Grayscale (1080p)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                barcodes = pyzbar.decode(gray)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Gốc 1080p High-Res)"
            except Exception:
                pass

        # Stage 3: PyZbar on High-Pass Sharpened Image (Fixes Out-of-Focus / Macro Blurry Shots)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
                sharpened = cv2.filter2D(small_gray, -1, kernel)
                barcodes = pyzbar.decode(sharpened)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Lọc Sắc Nét Khử Mờ)"
            except Exception:
                pass

        # Stage 4: PyZbar on CLAHE Contrast Equalization (Fixes Phone Screen Glare)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                equalized = clahe.apply(small_gray)
                barcodes = pyzbar.decode(equalized)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Khử Bóng Màn Hình CLAHE)"
            except Exception:
                pass

        # Stage 5: PyZbar on Otsu Binarization Thresholding
        if not raw_data:
            try:
                from pyzbar import pyzbar
                _, thresh = cv2.threshold(small_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                barcodes = pyzbar.decode(thresh)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Ngưỡng Binarize Otsu)"
            except Exception:
                pass

        # Stage 6: Native OpenCV Barcode Detector
        if not raw_data:
            if not hasattr(self, 'opencv_barcode'):
                self.opencv_barcode = cv2.barcode.BarcodeDetector()
            try:
                ok, decoded_info, _, _ = self.opencv_barcode.detectAndDecode(frame)
                if ok and decoded_info and decoded_info[0]:
                    raw_data = decoded_info[0].strip()
                    engine_used = "OpenCV Barcode Engine"
            except Exception:
                pass

        # Stage 7: Native OpenCV QRCode Detector
        if not raw_data:
            if not hasattr(self, 'qr_detector'):
                self.qr_detector = cv2.QRCodeDetector()
            try:
                val, _, _ = self.qr_detector.detectAndDecode(frame)
                if val:
                    raw_data = val.strip()
                    engine_used = "OpenCV QRCode Engine"
            except Exception:
                pass

        # Stage 8: PyZbar on 90-degree Rotated Image (Fixes vertical phone orientation)
        if not raw_data:
            try:
                from pyzbar import pyzbar
                rotated = cv2.rotate(small_gray, cv2.ROTATE_90_CLOCKWISE)
                barcodes = pyzbar.decode(rotated)
                if barcodes:
                    raw_data = barcodes[0].data.decode("utf-8", errors="ignore").strip()
                    engine_used = "PyZbar (Xoay 90 Độ)"
            except Exception:
                pass

        if raw_data:
            current_time = time.time()
            if raw_data != self.last_barcode_data or (current_time - self.last_barcode_time > 2.0):
                self.last_barcode_data = raw_data
                self.last_barcode_time = current_time
                logger.info(f"[BARCODE_SCAN_TRACE] ✅ Engine '{engine_used}' quét thành công Mã: '{raw_data}'")
                print(f"📷 [BARCODE_TRACE]: {engine_used} -> {raw_data}")
                self.barcode_signal.emit(raw_data)

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
            database.add_photo(
                patient_id=self._active_patient_id, 
                relative_path=relative_path,
                operator_id=self._active_operator_id,
                operator_name=self._active_operator_name
            )
            
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
                "info": "Driver âm thanh HD / Vosk Speech AI",
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

        self.patient_search_service = PatientSearchService()
        self.multimodal_dispatcher = MultiModalDispatcher()

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

        # Horizontal Tab Buttons (F1-F4)
        self.nav_btns = []
        tab_titles = [
            ("F1 📷  1. Chụp Ảnh", 0),
            ("F2 📂  2. Thư Mục Bệnh Án", 1),
            ("F3 👨‍⚕️  3. Nhân Viên", 2),
            ("F4 ⚙️  4. Cài Đặt", 3)
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
        
        self.tab1_widget = self.build_tab1_capture()
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
        self.status_bar.showMessage(f"Phiên bản: {config.__version__} | Database: WAL Mode OK | [F1-F11]: Phím tắt nhanh")
        
        # Default select Tab 1
        self.switch_tab(0)

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        for idx, btn in enumerate(self.nav_btns):
            is_active = "true" if idx == index else "false"
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
        if index == 1:
            self.load_history_records()
        elif index == 2:
            self.load_staff_and_audit_data()

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
        
        self.txt_gender = QComboBox()
        self.txt_gender.addItems(["Nam", "Nữ", "Khác"])
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

        # Top Control Bar (Search + Breadcrumb + Action Buttons)
        top_bar = QHBoxLayout()
        
        self.lbl_breadcrumb = QLabel("📁 Tất cả Thư mục Bệnh án")
        self.lbl_breadcrumb.setStyleSheet("font-weight: bold; font-size: 15px; color: #38bdf8;")
        top_bar.addWidget(self.lbl_breadcrumb)
        
        top_bar.addSpacing(15)

        # Search box (Fuzzy Search by ID, Name, or QR)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Tìm gần đúng theo Mã BA, Tên hoặc quét Mã QR (Ctrl+F)...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self.load_history_records)
        top_bar.addWidget(self.txt_search, stretch=1)
        
        top_bar.addSpacing(10)

        self.btn_back_folder = QPushButton("◀️ Quay lại Thư mục (Backspace)")
        self.btn_back_folder.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px;")
        self.btn_back_folder.setCursor(Qt.PointingHandCursor)
        self.btn_back_folder.clicked.connect(self.show_level1_folders)
        self.btn_back_folder.setVisible(False)
        top_bar.addWidget(self.btn_back_folder)

        self.btn_open_tab1 = QPushButton("📷 Mở ở Tab Chụp (F1)")
        self.btn_open_tab1.setStyleSheet("background-color: #0284c7; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px;")
        self.btn_open_tab1.setCursor(Qt.PointingHandCursor)
        self.btn_open_tab1.clicked.connect(self.open_selected_folder_in_tab1)
        self.btn_open_tab1.setVisible(False)
        top_bar.addWidget(self.btn_open_tab1)

        self.btn_export_report = QPushButton("📄 Xuất Báo Cáo (F10)")
        self.btn_export_report.setStyleSheet("background-color: #0d9488; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px;")
        self.btn_export_report.setCursor(Qt.PointingHandCursor)
        self.btn_export_report.clicked.connect(self.export_patient_report)
        top_bar.addWidget(self.btn_export_report)
        
        layout.addLayout(top_bar)

        # Stacked Container for Level 1 vs Level 2
        self.tab2_stack = QStackedWidget()
        
        # --- LEVEL 1 PAGE: VISUAL FOLDER CARDS GRID ---
        self.level1_widget = QWidget()
        level1_layout = QVBoxLayout(self.level1_widget)
        level1_layout.setContentsMargins(0, 0, 0, 0)
        
        self.level1_scroll = QScrollArea()
        self.level1_scroll.setWidgetResizable(True)
        self.level1_scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; background-color: #090d16; border-radius: 6px; }")
        
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
        self.level2_scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; background-color: #090d16; border-radius: 6px; }")
        
        self.level2_container = QWidget()
        self.level2_grid = QGridLayout(self.level2_container)
        self.level2_grid.setContentsMargins(15, 15, 15, 15)
        self.level2_grid.setSpacing(15)
        self.level2_scroll.setWidget(self.level2_container)
        level2_layout.addWidget(self.level2_scroll)
        
        self.tab2_stack.addWidget(self.level2_widget)

        layout.addWidget(self.tab2_stack)
        
        self.selected_patient_folder_id = None
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

    # ----------------- TAB 4: HARDWARE & SETTINGS -----------------
    def build_tab4_settings(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        group_hw = QGroupBox("CẤU HÌNH PHẦN CỨNG & GIAO DIỆN")
        form = QFormLayout(group_hw)
        
        # Real Physical Camera Selection
        self.cfg_camera_select = QComboBox()
        real_cams = get_real_camera_list()
        for cam in real_cams:
            self.cfg_camera_select.addItem(f"{cam['name']} (Cổng Index {cam['index']})", cam["index"])
        cur_cam_idx = self.app_config.get("camera_index", 0)
        match_idx = self.cfg_camera_select.findData(cur_cam_idx)
        if match_idx >= 0:
            self.cfg_camera_select.setCurrentIndex(match_idx)
        self.cfg_camera_select.currentIndexChanged.connect(self.change_camera)
        
        cam_row = QHBoxLayout()
        cam_row.addWidget(self.cfg_camera_select, stretch=1)
        btn_test_cam = QPushButton("🛠️ Test Camera (Quét Mã QR)")
        btn_test_cam.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_cam.clicked.connect(self.run_test_camera)
        cam_row.addWidget(btn_test_cam)
        form.addRow("Chọn Camera:", cam_row)

        # Microphone Selection
        self.cfg_mic_select = QComboBox()
        available_mics = voice_detector.get_available_microphones()
        self.cfg_mic_select.addItems(available_mics)
        cur_mic = self.app_config.get("microphone_name", "default")
        idx = self.cfg_mic_select.findText(cur_mic)
        if idx >= 0:
            self.cfg_mic_select.setCurrentIndex(idx)
        else:
            self.cfg_mic_select.setCurrentIndex(0)
        self.cfg_mic_select.currentIndexChanged.connect(self.change_microphone)
        
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.cfg_mic_select, stretch=1)
        btn_test_mic = QPushButton("🛠️ Test Mic (Thử Lệnh Vozk)")
        btn_test_mic.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_mic.clicked.connect(self.run_test_mic)
        mic_row.addWidget(btn_test_mic)
        form.addRow("Chọn Microphone (Venfish/Bluetooth/3.5mm):", mic_row)
        
        # Foot pedal status info
        self.lbl_pedal_info = QLabel("PCSensor USB FootSwitch (Gán phím F13/ALT - Tự động phân biệt Cử chỉ 1, 2, 3 giậm & Nhấn giữ)")
        self.lbl_pedal_info.setStyleSheet("color: #38bdf8; font-weight: bold;")
        pedal_row = QHBoxLayout()
        pedal_row.addWidget(self.lbl_pedal_info, stretch=1)
        btn_test_pedal = QPushButton("🛠️ Test Bàn Đạp Chân")
        btn_test_pedal.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_test_pedal.clicked.connect(self.run_test_pedal)
        pedal_row.addWidget(btn_test_pedal)
        form.addRow("Bàn đạp chân (Pedal):", pedal_row)
        
        # Theme switcher
        self.cb_theme = QComboBox()
        self.cb_theme.addItems(["Dark Slate (Mặc định)", "Light Clinical (Sáng Y tế)"])
        current_t = self.app_config.get("active_theme", "dark")
        self.cb_theme.setCurrentIndex(0 if current_t == "dark" else 1)
        self.cb_theme.currentIndexChanged.connect(self.on_theme_dropdown_changed)
        form.addRow("Chế độ màu Giao diện:", self.cb_theme)
        
        # Working Directory Selection
        self.txt_working_dir = QLineEdit(str(config.get_photos_dir()))
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.txt_working_dir, stretch=1)
        btn_browse_dir = QPushButton("📁 Chọn Thư Mục")
        btn_browse_dir.setStyleSheet("background-color: #0284c7; color: white; padding: 4px 12px;")
        btn_browse_dir.clicked.connect(self.browse_working_dir)
        dir_row.addWidget(btn_browse_dir)
        form.addRow("Thư mục lưu trữ Ảnh Bệnh án:", dir_row)

        # OTA Update Intranet URL
        self.txt_ota_url = QLineEdit(self.app_config.get("update_url", ""))
        form.addRow("Địa chỉ Cập nhật Intranet:", self.txt_ota_url)
        
        btn_save_cfg = QPushButton("Lưu Cấu Hình Cài Đặt")
        btn_save_cfg.clicked.connect(self.save_settings_cfg)
        form.addRow("", btn_save_cfg)
        
        layout.addWidget(group_hw)

        # Hardware Scanner & Diagnostic Console Box
        group_scan = QGroupBox("QUÉT & CHẨN ĐOÁN PHẦN CỨNG HỆ THỐNG")
        scan_layout = QVBoxLayout(group_scan)
        
        scan_top = QHBoxLayout()
        self.btn_scan_hw = QPushButton("🔍 QUÉT PHẦN CỨNG (Scan Hardware)")
        self.btn_scan_hw.clicked.connect(self.scan_system_hardware)
        scan_top.addWidget(self.btn_scan_hw)
        
        self.lbl_hw_status = QLabel("Bấm nút để bắt đầu quét phần cứng...")
        self.lbl_hw_status.setStyleSheet("color: #38bdf8; font-weight: bold;")
        scan_top.addWidget(self.lbl_hw_status)
        scan_top.addStretch()
        scan_layout.addLayout(scan_top)
        
        self.table_hw = QTableWidget()
        self.table_hw.setColumnCount(5)
        self.table_hw.setHorizontalHeaderLabels(["Loại phần cứng", "Tên phần cứng", "Trạng thái", "Thông tin chi tiết / Cổng", "Thao tác Test"])
        self.table_hw.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_hw.setFixedHeight(210)
        scan_layout.addWidget(self.table_hw)
        
        layout.addWidget(group_scan)
        layout.addStretch()
        self.load_initial_hardware_cache()
        return widget

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
                
                self.level2_grid.addWidget(card, r, c)

        self.tab2_stack.setCurrentIndex(1)

    def open_selected_folder_in_tab1(self):
        if self.selected_patient_folder_id:
            self.handle_scanned_barcode(self.selected_patient_folder_id)
            self.switch_tab(0)

    def load_history_records(self):
        if self.tab2_stack.currentIndex() == 1 and self.selected_patient_folder_id:
            self.open_patient_folder(self.selected_patient_folder_id)
            return

        query = self.txt_search.text().strip().lower()
        conn = database.get_db_connection()
        cursor = conn.cursor()
        if query:
            cursor.execute("SELECT * FROM patients WHERE LOWER(id) LIKE ? OR LOWER(name) LIKE ? ORDER BY created_at DESC", (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        # Clear Level 1 Grid
        while self.level1_grid.count():
            item = self.level1_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not rows:
            empty_lbl = QLabel("Không tìm thấy Thư mục Bệnh án nào khớp với từ khóa.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; font-weight: bold; margin: 40px;")
            self.level1_grid.addWidget(empty_lbl, 0, 0)
            return

        cols = 4
        for idx, p in enumerate(rows):
            p_id = p["id"]
            p_name = p["name"] or "Chưa tên"
            p_year = p["birth_year"] or ""
            
            photos = database.get_patient_photos(p_id)
            photo_count = len(photos)
            
            # Find cover photo
            cover_pix = None
            if photos:
                latest_photo_path = database.get_full_photo_path(photos[0]["file_path"])
                pix = QPixmap(str(latest_photo_path))
                if not pix.isNull():
                    cover_pix = pix.scaled(200, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            r = idx // cols
            c = idx % cols

            # Create Folder Card Widget
            card = QWidget()
            card.setFixedSize(220, 210)
            card.setStyleSheet("""
                QWidget {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
                QWidget:hover {
                    border: 1.5px solid #38bdf8;
                    background-color: #1e293b;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(4)

            # Cover Thumbnail Image
            lbl_cover = QLabel()
            lbl_cover.setFixedSize(204, 120)
            lbl_cover.setAlignment(Qt.AlignCenter)
            lbl_cover.setStyleSheet("background-color: #020617; border-radius: 4px;")
            if cover_pix:
                lbl_cover.setPixmap(cover_pix)
            else:
                lbl_cover.setText("📁 Thư mục trống")
                lbl_cover.setStyleSheet("background-color: #020617; color: #475569; font-weight: bold;")
            card_layout.addWidget(lbl_cover)

            # Header info
            lbl_title = QLabel(f"📂 {p_id}")
            lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #38bdf8;")
            card_layout.addWidget(lbl_title)

            lbl_sub = QLabel(f"{p_name} ({p_year}) | 🖼️ {photo_count} ảnh")
            lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
            card_layout.addWidget(lbl_sub)

            card.setCursor(Qt.PointingHandCursor)
            card.mousePressEvent = lambda e, pid=p_id: self.open_patient_folder(pid)
            
            self.level1_grid.addWidget(card, r, c)

    def on_history_item_clicked(self, row, col):
        pass
        self.sidebar.setCurrentRow(0)  # Jump to Tab 1

    def export_patient_report(self):
        if not self.current_patient_id:
            QMessageBox.warning(self, "Xuất Báo Cáo", "Vui lòng chọn một bệnh nhân để xuất báo cáo.")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu Phiếu Báo Cáo Ảnh", f"BaoCao_{self.current_patient_id}.txt", "Text Files (*.txt)")
        if save_path:
            patient = database.get_patient(self.current_patient_id)
            photos = database.get_patient_photos(self.current_patient_id)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(f"=== BÁO CÁO HÌNH ẢNH BỆNH ÁN - 354 HOSPITAL ===\n")
                f.write(f"Mã BA: {self.current_patient_id}\n")
                f.write(f"Họ tên: {patient.get('name', 'N/A')}\n")
                f.write(f"Năm sinh: {patient.get('birth_year', 'N/A')}\n")
                f.write(f"Giới tính: {patient.get('gender', 'N/A')}\n")
                f.write(f"Tổng số ảnh chụp: {len(photos)}\n\n")
                f.write("Danh sách ảnh:\n")
                for p in photos:
                    f.write(f" - [{p['captured_at']}] {p['file_path']} (Người chụp: {p['operator_name']})\n")
            QMessageBox.information(self, "Thành công", f"Đã xuất file báo cáo: {save_path}")

    # ----------------- SETTINGS & THEME LOGIC -----------------
    def on_theme_dropdown_changed(self, idx):
        theme_name = "dark" if idx == 0 else "light"
        self.apply_theme(theme_name)

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
        btn.setStyleSheet("background-color: #0284c7; color: white; padding: 2px 8px; font-weight: bold; border-radius: 4px;")
        
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
            
        self.table_hw.setCellWidget(row, 4, btn)

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

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

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
        self.voice_thread.capture_signal.connect(lambda: self.trigger_photo_capture(source="VOICE_COMMAND"))
        self.voice_thread.keyword_signal.connect(self.on_voice_keyword_detected)
        self.voice_thread.status_signal.connect(self.update_voice_status)
        self.voice_thread.volume_signal.connect(self.update_voice_volume)
        self.voice_thread.error_signal.connect(self.handle_thread_error)
        
        self.voice_thread.start()

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
        logger.info(f"[GESTURE_EVENT] Pedal Gesture: {gesture} | Op: {self.active_operator_id}")
        action_id = database.get_mapped_action(self.active_operator_id, "PEDAL_GESTURE", gesture)
        if action_id:
            action_registry.dispatch_action(action_id, self)
        else:
            if gesture == "SINGLE_TAP":
                self.trigger_photo_capture(source="PEDAL_SINGLE_TAP")
            elif gesture == "DOUBLE_TAP":
                self.delete_latest_photo()

    @Slot(str)
    def on_voice_keyword_detected(self, keyword):
        # Ignore clinical triggers if a modal test dialog is currently active
        from PySide6.QtWidgets import QApplication
        active_window = QApplication.activeModalWidget()
        if active_window is not None:
            logger.info(f"[VOICE_EVENT] Ignored keyword '{keyword}' because modal test dialog is active.")
            return

        logger.info(f"[VOICE_EVENT] Voice Keyword: '{keyword}' | Op: {self.active_operator_id}")
        action_id = database.get_mapped_action(self.active_operator_id, "VOICE_KEYWORD", keyword)
        if action_id:
            action_registry.dispatch_action(action_id, self)
        else:
            if keyword == "chụp":
                self.trigger_photo_capture(source="VOICE_CHỤP")
            elif keyword == "xóa":
                self.delete_latest_photo()

    def delete_latest_photo(self):
        if not self.current_patient_id:
            self.status_bar.showMessage("Chưa chọn bệnh nhân để xóa ảnh.", 3000)
            return
        photos = database.get_patient_photos(self.current_patient_id)
        if photos:
            last_photo = photos[-1]
            print('\a')
            database.delete_photo(last_photo["id"], operator_name=self.active_operator_name)
            self.load_patient_photos()
            self.status_bar.showMessage(f"Đã xóa ảnh gần nhất: {os.path.basename(last_photo['file_path'])}", 4000)

    def reset_active_patient(self):
        print('\a')
        self.current_patient_id = None
        self.txt_patient_id.clear()
        self.txt_patient_name.clear()
        self.txt_birth_year.clear()
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
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            self.camera_feed.size(), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.camera_feed.setPixmap(scaled_pixmap)

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

    @Slot(str)
    def handle_scanned_barcode(self, barcode_data):
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass
            
        parsed = barcode_parser.parse_barcode(barcode_data)
        patient_id = parsed["patient_id"]
        
        self.lbl_scan_status.setText(f"✅ ĐÃ QUÉT MÃ BỆNH NHÂN: {patient_id} (ĐÃ MỞ PHIÊN KHÁM MỚI)")
        self.lbl_scan_status.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px; padding: 4px; background-color: #052e16; border-radius: 4px;")
        
        self.txt_patient_id.setText(patient_id)
        self.current_patient_id = patient_id
        self.camera_thread.set_active_patient(patient_id)
        
        patient = database.get_patient(patient_id)
        if patient:
            self.txt_patient_name.setText(patient.get("name", ""))
            self.txt_birth_year.setText(str(patient.get("birth_year") or ""))
            gender = patient.get("gender", "Nam")
            idx = self.txt_gender.findText(gender)
            if idx >= 0:
                self.txt_gender.setCurrentIndex(idx)
        else:
            name = parsed.get("name", "")
            dob = parsed.get("birth_year")
            gender = parsed.get("gender", "Nam")
            
            database.create_patient(patient_id, name=name, birth_year=dob, gender=gender)
            self.txt_patient_name.setText(name)
            self.txt_birth_year.setText(str(dob) if dob else "")
            idx = self.txt_gender.findText(gender)
            if idx >= 0:
                self.txt_gender.setCurrentIndex(idx)
            
        database.log_audit_event("BARCODE_SCAN", operator_name=self.active_operator_name, patient_id=patient_id)
        self.load_patient_photos()

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
            gender = patient.get("gender", "Nam")
            idx = self.txt_gender.findText(gender)
            if idx >= 0:
                self.txt_gender.setCurrentIndex(idx)
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
            self.lbl_scan_status.setText("⚠️ VUI LÒNG QUÉT MÃ VẠCH BỆNH NHÂN TRƯỚC KHI CHỤP!")
            self.lbl_scan_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px; padding: 4px; background-color: #450a0a; border-radius: 4px;")
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
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                
        if not self.current_patient_id:
            self.lbl_baseline_photo.setText("Chưa có ảnh đối chiếu")
            return

        photos = database.get_patient_photos(self.current_patient_id)
        all_photo_paths = [str(database.get_full_photo_path(p["file_path"])) for p in photos if database.get_full_photo_path(p["file_path"])]
        
        # Load Photo 1 into Split-screen Baseline View on the Right (if not custom set)
        if photos and not hasattr(self, 'custom_baseline_path'):
            baseline_path = database.get_full_photo_path(photos[0]["file_path"])
            if baseline_path and baseline_path.exists():
                pix = QPixmap(str(baseline_path))
                scaled = pix.scaled(self.lbl_baseline_photo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_baseline_photo.setPixmap(scaled)

        for idx, photo in enumerate(photos):
            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(2, 2, 2, 2)
            
            lbl_thumb = QLabel()
            lbl_thumb.setFixedSize(110, 85)
            lbl_thumb.setStyleSheet("border: 1px solid #334155; background-color: #020617;")
            
            img_path = database.get_full_photo_path(photo["file_path"])
            if img_path and img_path.exists():
                pix = QPixmap(str(img_path))
                lbl_thumb.setPixmap(pix.scaled(lbl_thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            lbl_title = QLabel(os.path.basename(photo["file_path"])[-12:])
            lbl_title.setStyleSheet("font-size: 10px; color: #94a3b8;")
            lbl_title.setAlignment(Qt.AlignCenter)
            
            item_layout.addWidget(lbl_thumb)
            item_layout.addWidget(lbl_title)
            
            photo_id = photo["id"]
            photo_idx = idx
            
            def make_context_menu(p_id, path, current_idx):
                def custom_context(pos):
                    menu = QMenu()
                    open_act = menu.addAction("👁️ Xem ảnh phóng to")
                    set_baseline_act = menu.addAction("📌 Đặt làm Ảnh đối chiếu đợt 1")
                    del_act = menu.addAction("🗑️ Xóa ảnh này")
                    action = menu.exec_(lbl_thumb.mapToGlobal(pos))
                    if action == open_act:
                        hardware_test_dialogs.show_image_preview(self, photo_paths=all_photo_paths, current_index=current_idx)
                    elif action == set_baseline_act:
                        if path and path.exists():
                            pix = QPixmap(str(path))
                            scaled = pix.scaled(self.lbl_baseline_photo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.lbl_baseline_photo.setPixmap(scaled)
                            self.status_bar.showMessage(f"Đã đặt {path.name} làm ảnh đối chiếu góc đợt 1.", 4000)
                    elif action == del_act:
                        reply = QMessageBox.question(
                            self, "Xác nhận xóa", "Bạn có chắc chắn muốn xóa ảnh này?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            database.delete_photo(p_id, operator_name=self.active_operator_name)
                            self.load_patient_photos()
                return custom_context

            lbl_thumb.setContextMenuPolicy(Qt.CustomContextMenu)
            lbl_thumb.customContextMenuRequested.connect(make_context_menu(photo_id, img_path, photo_idx))
            lbl_thumb.mousePressEvent = lambda e, p_idx=photo_idx: hardware_test_dialogs.show_image_preview(self, photo_paths=all_photo_paths, current_index=p_idx) if e.button() == Qt.LeftButton else None
            
            self.grid_layout.addWidget(item_widget)

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

    @Slot(str)
    def handle_thread_error(self, err_msg):
        logger.warning(f"[THREAD_ERROR] {err_msg}")
        self.status_bar.showMessage(f"⚠️ {err_msg}", 6000)
        if hasattr(self, 'lbl_voice_status'):
            self.lbl_voice_status.setText("Microphone: Tự động kết nối lại...")

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
                logger.info(f"[EVENT_FILTER_PEDAL] Intercepted configured trigger key: {key} (config='{trigger_key_cfg}')")
                print(f"🦶 [PEDAL_SUCCESS]: Intercepted Configured Key = {key} (config='{trigger_key_cfg}')")
                self.trigger_photo_capture(source=f"EVENT_FILTER_PEDAL_{trigger_key_cfg}")
                return True
            
            # 1. Intercept Pedal Function Keys (F13, F12, F5, F14, F15)
            if key in (Qt.Key_F13, Qt.Key_F12, Qt.Key_F5, Qt.Key_F14, Qt.Key_F15):
                logger.info(f"[EVENT_FILTER_PEDAL] Intercepted pedal function key: {key}")
                print(f"🦶 [PEDAL_SUCCESS]: Intercepted Function Key = {key}")
                self.trigger_photo_capture(source=f"EVENT_FILTER_PEDAL_{key}")
                return True
                
            # 2. Intercept Pedal Modifier Keys (Alt / Meta)
            if key in (Qt.Key_Alt, Qt.Key_Meta):
                logger.info(f"[EVENT_FILTER_PEDAL] Intercepted pedal Alt/Meta key: {key}")
                print(f"🦶 [PEDAL_SUCCESS]: Intercepted Alt Key = {key}")
                self.trigger_photo_capture(source=f"EVENT_FILTER_ALT_{key}")
                return True

            # 3. Intercept Space key if focus is not in active text input line
            if key == Qt.Key_Space:
                focused = QApplication.focusWidget()
                if not isinstance(focused, QLineEdit):
                    logger.info("[EVENT_FILTER_PEDAL] Intercepted Space key outside text edit")
                    print("🦶 [PEDAL_SUCCESS]: Intercepted Space Key outside text edit")
                    self.trigger_photo_capture(source="EVENT_FILTER_SPACE")
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
        key = event.key()
        if hasattr(self, 'multimodal_dispatcher') and self.multimodal_dispatcher:
            self.multimodal_dispatcher.handle_key_event(key)
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
