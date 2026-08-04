from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from src.patient_search_service import PatientSearchService
from src.ui_patient_grid import PatientGridDialog
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType

class ClinicalCockpitWidget(QWidget):
    start_session_requested = Signal()
    complete_session_requested = Signal()
    capture_requested = Signal()
    delete_last_requested = Signal()

    def __init__(self, search_service: PatientSearchService, dispatcher: MultiModalDispatcher, parent=None):
        super().__init__(parent)
        self.search_service = search_service
        self.dispatcher = dispatcher
        self.active_patient = None
        self.captured_photos = []
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ---------------- 1. Standby Patient Banner & Validation Bar ----------------
        self.banner = QFrame()
        self.banner.setFrameShape(QFrame.StyledPanel)
        self.banner.setStyleSheet("background-color: #0f172a; border-radius: 8px; padding: 6px;")
        
        banner_layout = QHBoxLayout(self.banner)
        
        lbl_prefix = QLabel("📋 Bệnh Nhân:")
        lbl_prefix.setStyleSheet("color: #38bdf8; font-weight: bold;")
        banner_layout.addWidget(lbl_prefix)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("Mã hồ sơ/phiếu *")
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Họ và tên *")
        self.input_birth = QLineEdit()
        self.input_birth.setPlaceholderText("Năm sinh *")
        self.input_gender = QLineEdit()
        self.input_gender.setPlaceholderText("Nam/Nữ *")

        for inp in (self.input_id, self.input_name, self.input_birth, self.input_gender):
            inp.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 6px; border-radius: 4px;")
            inp.textChanged.connect(self.validate_inputs)
            banner_layout.addWidget(inp)

        self.btn_search = QPushButton("🔍 F5 Tìm hồ sơ")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_search.clicked.connect(self.open_search_grid)
        banner_layout.addWidget(self.btn_search)

        self.btn_start = QPushButton("🚀 F1 Bắt đầu phiên")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet("""
            QPushButton { background-color: #15803d; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_start.clicked.connect(self.on_start_session)
        banner_layout.addWidget(self.btn_start)

        main_layout.addWidget(self.banner)

        # ---------------- 2. Main Center Widescreen Camera (100% Width - No Baseline) ----------------
        self.camera_panel = QFrame()
        cam_layout = QVBoxLayout(self.camera_panel)
        self.camera_label = QLabel("📷 WEBCAM LOGITECH C920e (1080p LIVE STREAM - MÀN HÌNH RỘNG 100%)\n\n[1 Giậm Bàn Đạp / Nói 'Chụp ảnh' / Space -> Lưu ngầm <150ms]\n[Giậm Giữ Bàn Đạp (Long Press) / Nói 'Xóa ảnh' -> Đưa vào Thùng Rác Tạm]")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #020617; border: 2px dashed #38bdf8; border-radius: 8px; color: #38bdf8; font-weight: bold; font-size: 14px;")
        cam_layout.addWidget(self.camera_label)
        main_layout.addWidget(self.camera_panel, stretch=7)

        # ---------------- 3. Bottom Panel (Filmstrip Carousel & Actions) ----------------
        bottom_panel = QFrame()
        bottom_panel.setStyleSheet("background-color: #0f172a; border-radius: 8px; padding: 6px;")
        bottom_layout = QHBoxLayout(bottom_panel)

        lbl_filmstrip = QLabel("Filmstrip Ảnh Ca Khám:")
        lbl_filmstrip.setStyleSheet("color: #94a3b8; font-size: 11px;")
        bottom_layout.addWidget(lbl_filmstrip)

        scroll_area = QScrollArea()
        scroll_area.setFixedHeight(85)
        scroll_area.setWidgetResizable(True)
        self.filmstrip_widget = QWidget()
        self.filmstrip_layout = QHBoxLayout(self.filmstrip_widget)
        self.filmstrip_layout.setContentsMargins(4, 4, 4, 4)
        scroll_area.setWidget(self.filmstrip_widget)
        bottom_layout.addWidget(scroll_area, stretch=8)

        self.btn_complete = QPushButton("✅ F2 Hoàn thành & Lưu CSDL")
        self.btn_complete.setCursor(Qt.PointingHandCursor)
        self.btn_complete.setStyleSheet("background-color: #0369a1; color: white; font-weight: bold; padding: 10px 16px; border-radius: 6px;")
        self.btn_complete.clicked.connect(self.on_complete_session)
        bottom_layout.addWidget(self.btn_complete, stretch=2)

        main_layout.addWidget(bottom_panel, stretch=2)

    def validate_inputs(self):
        valid = (
            bool(self.input_id.text().strip()) and
            bool(self.input_name.text().strip()) and
            bool(self.input_birth.text().strip()) and
            bool(self.input_gender.text().strip())
        )
        self.btn_start.setEnabled(valid)
        border_color = "#22c55e" if valid else "#ef4444"
        self.banner.setStyleSheet(f"background-color: #0f172a; border: 1.5px solid {border_color}; border-radius: 8px; padding: 6px;")

    def open_search_grid(self):
        dialog = PatientGridDialog(self.search_service, self)
        dialog.patient_selected.connect(self.load_patient)
        dialog.exec()

    def load_patient(self, patient_data: dict):
        self.active_patient = patient_data
        self.input_id.setText(patient_data.get("patient_id", ""))
        self.input_name.setText(patient_data.get("full_name", ""))
        self.input_birth.setText(patient_data.get("birth_year", ""))
        self.input_gender.setText(patient_data.get("gender", ""))
        self.validate_inputs()

    def on_start_session(self):
        self.start_session_requested.emit()

    def on_complete_session(self):
        self.complete_session_requested.emit()
        self.reset_session()

    def reset_session(self):
        self.active_patient = None
        self.input_id.clear()
        self.input_name.clear()
        self.input_birth.clear()
        self.input_gender.clear()
        for i in reversed(range(self.filmstrip_layout.count())):
            w = self.filmstrip_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.validate_inputs()

    def connect_signals(self):
        self.dispatcher.action_triggered.connect(self.on_action_triggered)

    def on_action_triggered(self, action: ActionType):
        if action == ActionType.START_SESSION and self.btn_start.isEnabled():
            self.on_start_session()
        elif action == ActionType.SEARCH_GRID:
            self.open_search_grid()
        elif action == ActionType.COMPLETE_SESSION:
            self.on_complete_session()
        elif action == ActionType.CAPTURE:
            self.capture_requested.emit()
        elif action == ActionType.DELETE_LAST:
            self.delete_last_requested.emit()
