"""Patient search grid dialog — recent / filtered / empty-new-patient prompt."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGridLayout,
    QScrollArea,
    QWidget,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

from src.patient_search_service import PatientSearchService


class PatientCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, patient_data: dict, parent=None, *, selected: bool = False):
        super().__init__(parent)
        self.patient_data = patient_data
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        border = "#38bdf8" if selected else "#334155"
        bg = "#0c4a6e" if selected else "#1e293b"
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 8px;
                padding: 8px;
            }}
            QFrame:hover {{
                border: 2px solid #38bdf8;
                background-color: #0f172a;
            }}
            """
        )

        layout = QVBoxLayout(self)

        self.thumb_label = QLabel("🔍 Ảnh Baseline")
        self.thumb_label.setFixedHeight(100)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(
            "background-color: #090d16; color: #64748b; border-radius: 4px;"
        )
        layout.addWidget(self.thumb_label)

        info_lbl = QLabel(
            f"<b>{patient_data.get('full_name')}</b><br>"
            f"Mã: {patient_data.get('patient_id')}<br>"
            f"Năm sinh: {patient_data.get('birth_year')} | {patient_data.get('gender')}"
        )
        info_lbl.setStyleSheet("color: #f8fafc; font-size: 11px;")
        layout.addWidget(info_lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self.patient_data)
        super().mousePressEvent(event)


class PatientGridDialog(QDialog):
    patient_selected = Signal(dict)
    new_patient_id_confirmed = Signal(str)
    filters_changed = Signal(dict)

    def __init__(
        self,
        search_service: PatientSearchService,
        parent=None,
        *,
        mode: str = "recent",
        initial_patient_id: str = "",
        initial_full_name: str = "",
        initial_birth_year: str = "",
        initial_gender: str = "",
    ):
        super().__init__(parent)
        self.search_service = search_service
        self._mode = mode
        self._results: list[dict] = []
        self._selected_index = -1
        self._suppress_filter_signal = False
        self.setWindowTitle("ĐANG TÌM HỒ SƠ — Tra cứu Bệnh nhân")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(800, 600)
        self.setup_ui()
        if initial_patient_id:
            self.filter_id.setText(initial_patient_id)
        if initial_full_name:
            self.filter_name.setText(initial_full_name)
        if initial_birth_year:
            self.filter_birth.setText(initial_birth_year)
        if initial_gender:
            self.filter_gender.setText(initial_gender)
        if mode == "recent" and not any(
            [initial_patient_id, initial_full_name, initial_birth_year, initial_gender]
        ):
            self.load_recent()
        else:
            self.perform_search()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        self.lbl_banner = QLabel("ĐANG TÌM HỒ SƠ")
        self.lbl_banner.setStyleSheet(
            "color: #fbbf24; font-weight: bold; font-size: 14px; padding: 4px;"
        )
        main_layout.addWidget(self.lbl_banner)

        filter_bar = QHBoxLayout()
        self.filter_id = QLineEdit()
        self.filter_id.setPlaceholderText("Mã hồ sơ/phiếu (khớp Exact)")
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText("Họ và tên")
        self.filter_birth = QLineEdit()
        self.filter_birth.setPlaceholderText("Năm sinh")
        self.filter_gender = QLineEdit()
        self.filter_gender.setPlaceholderText("Giới tính")

        self.btn_search = QPushButton("🔍 Tìm kiếm")
        self.btn_search.clicked.connect(self.perform_search)

        for w in (
            self.filter_id,
            self.filter_name,
            self.filter_birth,
            self.filter_gender,
        ):
            w.returnPressed.connect(self.perform_search)

        filter_bar.addWidget(self.filter_id)
        filter_bar.addWidget(self.filter_name)
        filter_bar.addWidget(self.filter_birth)
        filter_bar.addWidget(self.filter_gender)
        filter_bar.addWidget(self.btn_search)
        main_layout.addLayout(filter_bar)

        self.lbl_empty = QLabel("")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setStyleSheet("color: #f8fafc; padding: 8px;")
        self.lbl_empty.hide()
        main_layout.addWidget(self.lbl_empty)

        self.btn_confirm_new = QPushButton("Dùng mã này cho bệnh nhân mới")
        self.btn_confirm_new.setStyleSheet(
            "background-color: #15803d; color: white; font-weight: bold; padding: 8px;"
        )
        self.btn_confirm_new.clicked.connect(self._confirm_new_patient)
        self.btn_confirm_new.hide()
        main_layout.addWidget(self.btn_confirm_new)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll_area)

    def current_filters(self) -> dict:
        return {
            "patient_id": self.filter_id.text().strip(),
            "full_name": self.filter_name.text().strip(),
            "birth_year": self.filter_birth.text().strip(),
            "gender": self.filter_gender.text().strip(),
        }

    def apply_external_filters(self, **kwargs) -> None:
        """Voice / barcode can fill filters without writing Cockpit."""
        self._suppress_filter_signal = True
        try:
            if "patient_id" in kwargs and kwargs["patient_id"] is not None:
                self.filter_id.setText(str(kwargs["patient_id"]))
            if "full_name" in kwargs and kwargs["full_name"] is not None:
                self.filter_name.setText(str(kwargs["full_name"]))
            if "birth_year" in kwargs and kwargs["birth_year"] is not None:
                self.filter_birth.setText(str(kwargs["birth_year"]))
            if "gender" in kwargs and kwargs["gender"] is not None:
                self.filter_gender.setText(str(kwargs["gender"]))
            self.perform_search()
        finally:
            self._suppress_filter_signal = False

    def load_recent(self):
        self._mode = "recent"
        self.lbl_banner.setText("ĐANG TÌM HỒ SƠ · Gần đây (50)")
        self._render_results(self.search_service.recent(limit=50))

    def perform_search(self):
        filters = self.current_filters()
        if not self._suppress_filter_signal:
            self.filters_changed.emit(filters)
        has_filter = any(filters.values())
        if not has_filter:
            self.load_recent()
            return
        self._mode = "filtered"
        self.lbl_banner.setText("ĐANG TÌM HỒ SƠ · Đã lọc")
        results = self.search_service.search(
            filters["patient_id"],
            filters["full_name"],
            filters["birth_year"],
            filters["gender"],
        )
        self._render_results(results)

    def _render_results(self, results: list[dict]):
        self._results = list(results)
        self._selected_index = 0 if len(self._results) == 1 else -1

        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        self.lbl_empty.hide()
        self.btn_confirm_new.hide()

        if not self._results:
            pid = self.filter_id.text().strip()
            if pid:
                self.lbl_empty.setText(
                    f"Chưa có hồ sơ [{pid}]. Dùng mã này cho bệnh nhân mới?"
                )
                self.lbl_empty.show()
                self.btn_confirm_new.show()
            else:
                self.lbl_empty.setText("Không có kết quả.")
                self.lbl_empty.show()
            return

        cols = 3
        for idx, item in enumerate(self._results):
            card = PatientCard(item, selected=(idx == self._selected_index))
            card.clicked.connect(self.on_card_selected)
            self.grid_layout.addWidget(card, idx // cols, idx % cols)

    def _confirm_new_patient(self):
        pid = self.filter_id.text().strip()
        if not pid:
            return
        self.new_patient_id_confirmed.emit(pid)
        self.accept()

    def on_card_selected(self, patient_data: dict):
        self.patient_selected.emit(patient_data)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if len(self._results) == 1:
                self.on_card_selected(self._results[0])
                return
            if (
                self._selected_index >= 0
                and self._selected_index < len(self._results)
            ):
                self.on_card_selected(self._results[self._selected_index])
                return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
