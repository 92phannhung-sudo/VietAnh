"""View/edit patient record and photos from Tab 2 search results."""

from __future__ import annotations

from src.ui_gender_combo import make_gender_combo, set_gender_combo, gender_combo_value

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PatientDetailDialog(QDialog):
    def __init__(self, patient_id: str, parent=None, *, operator_name: str = ""):
        super().__init__(parent)
        self.patient_id = patient_id
        self.operator_name = operator_name
        self.setWindowTitle(f"Chi tiết hồ sơ — {patient_id}")
        self.resize(900, 640)
        self._build_ui()
        self._load_patient()
        self._load_photos()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        info_box = QGroupBox("Thông tin hồ sơ")
        form = QFormLayout(info_box)

        self.txt_id = QLineEdit()
        self.txt_id.setReadOnly(True)
        form.addRow("Mã BN:", self.txt_id)

        self.lbl_created = QLabel("—")
        self.lbl_created.setStyleSheet("color: #94a3b8;")
        form.addRow("Ngày tạo hồ sơ:", self.lbl_created)

        self.txt_name = QLineEdit()
        form.addRow("Họ và tên:", self.txt_name)

        self.txt_birth_year = QLineEdit()
        form.addRow("Năm sinh:", self.txt_birth_year)

        self.txt_gender = make_gender_combo()
        form.addRow("Giới tính:", self.txt_gender)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_save = QPushButton("💾 Lưu thông tin")
        btn_save.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        btn_save.clicked.connect(self._save_patient)
        btn_row.addWidget(btn_save)
        form.addRow("", btn_row)

        root.addWidget(info_box)

        photos_box = QGroupBox("Ảnh trong hồ sơ")
        photos_layout = QVBoxLayout(photos_box)

        self.lbl_photo_empty = QLabel("Chưa có ảnh nào trong hồ sơ này.")
        self.lbl_photo_empty.setAlignment(Qt.AlignCenter)
        self.lbl_photo_empty.setStyleSheet("color: #64748b; font-weight: bold; padding: 24px;")
        self.lbl_photo_empty.hide()

        self.photo_scroll = QScrollArea()
        self.photo_scroll.setWidgetResizable(True)
        self.photo_grid_host = QWidget()
        self.photo_grid = QGridLayout(self.photo_grid_host)
        self.photo_grid.setContentsMargins(8, 8, 8, 8)
        self.photo_grid.setSpacing(12)
        self.photo_scroll.setWidget(self.photo_grid_host)
        photos_layout.addWidget(self.photo_scroll)
        photos_layout.addWidget(self.lbl_photo_empty)

        root.addWidget(photos_box, stretch=1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

    def _load_patient(self):
        self.txt_id.setText(self.patient_id)
        patient = database.get_patient(self.patient_id)
        if not patient:
            self.txt_name.setPlaceholderText("Chưa có trong DB — nhập và Lưu để tạo")
            self.lbl_created.setText("—")
            return
        self.txt_name.setText(patient.get("name") or "")
        by = patient.get("birth_year")
        self.txt_birth_year.setText("" if by in (None, "") else str(by))
        set_gender_combo(self.txt_gender, patient.get("gender"))
        self.lbl_created.setText(format_patient_created_at(patient.get("created_at")))

    def _save_patient(self):
        name = self.txt_name.text().strip()
        birth_raw = self.txt_birth_year.text().strip()
        gender = self.txt_gender.currentText()
        birth_year = None
        if birth_raw:
            try:
                birth_year = int(birth_raw)
            except ValueError:
                QMessageBox.warning(self, "Cảnh báo", "Năm sinh phải là số nguyên.")
                return

        patient = database.get_patient(self.patient_id)
        if patient:
            database.update_patient(self.patient_id, name, birth_year, gender)
        else:
            database.create_patient(
                self.patient_id, name=name, birth_year=birth_year, gender=gender
            )
        database.log_audit_event(
            "PATIENT_UPDATE",
            operator_name=self.operator_name,
            patient_id=self.patient_id,
        )
        QMessageBox.information(self, "Thành công", "Đã lưu thông tin hồ sơ.")
        self._load_patient()

    def _clear_photo_grid(self):
        while self.photo_grid.count():
            item = self.photo_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_photos(self):
        self._clear_photo_grid()
        photos = database.get_patient_photos(self.patient_id)
        if not photos:
            self.lbl_photo_empty.show()
            self.photo_scroll.hide()
            return

        self.lbl_photo_empty.hide()
        self.photo_scroll.show()

        all_paths = [
            database.get_full_photo_path(photo["file_path"]) for photo in photos
        ]
        cols = 4
        for idx, photo in enumerate(photos):
            full_path = all_paths[idx]
            card = QGroupBox()
            card.setStyleSheet(
                """
                QGroupBox {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                }
                """
            )
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
            lbl_img.mousePressEvent = lambda e, p_idx=idx: hardware_test_dialogs.show_image_preview(
                self, photo_paths=all_paths, current_index=p_idx
            )
            card_layout.addWidget(lbl_img)

            lbl_info = QLabel(f"📄 Ảnh #{idx + 1}\n⏱️ {photo.get('captured_at', '')}")
            lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
            card_layout.addWidget(lbl_info)

            btn_del = QPushButton("🗑️ Xóa ảnh")
            btn_del.setStyleSheet(
                "background-color: #7f1d1d; color: white; padding: 4px; border-radius: 4px;"
            )
            photo_id = photo["id"]

            def _delete_photo(_checked=False, pid=photo_id):
                reply = QMessageBox.question(
                    self,
                    "Xác nhận xóa",
                    "Xóa ảnh này khỏi hồ sơ?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    database.delete_photo(pid, operator_name=self.operator_name)
                    self._load_photos()

            btn_del.clicked.connect(_delete_photo)
            card_layout.addWidget(btn_del)

            self.photo_grid.addWidget(card, idx // cols, idx % cols)
