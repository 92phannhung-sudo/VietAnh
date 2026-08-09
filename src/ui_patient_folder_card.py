"""Tab 2 folder card — always-visible actions (no hover-only overlay)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class PatientFolderCard(QWidget):
    """Patient folder thumbnail with persistent action buttons."""

    view_detail = Signal(str)
    continue_work = Signal(str)

    def __init__(
        self,
        patient_id: str,
        *,
        name: str = "",
        birth_year: str | int = "",
        gender: str = "",
        photo_count: int = 0,
        created_at_display: str = "—",
        cover_pixmap: QPixmap | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.patient_id = patient_id
        self.setFixedSize(228, 268)
        self.setStyleSheet(
            """
            QWidget#PatientFolderCard {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QWidget#PatientFolderCard:hover {
                border: 1.5px solid #38bdf8;
            }
            QLabel#cardTitle {
                font-weight: bold;
                font-size: 13px;
                color: #38bdf8;
            }
            QLabel#cardMeta, QLabel#cardCreated {
                color: #94a3b8;
                font-size: 11px;
            }
            QPushButton#btnDetail {
                background-color: #334155;
                color: #f8fafc;
                font-weight: bold;
                padding: 6px 4px;
                border-radius: 5px;
                border: none;
            }
            QPushButton#btnDetail:hover { background-color: #475569; }
            QPushButton#btnContinue {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                padding: 6px 4px;
                border-radius: 5px;
                border: none;
            }
            QPushButton#btnContinue:hover { background-color: #15803d; }
            """
        )
        self.setObjectName("PatientFolderCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl_cover = QLabel()
        lbl_cover.setFixedSize(208, 96)
        lbl_cover.setAlignment(Qt.AlignCenter)
        lbl_cover.setStyleSheet("background-color: #020617; border-radius: 4px;")
        if cover_pixmap and not cover_pixmap.isNull():
            lbl_cover.setPixmap(cover_pixmap)
        else:
            lbl_cover.setText("📁")
            lbl_cover.setStyleSheet(
                "background-color: #020617; color: #475569; font-size: 28px; border-radius: 4px;"
            )
        layout.addWidget(lbl_cover)

        lbl_title = QLabel(f"📂 {patient_id}")
        lbl_title.setObjectName("cardTitle")
        layout.addWidget(lbl_title)

        year = birth_year if birth_year not in (None, "") else "—"
        gender_txt = gender or "—"
        lbl_meta = QLabel(f"{name or 'Chưa tên'} · {year} · {gender_txt}")
        lbl_meta.setObjectName("cardMeta")
        lbl_meta.setWordWrap(True)
        layout.addWidget(lbl_meta)

        lbl_created = QLabel(f"📅 Tạo: {created_at_display} · 🖼️ {photo_count} ảnh")
        lbl_created.setObjectName("cardCreated")
        lbl_created.setWordWrap(True)
        layout.addWidget(lbl_created)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_detail = QPushButton("Chi tiết")
        btn_detail.setObjectName("btnDetail")
        btn_detail.setCursor(Qt.PointingHandCursor)
        btn_detail.clicked.connect(lambda: self.view_detail.emit(self.patient_id))
        btn_row.addWidget(btn_detail, stretch=1)

        btn_continue = QPushButton("Làm việc tiếp")
        btn_continue.setObjectName("btnContinue")
        btn_continue.setCursor(Qt.PointingHandCursor)
        btn_continue.clicked.connect(lambda: self.continue_work.emit(self.patient_id))
        btn_row.addWidget(btn_continue, stretch=1)

        layout.addLayout(btn_row)
