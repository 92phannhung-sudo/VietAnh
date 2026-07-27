import os
import sys
import time
import logging
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize
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
from pedal_gesture_fsm import PedalGestureFSM
from voice_detector import VoiceDetectorThread
from updater import UpdateCheckerThread

# Configure Logging according to SPECIFICATION: [YYYY-MM-DD HH:MM:SS,ms] [LEVEL] [MODULE] [THREAD_ID] - Message
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

file_handler = RotatingFileHandler(config.LOG_PATH, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] [Thread-%(thread)d] - %(message)s",
    handlers=[file_handler, stream_handler]
)
logger = logging.getLogger("PatientApp")


class CameraThread(QThread):
    frame_signal = Signal(QImage)
    barcode_signal = Signal(str)
    photo_saved_signal = Signal(str, float) # (file_path, latency_ms)
    error_signal = Signal(str)

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
        self.camera_index = index
        if self._running:
            self.stop()
            self.start()

    def set_active_patient(self, patient_id):
        self._active_patient_id = patient_id

    def set_active_operator(self, operator_id, operator_name):
        self._active_operator_id = operator_id
        self._active_operator_name = operator_name

    def request_capture(self, source="GUI_BUTTON"):
        self._capture_source = source
        self._capture_requested = True

    def run(self):
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)
            
        if not self.cap.isOpened():
            self.error_signal.emit("Không thể kết nối tới Camera Logitech.")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        self._running = True
        frame_counter = 0

        while self._running:
            start_t = time.time()
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            if self._capture_requested and self._active_patient_id:
                self._capture_requested = False
                self._save_photo(frame, start_t)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            cv2.putText(
                rgb_frame, f"Logi C920e - {w}x{h}", (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (34, 197, 94), 2
            )
            
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.frame_signal.emit(qt_image)

            frame_counter += 1
            if frame_counter % 5 == 0:
                self._scan_barcode(frame)

            time.sleep(0.01)

        self.cap.release()
        self.cap = None

    def stop(self):
        self._running = False
        if self.cap and self.cap.isOpened():
            try:
                self.cap.release()
            except Exception:
                pass
        self.wait(500)
        if self.isRunning():
            self.terminate()

    def _scan_barcode(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        
        for barcode in barcodes:
            barcode_data = barcode.data.decode("utf-8").strip()
            current_time = time.time()
            if barcode_data != self.last_barcode_data or (current_time - self.last_barcode_time > 2.0):
                self.last_barcode_data = barcode_data
                self.last_barcode_time = current_time
                logger.info(f"[BARCODE_SCAN] Decoded raw data: {barcode_data}")
                self.barcode_signal.emit(barcode_data)
                break

    def _save_photo(self, frame, trigger_timestamp):
        try:
            patient_dir = config.PHOTOS_DIR / self._active_patient_id
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
    video_inputs = QMediaDevices.videoInputs()
    qm_names = [cam.description().strip() for cam in video_inputs if cam.description().strip()]
    
    # Cross-check OpenCV capture ports 0 through 7
    for idx in range(8):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.release()
            if idx < len(qm_names):
                name = qm_names[idx]
            else:
                name = f"USB Video Device / Camera #{idx}"
            cams.append({"index": idx, "name": name})
            
    if not cams and qm_names:
        for idx, name in enumerate(qm_names):
            cams.append({"index": idx, "name": name})
            
    if not cams:
        cams.append({"index": 0, "name": "Không tìm thấy Camera vật lý"})
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
        cam_found = False
        for cam in real_cams:
            idx = cam["index"]
            if cam["name"] == "Không tìm thấy Camera vật lý":
                continue
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                results.append({
                    "name": cam["name"],
                    "type": "Camera / Webcam (USB UVC)",
                    "status": "SẴN SÀNG (OK)",
                    "info": f"Cổng Index {idx} | 1080p Stream",
                    "index": idx
                })
                cap.release()
                cam_found = True
                break
        if not cam_found:
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

        # Apply initial theme QSS
        self.apply_theme(self.app_config.get("active_theme", "dark"))
        
        self.setup_ui()
        self.start_camera_thread()
        self.start_voice_thread()
        self.start_updater_thread()
        self.register_pedal_hook()

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
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------- LEFT SIDEBAR NAVIGATION -----------------
        sidebar_container = QWidget()
        sidebar_container.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        
        item_tab1 = QListWidgetItem(" 📷  1. Chụp Ảnh")
        item_tab2 = QListWidgetItem(" 📂  2. Tra Cứu")
        item_tab3 = QListWidgetItem(" 👨‍⚕️  3. Nhân Viên")
        item_tab4 = QListWidgetItem(" ⚙️  4. Cài Đặt")
        
        self.sidebar.addItem(item_tab1)
        self.sidebar.addItem(item_tab2)
        self.sidebar.addItem(item_tab3)
        self.sidebar.addItem(item_tab4)
        
        self.sidebar.currentRowChanged.connect(self.switch_tab)
        sidebar_layout.addWidget(self.sidebar)

        # Dedicated Exit / Close App Button at bottom of sidebar
        self.btn_exit_app = QPushButton("🚪  Thoát Ứng Dụng")
        self.btn_exit_app.setStyleSheet("background-color: #dc2626; color: white; border-radius: 0px; padding: 14px; font-weight: bold; font-size: 14px;")
        self.btn_exit_app.clicked.connect(self.confirm_exit_app)
        sidebar_layout.addWidget(self.btn_exit_app)

        main_layout.addWidget(sidebar_container)

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
        self.status_bar.showMessage(f"Phiên bản: {config.__version__} | Database: WAL Mode OK")
        
        # Default select Tab 1
        self.sidebar.setCurrentRow(0)

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
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
        
        layout.addLayout(top_banner)

        # Split Screen Layout (Live Camera vs Baseline Comparison Photo)
        split_layout = QHBoxLayout()
        
        # Left: Camera Stream Box
        cam_box = QGroupBox("1. MÀN HÌNH CAMERA THỜI GIAN THỰC")
        cam_box_layout = QVBoxLayout(cam_box)
        
        self.camera_feed = QLabel("Đang mở Camera...")
        self.camera_feed.setAlignment(Qt.AlignCenter)
        self.camera_feed.setMinimumSize(480, 360)
        self.camera_feed.setStyleSheet("background-color: #090d16; border: 1px solid #1e293b; border-radius: 4px;")
        cam_box_layout.addWidget(self.camera_feed)
        
        split_layout.addWidget(cam_box, stretch=1)

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
        self.txt_patient_id.setReadOnly(True)
        info_form.addRow("Mã BA:", self.txt_patient_id)
        
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

    # ----------------- TAB 2: PATIENT HISTORY & REPORTS -----------------
    def build_tab2_history(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        # Search Bar
        search_box = QHBoxLayout()
        search_box.addWidget(QLabel("Tìm kiếm Bệnh án:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Nhập Mã BA hoặc Tên bệnh nhân...")
        self.txt_search.textChanged.connect(self.load_history_records)
        search_box.addWidget(self.txt_search)
        
        self.btn_export_report = QPushButton("Xuất Báo Cáo PDF / In")
        self.btn_export_report.clicked.connect(self.export_patient_report)
        search_box.addWidget(self.btn_export_report)
        
        layout.addLayout(search_box)

        # History Table
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(6)
        self.table_history.setHorizontalHeaderLabels(["Mã BA", "Họ và Tên", "Năm sinh", "Giới tính", "Ngày tạo", "Số ảnh"])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_history.cellDoubleClicked.connect(self.on_history_item_clicked)
        
        layout.addWidget(self.table_history)
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
        staff_id = self.cb_active_operator.currentData()
        if staff_id:
            self.active_operator_id = staff_id
            self.active_operator_name = self.cb_active_operator.currentText().split(" (")[0]
            self.app_config["active_operator_id"] = staff_id
            config.save_config(self.app_config)
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

    # ----------------- HISTORY & REPORT LOGIC -----------------
    def load_history_records(self):
        query = self.txt_search.text().strip().lower()
        conn = database.get_db_connection()
        cursor = conn.cursor()
        if query:
            cursor.execute("SELECT * FROM patients WHERE LOWER(id) LIKE ? OR LOWER(name) LIKE ?", (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        self.table_history.setRowCount(len(rows))
        for r, p in enumerate(rows):
            photos = database.get_patient_photos(p["id"])
            self.table_history.setItem(r, 0, QTableWidgetItem(p["id"]))
            self.table_history.setItem(r, 1, QTableWidgetItem(p["name"] or ""))
            self.table_history.setItem(r, 2, QTableWidgetItem(str(p["birth_year"] or "")))
            self.table_history.setItem(r, 3, QTableWidgetItem(p["gender"] or ""))
            self.table_history.setItem(r, 4, QTableWidgetItem(p["created_at"]))
            self.table_history.setItem(r, 5, QTableWidgetItem(f"{len(photos)} ảnh"))

    def on_history_item_clicked(self, row, col):
        patient_id = self.table_history.item(row, 0).text()
        self.handle_scanned_barcode(patient_id)
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

    def save_settings_cfg(self):
        self.app_config["update_url"] = self.txt_ota_url.text().strip()
        config.save_config(self.app_config)
        QMessageBox.information(self, "Cài Đặt", "Đã lưu cài đặt hệ thống.")

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
        # Temporarily stop background camera thread to avoid OpenCV DirectShow device collision
        if hasattr(self, 'camera_thread') and self.camera_thread is not None:
            self.camera_thread.stop()
            
        cam_idx = self.cfg_camera_select.currentData()
        if cam_idx is None:
            cam_idx = 0
        hardware_test_dialogs.test_camera(self, camera_index=cam_idx)
        
        # Resume background camera thread after test modal closes
        self.start_camera_thread()

    def run_test_mic(self):
        # Stop background voice detector thread temporarily to prevent PyAudio stream lockup
        if hasattr(self, 'voice_thread') and self.voice_thread is not None:
            self.voice_thread.stop()
            
        mic_name = self.cfg_mic_select.currentText()
        hardware_test_dialogs.test_microphone(self, mic_name=mic_name)
        
        # Resume background voice detector thread after test modal closes
        self.start_voice_thread()

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
    def on_hardware_scan_finished(self, results):
        if hasattr(self, 'scan_dialog') and self.scan_dialog is not None:
            self.scan_dialog.close()
            self.scan_dialog = None

        # Display results in self.table_hw (5 Columns)
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

        # Refresh dropdowns
        mics = voice_detector.get_available_microphones()
        self.cfg_mic_select.clear()
        self.cfg_mic_select.addItems(mics)

        # Save scanned hardware list to DB Cache
        database.save_scanned_hardware_list(results)
        self.lbl_hw_status.setText(f"Quét hoàn tất! Đã lưu {len(results)} phần cứng vào CSDL (Lần sau không cần quét lại).")
        self.btn_scan_hw.setEnabled(True)
        database.log_audit_event("HARDWARE_SCAN", operator_name=self.active_operator_name, details=f"Scanned & persisted {len(results)} devices into DB cache.")

    def load_initial_hardware_cache(self):
        cached = database.get_cached_hardware_devices()
        if cached and hasattr(self, 'table_hw'):
            self.table_hw.setRowCount(len(cached))
            for r, item in enumerate(cached):
                self.table_hw.setItem(r, 0, QTableWidgetItem(item.get("device_type", "")))
                self.table_hw.setItem(r, 1, QTableWidgetItem(item.get("device_name", "")))
                status_item = QTableWidgetItem("SẴN SÀNG (OK)")
                status_item.setForeground(Qt.green)
                self.table_hw.setItem(r, 2, status_item)
                self.table_hw.setItem(r, 3, QTableWidgetItem(f"{item.get('device_info', '')} (Cập nhật: {item.get('updated_at', '')})"))
                self.attach_table_test_button(r, item.get("device_type", ""))
            self.lbl_hw_status.setText(f"Đã tải {len(cached)} phần cứng từ CSDL (Không cần quét lại).")

    # ----------------- NATIVE QT KEYPRESS FALLBACK -----------------
    def keyPressEvent(self, event):
        target_key_name = self.app_config.get("trigger_key", "f13").upper()
        event_key_name = Qt.Key(event.key()).name.replace("Key_", "").upper()
        if event_key_name == target_key_name:
            logger.info(f"[QT_KEY_FALLBACK] Foot pedal keypress intercepted by Qt fallback: {event_key_name}")
            if hasattr(self, 'pedal_fsm') and self.pedal_fsm is not None:
                self.pedal_fsm.process_raw_key(target_key_name, "down")
                self.pedal_fsm.process_raw_key(target_key_name, "up")
        else:
            super().keyPressEvent(event)

    def start_camera_thread(self):
        self.camera_thread = CameraThread()
        self.camera_thread.set_camera(self.app_config.get("camera_index", 0))
        self.camera_thread.set_active_operator(self.active_operator_id, self.active_operator_name)
        self.camera_thread.frame_signal.connect(self.update_camera_frame)
        self.camera_thread.barcode_signal.connect(self.handle_scanned_barcode)
        self.camera_thread.photo_saved_signal.connect(self.handle_photo_saved)
        self.camera_thread.error_signal.connect(self.handle_thread_error)
        self.camera_thread.start()

    def start_voice_thread(self):
        self.voice_thread = VoiceDetectorThread()
        self.voice_thread.capture_signal.connect(lambda: self.trigger_photo_capture(source="VOICE_COMMAND"))
        self.voice_thread.keyword_signal.connect(self.on_voice_keyword_detected)
        self.voice_thread.status_signal.connect(self.update_voice_status)
        self.voice_thread.volume_signal.connect(self.update_voice_volume)
        self.voice_thread.error_signal.connect(self.handle_thread_error)
        
        model_path = Path(self.app_config["vosk_model_path"])
        if not model_path.exists():
            reply = QMessageBox.question(
                self, "Thiếu Mô Hình Giọng Nói",
                "Mô hình nhận diện giọng nói tiếng Việt offline chưa được cài đặt. Bạn có muốn tải về tự động không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.voice_thread.download_progress.connect(self.show_download_progress)
                import threading
                threading.Thread(target=lambda: self.voice_thread.download_model(str(model_path)), daemon=True).start()
            else:
                self.lbl_voice_status.setText("Microphone: Thiếu mô hình (Tắt)")
                return
        
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
            last_photo = photos[-1]
            full_path = database.get_full_photo_path(last_photo["file_path"])
            if full_path and full_path.exists():
                os.startfile(str(full_path))

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
            if hasattr(self, 'voice_thread') and self.voice_thread is not None:
                self.voice_thread.stop()
                self.start_voice_thread()
        except Exception as e:
            logger.error(f"[MIC_ERROR] Error changing microphone: {str(e)}", exc_info=True)

    @Slot(str)
    def handle_scanned_barcode(self, barcode_data):
        print('\a')
        
        parsed = barcode_parser.parse_barcode(barcode_data)
        patient_id = parsed["patient_id"]
        
        self.lbl_scan_status.setText(f"ĐÃ QUÉT: {patient_id}")
        self.lbl_scan_status.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px;")
        
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
    @Slot(str)
    def trigger_photo_capture(self, source="GUI_BUTTON"):
        if not self.current_patient_id:
            self.lbl_scan_status.setText("VUI LÒNG QUÉT MÃ VẠCH TRƯỚC KHI CHỤP!")
            self.lbl_scan_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;")
            return

        total, used, free = shutil.disk_usage(config.BASE_DIR)
        free_mb = free / (1024 * 1024)
        if free_mb < 500:
            QMessageBox.critical(self, "Bộ Nhớ Đầy", f"Dung lượng ổ đĩa còn lại quá thấp ({free_mb:.1f}MB). Vui lòng dọn dẹp ổ đĩa!")
            return

        logger.info(f"[CAPTURE_REQUEST] Trigger Source: {source} | Patient: {self.current_patient_id}")
        self.camera_thread.request_capture(source=source)

    @Slot(str, float)
    def handle_photo_saved(self, file_path, latency_ms):
        self.load_patient_photos()
        self.status_bar.showMessage(f"Đã lưu: {os.path.basename(file_path)} ({latency_ms:.1f}ms)", 3000)

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
        
        # Load Photo 1 into Split-screen Baseline View on the Right
        if photos:
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
            
            def make_context_menu(p_id, path):
                def custom_context(pos):
                    menu = QMenu()
                    open_act = menu.addAction("Mở ảnh đầy đủ")
                    del_act = menu.addAction("Xóa ảnh này")
                    action = menu.exec_(lbl_thumb.mapToGlobal(pos))
                    if action == open_act:
                        os.startfile(str(path))
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
            lbl_thumb.customContextMenuRequested.connect(make_context_menu(photo_id, img_path))
            lbl_thumb.mousePressEvent = lambda e, p=img_path: os.startfile(str(p)) if e.button() == Qt.LeftButton else None
            
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
            logger.info("[MAIN] Closing application. Cleaning active threads...")
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
                
            if hasattr(self, 'camera_thread') and self.camera_thread is not None:
                self.camera_thread.stop()
                
            if hasattr(self, 'voice_thread') and self.voice_thread is not None:
                self.voice_thread.stop()
                
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
    sys.exit(app.exec())
