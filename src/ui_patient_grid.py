from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGridLayout, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
from src.patient_search_service import PatientSearchService

class PatientCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, patient_data: dict, parent=None):
        super().__init__(parent)
        self.patient_data = patient_data
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
            }
            QFrame:hover {
                border: 2px solid #38bdf8;
                background-color: #0f172a;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Thumbnail placeholder for latest baseline photo
        self.thumb_label = QLabel("🔍 Ảnh Baseline")
        self.thumb_label.setFixedHeight(100)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background-color: #090d16; color: #64748b; border-radius: 4px;")
        layout.addWidget(self.thumb_label)

        info_lbl = QLabel(f"<b>{patient_data.get('full_name')}</b><br>"
                          f"Mã: {patient_data.get('patient_id')}<br>"
                          f"Năm sinh: {patient_data.get('birth_year')} | {patient_data.get('gender')}")
        info_lbl.setStyleSheet("color: #f8fafc; font-size: 11px;")
        layout.addWidget(info_lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self.patient_data)
        super().mousePressEvent(event)


class PatientGridDialog(QDialog):
    patient_selected = Signal(dict)

    def __init__(self, search_service: PatientSearchService, parent=None):
        super().__init__(parent)
        self.search_service = search_service
        self.setWindowTitle("🔍 Tra cứu & Tìm kiếm Hồ sơ Bệnh nhân (Grid View)")
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Filter Bar (4 Optional Fields)
        filter_bar = QHBoxLayout()
        self.filter_id = QLineEdit()
        self.filter_id.setPlaceholderText("Mã hồ sơ/phiếu")
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText("Họ và tên")
        self.filter_birth = QLineEdit()
        self.filter_birth.setPlaceholderText("Năm sinh")
        self.filter_gender = QLineEdit()
        self.filter_gender.setPlaceholderText("Giới tính")

        self.btn_search = QPushButton("🔍 Tìm kiếm")
        self.btn_search.clicked.connect(self.perform_search)

        filter_bar.addWidget(self.filter_id)
        filter_bar.addWidget(self.filter_name)
        filter_bar.addWidget(self.filter_birth)
        filter_bar.addWidget(self.filter_gender)
        filter_bar.addWidget(self.btn_search)

        main_layout.addLayout(filter_bar)

        # Grid List Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)

        main_layout.addWidget(self.scroll_area)

    def perform_search(self):
        p_id = self.filter_id.text()
        p_name = self.filter_name.text()
        p_birth = self.filter_birth.text()
        p_gender = self.filter_gender.text()

        results = self.search_service.search(p_id, p_name, p_birth, p_gender)
        
        # Clear existing grid
        for i in reversed(range(self.grid_layout.count())): 
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        cols = 3
        for idx, item in enumerate(results):
            card = PatientCard(item)
            card.clicked.connect(self.on_card_selected)
            r = idx // cols
            c = idx % cols
            self.grid_layout.addWidget(card, r, c)

    def on_card_selected(self, patient_data: dict):
        self.patient_selected.emit(patient_data)
        self.accept()
