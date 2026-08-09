from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal
from src.patient_search_service import PatientSearchService
from src.multimodal_dispatcher import MultiModalDispatcher, ActionType
from src.patient_session_controller import Field, Phase
from src.ui_gender_combo import make_gender_combo, set_gender_combo, gender_combo_value

from PySide6.QtGui import QPixmap

class ClinicalCockpitWidget(QWidget):
    start_session_requested = Signal()
    begin_capture_requested = Signal()
    complete_session_requested = Signal()
    capture_requested = Signal()
    delete_last_requested = Signal()
    delete_all_requested = Signal()
    patient_loaded = Signal(dict)

    def __init__(self, search_service: PatientSearchService, dispatcher: MultiModalDispatcher, parent=None):
        super().__init__(parent)
        self.search_service = search_service
        self.dispatcher = dispatcher
        self.active_patient = None
        self.captured_photos = []
        self.is_session_open = False
        self._camera_hw_error = None  # str | None — last camera hardware failure
        self._last_phase = None
        self.setup_ui()
        self.connect_signals()
        self.update_session_ui_state(False)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ---------------- 1. Standby Patient Banner & Validation Bar ----------------
        self.banner = QFrame()
        self.banner.setFrameShape(QFrame.StyledPanel)
        self.banner.setStyleSheet("background-color: #0f172a; border-radius: 8px; padding: 6px;")
        
        banner_vlayout = QVBoxLayout(self.banner)
        banner_vlayout.setContentsMargins(6, 6, 6, 6)
        banner_vlayout.setSpacing(6)

        # Top line: Status Badge Indicator
        self.lbl_status_badge = QLabel("⚪ TRẠNG THÁI CHỜ: Quét mã QR hoặc nhập Mã BN để bắt đầu ca khám")
        self.lbl_status_badge.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #1e293b; border-radius: 4px;")
        banner_vlayout.addWidget(self.lbl_status_badge)

        # Bottom line: Inputs & Action Buttons
        banner_layout = QHBoxLayout()
        
        lbl_prefix = QLabel("📋 Bệnh Nhân:")
        lbl_prefix.setStyleSheet("color: #38bdf8; font-weight: bold;")
        banner_layout.addWidget(lbl_prefix)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("Mã hồ sơ/phiếu *")
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Họ và tên *")
        self.input_birth = QLineEdit()
        self.input_birth.setPlaceholderText("Năm sinh *")
        self.input_gender = make_gender_combo()

        for inp in (self.input_id, self.input_name, self.input_birth):
            inp.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 6px; border-radius: 4px;")
            banner_layout.addWidget(inp)
        banner_layout.addWidget(self.input_gender)

        self.btn_search = QPushButton("🔍 F5 Thư mục")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setToolTip("F5 — mở Tab Thư Mục Bệnh Án để tìm / chọn hồ sơ")
        self.btn_search.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        # Click wiring: MainWindow disconnects and routes through Hotkey("F5")
        banner_layout.addWidget(self.btn_search)

        self.btn_start = QPushButton("🚀 F1 Mở phiên")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setEnabled(True)
        self.btn_start.setStyleSheet("""
            QPushButton { background-color: #15803d; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #16a34a; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_start.clicked.connect(self.on_start_session)
        banner_layout.addWidget(self.btn_start)

        self.btn_begin_capture = QPushButton("F2 · Bắt đầu chụp (khóa hồ sơ)")
        self.btn_begin_capture.setCursor(Qt.PointingHandCursor)
        self.btn_begin_capture.setEnabled(False)
        self.btn_begin_capture.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #3b82f6; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_begin_capture.clicked.connect(self.begin_capture_requested.emit)
        banner_layout.addWidget(self.btn_begin_capture)

        banner_vlayout.addLayout(banner_layout)
        main_layout.addWidget(self.banner)

        # ---------------- 2. Main Center Split (100% Widescreen Default | Dynamic 60/40 Split when Baseline Photo Exists) ----------------
        self.center_split = QHBoxLayout()

        # Left Panel (Camera Stream - 100% Widescreen by default, 60% when Baseline visible)
        self.camera_panel = QFrame()
        cam_layout = QVBoxLayout(self.camera_panel)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_label = QLabel("📷 WEBCAM LOGITECH C920e (1080p LIVE STREAM)\n\n[1 Giậm Bàn Đạp / Nói 'Chụp ảnh' / Space -> Lưu ngầm <150ms]\n[Giậm Giữ Bàn Đạp (Long Press) / Nói 'Xóa ảnh' -> Đưa vào Thùng Rác Tạm]")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.camera_label.setMinimumSize(1, 1)
        self.camera_label.setStyleSheet("background-color: #020617; border: 2px dashed #38bdf8; border-radius: 8px; color: #38bdf8; font-weight: bold; font-size: 13px;")
        cam_layout.addWidget(self.camera_label)
        self.center_split.addWidget(self.camera_panel, stretch=6)

        # Right Panel (Baseline Photo Comparison 40% - Hidden by default until baseline photo exists)
        self.baseline_panel = QFrame()
        base_layout = QVBoxLayout(self.baseline_panel)
        base_layout.setContentsMargins(0, 0, 0, 0)
        self.baseline_title = QLabel("🔍 Ảnh Baseline (Khám trước)")
        self.baseline_title.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 13px;")
        base_layout.addWidget(self.baseline_title)

        self.baseline_label = QLabel("[Chưa chọn Bệnh nhân / Chưa có ảnh Baseline]")
        self.baseline_label.setAlignment(Qt.AlignCenter)
        self.baseline_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.baseline_label.setMinimumSize(1, 1)
        self.baseline_label.setStyleSheet("background-color: #1e293b; border-radius: 8px; color: #64748b;")
        base_layout.addWidget(self.baseline_label)
        self.center_split.addWidget(self.baseline_panel, stretch=4)
        
        # Hide baseline panel by default for 100% widescreen camera view on new patients
        self.baseline_panel.setVisible(False)

        main_layout.addLayout(self.center_split, stretch=7)

        # ---------------- 3. Bottom Panel (Filmstrip Carousel & Actions) ----------------
        bottom_panel = QFrame()
        bottom_panel.setStyleSheet("background-color: #0f172a; border-radius: 8px; padding: 6px;")
        bottom_layout = QHBoxLayout(bottom_panel)

        self.lbl_filmstrip = QLabel("Filmstrip Ảnh Ca Khám:")
        self.lbl_filmstrip.setStyleSheet("color: #94a3b8; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_filmstrip)

        scroll_area = QScrollArea()
        scroll_area.setFixedHeight(85)
        scroll_area.setWidgetResizable(True)
        self.filmstrip_widget = QWidget()
        self.filmstrip_layout = QHBoxLayout(self.filmstrip_widget)
        self.filmstrip_layout.setContentsMargins(4, 4, 4, 4)
        self.filmstrip_layout.setAlignment(Qt.AlignLeft)
        scroll_area.setWidget(self.filmstrip_widget)
        bottom_layout.addWidget(scroll_area, stretch=8)

        self.btn_complete = QPushButton("F4 · Kết thúc phiên (tắt thiết bị)")
        self.btn_complete.setCursor(Qt.PointingHandCursor)
        self.btn_complete.setStyleSheet(
            "background-color: #b45309; color: white; font-weight: bold; padding: 10px 16px; border-radius: 6px;"
        )
        self.btn_complete.clicked.connect(self.on_complete_session)
        bottom_layout.addWidget(self.btn_complete, stretch=2)

        main_layout.addWidget(bottom_panel, stretch=2)

    def update_session_ui_state(self, is_open: bool):
        self.is_session_open = is_open
        for inp in (self.input_id, self.input_name, self.input_birth, self.input_gender):
            inp.setEnabled(is_open)
        self.btn_search.setEnabled(True)  # Standby OK — browse old records without F1
        self.btn_complete.setEnabled(is_open)
        
        if is_open:
            self.btn_start.setText("🏁 F1 Kết thúc phiên")
            self.btn_start.setStyleSheet("""
                QPushButton { background-color: #dc2626; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
                QPushButton:hover { background-color: #ef4444; }
            """)
            p_id = self.input_id.text().strip()
            p_name = self.input_name.text().strip()
            if p_id and p_name:
                self.lbl_status_badge.setText(f"🔴 ĐANG KHÁM: [{p_id}] - {p_name}")
                self.lbl_status_badge.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #0c4a6e; border: 1px solid #0284c7; border-radius: 4px;")
            else:
                self.lbl_status_badge.setText("🟢 ĐÃ MỞ PHIÊN KHÁM: Sẵn sàng quét mã QR hoặc nhập Mã BN để bắt đầu")
                self.lbl_status_badge.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #052e16; border: 1px solid #16a34a; border-radius: 4px;")
        else:
            self.btn_start.setText("🚀 F1 Mở phiên làm việc")
            self.btn_start.setStyleSheet("""
                QPushButton { background-color: #15803d; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
                QPushButton:hover { background-color: #16a34a; }
            """)
            self.lbl_status_badge.setText("⚪ PHIÊN ĐÃ KẾT THÚC (CHẾ ĐỘ CHỜ): Camera, Bàn đạp & Giọng nói đang TẮT. Nhấn F1 để MỞ PHIÊN KHÁM")
            self.lbl_status_badge.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #1e293b; border-radius: 4px;")
            self.camera_label.setPixmap(QPixmap())
            self.camera_label.setText("⏸️ HỆ THỐNG ĐANG Ở CHẾ ĐỘ CHỜ (KẾT THÚC PHIÊN)\n\n[Bàn đạp, Giọng nói và Camera tạm dừng]\n[BẤM F1 ĐỂ MỞ ĐẦU PHIÊN KHÁM MỚI]")

    def validate_inputs(self):
        """Legacy banner border hint only — badge/phase come from apply_session_view."""
        if not self.is_session_open:
            return
        p_id = self.input_id.text().strip()
        p_name = self.input_name.text().strip()
        if p_id and p_name:
            self.banner.setStyleSheet(
                "background-color: #0c4a6e; border: 1.5px solid #0284c7; border-radius: 8px; padding: 6px;"
            )
        else:
            self.banner.setStyleSheet(
                "background-color: #0f172a; border: 1.5px solid #334155; border-radius: 8px; padding: 6px;"
            )

    def open_search_grid(self):
        """Legacy multimodal hook — search is Tab 2 via MainWindow Hotkey F5."""
        return

    def load_patient(self, patient_data: dict):
        if not self.is_session_open:
            self.update_session_ui_state(True)
        self.active_patient = patient_data
        self.input_id.setText(patient_data.get("patient_id", ""))
        self.input_name.setText(patient_data.get("full_name", ""))
        self.input_birth.setText(patient_data.get("birth_year", ""))
        set_gender_combo(self.input_gender, patient_data.get("gender", ""))
        
        has_baseline = bool(patient_data.get("has_baseline", False))
        if has_baseline:
            self.baseline_label.setText(f"[Ảnh Baseline BN: {patient_data.get('patient_id')}]")
            self.baseline_panel.setVisible(True)
        else:
            self.baseline_panel.setVisible(False)
            
        self.validate_inputs()

    def load_patient_from_voice(self, patient_data: dict):
        """Auto fills input fields from spoken patient demographics.

        Supports two modes:
        - Partial update (_partial=True): Only overwrites the specific field(s)
          spoken (e.g. "Họ và tên ..." fills only the name field).
        - Full update: Fills all fields at once from a complete spoken sentence.
        """
        if not patient_data:
            return
        if not self.is_session_open:
            self.update_session_ui_state(True)

        is_partial = patient_data.get("_partial", False)

        if is_partial:
            # Single-field update: only set the field(s) present in the dict
            updated_fields = []
            if "full_name" in patient_data:
                self.input_name.setText(patient_data["full_name"])
                updated_fields.append(f"Tên: {patient_data['full_name']}")
            if "birth_year" in patient_data:
                self.input_birth.setText(patient_data["birth_year"])
                updated_fields.append(f"Năm sinh: {patient_data['birth_year']}")
            if "gender" in patient_data:
                set_gender_combo(self.input_gender, patient_data["gender"])
                updated_fields.append(f"Giới tính: {patient_data['gender']}")
            if "patient_id" in patient_data:
                self.input_id.setText(patient_data["patient_id"])
                updated_fields.append(f"Mã BN: {patient_data['patient_id']}")

            field_summary = " | ".join(updated_fields)
            self.lbl_status_badge.setText(f"🎙️ CẬP NHẬT GIỌNG NÓI: {field_summary}")
            self.lbl_status_badge.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #2e1065; border: 1px solid #7c3aed; border-radius: 4px;")
            self.validate_inputs()
        else:
            # Full-sentence voice update — fill only the fields voice provided
            # Patient ID is NEVER auto-generated by voice; it must come from keyboard/barcode.
            updated_fields = []
            if "full_name" in patient_data:
                self.input_name.setText(patient_data["full_name"])
                updated_fields.append(patient_data["full_name"])
            if "birth_year" in patient_data:
                self.input_birth.setText(patient_data["birth_year"])
                updated_fields.append(patient_data["birth_year"])
            if "gender" in patient_data:
                set_gender_combo(self.input_gender, patient_data["gender"])
                updated_fields.append(patient_data["gender"])
            if "patient_id" in patient_data:
                self.input_id.setText(patient_data["patient_id"])

            summary = " - ".join(updated_fields)
            self.lbl_status_badge.setText(f"🎙️ NẠP GIỌNG NÓI THÀNH CÔNG: {summary}")
            self.lbl_status_badge.setStyleSheet("color: #f472b6; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #831843; border: 1px solid #db2777; border-radius: 4px;")
            self.validate_inputs()

    def on_start_session(self):
        """F1 — session open/close is decided by PatientSessionController."""
        self.start_session_requested.emit()

    def on_complete_session(self):
        """F4 end session — controller owns clear; shell only emits."""
        self.complete_session_requested.emit()

    def apply_session_view(self, view) -> None:
        """Bind demography / phase / affordances from SessionView (Design A)."""
        from src.patient_session_controller import Phase, Field

        phase = view.phase
        is_open = phase != Phase.STANDBY
        aff = view.affordances
        demo = view.demography

        for inp in (self.input_id, self.input_name, self.input_birth, self.input_gender):
            inp.blockSignals(True)

        def _ui_text(val) -> str:
            if val is None:
                return ""
            s = str(val).strip()
            return "" if s.lower() == "none" else s

        self.input_id.setText(_ui_text(demo.patient_id))
        self.input_name.setText(_ui_text(demo.full_name))
        self.input_birth.setText("" if demo.birth_year is None else str(demo.birth_year))
        set_gender_combo(self.input_gender, _ui_text(demo.gender))

        editable = aff.editable
        self.input_id.setEnabled(is_open and Field.PATIENT_ID in editable)
        self.input_name.setEnabled(is_open and Field.FULL_NAME in editable)
        self.input_birth.setEnabled(is_open and Field.BIRTH_YEAR in editable)
        self.input_gender.setEnabled(is_open and Field.GENDER in editable)

        for inp in (self.input_id, self.input_name, self.input_birth, self.input_gender):
            inp.blockSignals(False)

        self.is_session_open = is_open
        self.btn_search.setEnabled(aff.can_open_search)
        self.btn_complete.setEnabled(aff.end_session)
        self.btn_begin_capture.setEnabled(aff.begin_capture)
        self.btn_begin_capture.setText("F2 · Bắt đầu chụp (khóa hồ sơ)")
        self.btn_complete.setText("F4 · Kết thúc phiên (tắt thiết bị)")

        # Tooltip for locked patient id (§12.5)
        if Field.PATIENT_ID not in editable and is_open:
            self.input_id.setToolTip("Đổi mã: F4 kết thúc phiên, rồi F1 và tìm lại")
        else:
            self.input_id.setToolTip("")

        if phase == Phase.STANDBY:
            self.btn_start.setText("🚀 F1 Mở phiên")
            self.btn_start.setStyleSheet("""
                QPushButton { background-color: #15803d; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
                QPushButton:hover { background-color: #16a34a; }
            """)
            self.lbl_status_badge.setText(
                "⚪ STANDBY — nhấn F1 để mở phiên (bật thiết bị)"
            )
            self.lbl_status_badge.setStyleSheet(
                "color: #94a3b8; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #1e293b; border-radius: 4px;"
            )
            self.active_patient = None
        elif phase == Phase.LOCKED_CAPTURE:
            self.btn_start.setText("🏁 F1 Đóng ca (Standby)")
            self.btn_start.setStyleSheet("""
                QPushButton { background-color: #dc2626; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
                QPushButton:hover { background-color: #ef4444; }
            """)
            pid = demo.patient_id or "?"
            pname = demo.full_name or ""
            self.lbl_status_badge.setText(f"🔒 Đang ghi ảnh cho: {pid} — {pname}")
            self.lbl_status_badge.setStyleSheet(
                "color: #fbbf24; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #78350f; border: 1px solid #f59e0b; border-radius: 4px;"
            )
        else:
            self.btn_start.setText("🏁 F1 Đóng ca (Standby)")
            self.btn_start.setStyleSheet("""
                QPushButton { background-color: #dc2626; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
                QPushButton:hover { background-color: #ef4444; }
            """)
            notice = view.notice
            if notice:
                self.lbl_status_badge.setText(f"⚠️ {notice}")
            elif aff.begin_capture:
                self.lbl_status_badge.setText(
                    f"🟢 READY — đủ hồ sơ. F2 để khóa & bắt đầu chụp [{demo.patient_id}]"
                )
                self.lbl_status_badge.setStyleSheet(
                    "color: #22c55e; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #052e16; border: 1px solid #16a34a; border-radius: 4px;"
                )
            else:
                field_hints = {
                    Field.PATIENT_ID: "Mã BN (gõ/F5)",
                    Field.FULL_NAME: 'Họ tên — nói "họ và tên …"',
                    Field.BIRTH_YEAR: 'Năm sinh — nói "năm sinh …"',
                    Field.GENDER: 'Giới tính — nói "giới tính nam/nữ"',
                }
                missing = " — ".join(
                    field_hints.get(f, f.value) for f in sorted(view.missing_for_gate, key=lambda x: x.value)
                )
                self.lbl_status_badge.setText(
                    f"🟢 ĐÃ MỞ PHIÊN ({phase.value}) · Thiếu: {missing}" if missing
                    else f"🟢 ĐÃ MỞ PHIÊN ({phase.value})"
                )
                self.lbl_status_badge.setStyleSheet(
                    "color: #22c55e; font-weight: bold; font-size: 13px; padding: 2px 6px; background-color: #052e16; border: 1px solid #16a34a; border-radius: 4px;"
                )
            if phase == Phase.INTAKE and not demo.patient_id:
                self.input_id.setFocus()

        self._last_phase = phase
        self.refresh_camera_panel(phase)

    def set_camera_hardware_error(self, message: str | None) -> None:
        """Show/clear camera HW failure on the live panel (not Standby copy)."""
        self._camera_hw_error = (message or "").strip() or None
        self.refresh_camera_panel(self._last_phase)

    def clear_camera_hardware_error(self) -> None:
        if self._camera_hw_error:
            self._camera_hw_error = None

    def refresh_camera_panel(self, phase=None) -> None:
        """Bind camera placeholder to session phase + hardware status."""
        from src.patient_session_controller import Phase

        if phase is None:
            phase = self._last_phase

        # Live frames already painted — don't clobber unless error / standby
        has_live = (
            self.camera_label.pixmap() is not None
            and not self.camera_label.pixmap().isNull()
        )

        if phase is None or phase == Phase.STANDBY:
            self.camera_label.setPixmap(QPixmap())
            self.camera_label.setStyleSheet(
                "background-color: #020617; border: 2px dashed #38bdf8; border-radius: 8px; "
                "color: #38bdf8; font-weight: bold; font-size: 13px;"
            )
            self.camera_label.setText(
                "⏸️ HỆ THỐNG ĐANG Ở CHẾ ĐỘ CHỜ (KẾT THÚC PHIÊN)\n\n"
                "[Bàn đạp, Giọng nói và Camera tạm dừng]\n"
                "[BẤM F1 ĐỂ MỞ ĐẦU PHIÊN KHÁM MỚI]"
            )
            return

        if self._camera_hw_error:
            self.camera_label.setPixmap(QPixmap())
            self.camera_label.setStyleSheet(
                "background-color: #450a0a; border: 2px solid #ef4444; border-radius: 8px; "
                "color: #fecaca; font-weight: bold; font-size: 13px;"
            )
            self.camera_label.setText(
                "📷 LỖI PHẦN CỨNG — KHÔNG KẾT NỐI ĐƯỢC CAMERA\n\n"
                f"{self._camera_hw_error}\n\n"
                "[Kiểm tra USB / quyền Camera (macOS) / chọn lại camera ở Tab Cài đặt]"
            )
            return

        if has_live:
            return

        self.camera_label.setStyleSheet(
            "background-color: #020617; border: 2px dashed #38bdf8; border-radius: 8px; "
            "color: #38bdf8; font-weight: bold; font-size: 13px;"
        )
        if phase == Phase.LOCKED_CAPTURE:
            self.camera_label.setText(
                "📷 ĐANG GHI ẢNH — chờ luồng camera…\n\n"
                "[Pedal / Space / giọng \"chụp\" để lưu ảnh]"
            )
        else:
            self.camera_label.setText(
                "📷 PHIÊN ĐÃ MỞ — đang chờ camera…\n\n"
                "[Nhập hồ sơ → F2 Bắt đầu chụp]"
            )

    def reset_session(self):
        self.active_patient = None
        self.input_id.clear()
        self.input_name.clear()
        self.input_birth.clear()
        set_gender_combo(self.input_gender, None)
        self.baseline_label.setText("[Chưa có ảnh Baseline]")
        self.baseline_panel.setVisible(False)
        for i in reversed(range(self.filmstrip_layout.count())):
            w = self.filmstrip_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        if not self.is_session_open:
            self.update_session_ui_state(False)

    def connect_signals(self):
        self.dispatcher.action_triggered.connect(self.on_action_triggered)

    def on_action_triggered(self, action: ActionType):
        if action == ActionType.START_SESSION:
            self.on_start_session()
        elif action == ActionType.SEARCH_GRID:
            self.open_search_grid()
        elif action == ActionType.COMPLETE_SESSION:
            self.on_complete_session()
        elif action == ActionType.CAPTURE:
            self.capture_requested.emit()
        elif action == ActionType.DELETE_LAST:
            self.delete_last_requested.emit()
        elif action == ActionType.DELETE_ALL:
            self.delete_all_requested.emit()
