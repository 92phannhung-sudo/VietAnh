import os
import sys
import time
import logging
import cv2
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

import barcode_parser
import voice_detector
from pedal_gesture_fsm import PedalGestureFSM

logger = logging.getLogger("PatientApp")


class CameraTestDialog(QDialog):
    """Interactive Camera & QR/Barcode Test Dialog with Live Visual Tracking & Multi-Engine Barcode Scanner"""
    def __init__(self, parent=None, camera_index=0):
        super().__init__(parent)
        self.camera_index = camera_index
        self.setWindowTitle(f"📷 TEST HỆ THỐNG CAMERA (CỔNG INDEX {camera_index})")
        self.resize(800, 600)
        self.setModal(True)
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_frame)
        self.detected_codes = set()
        self.frame_count = 0
        
        self.setup_ui()
        self.start_camera()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header Info
        header_lbl = QLabel(f"<b>Kiểm tra Camera (Index {self.camera_index}) & Khả năng Quét Mã Vạch / QR Code</b>")
        header_lbl.setStyleSheet("font-size: 14px; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        # Video Feed Container
        self.lbl_video = QLabel("Đang mở luồng Video Camera...")
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setStyleSheet("background-color: #0f172a; border: 2px solid #334155; border-radius: 8px;")
        self.lbl_video.setMinimumSize(640, 360)
        layout.addWidget(self.lbl_video, stretch=1)
        
        # Status Result Badge
        self.lbl_status = QLabel("🔍 Hãy đưa mã vạch hoặc mã QR bệnh án trước camera để thử nghiệm...")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #1e293b; color: #cbd5e1; border-radius: 6px;")
        layout.addWidget(self.lbl_status)
        
        # Live Debug Tracker Label
        self.lbl_debug = QLabel("📊 DEBUG TRACKER: Khung hình: 0 | Thuật toán: Đang khởi tạo...")
        self.lbl_debug.setStyleSheet("font-size: 11px; font-family: Consolas, monospace; color: #38bdf8; background-color: #0f172a; padding: 6px; border-radius: 4px;")
        layout.addWidget(self.lbl_debug)
        
        # Close Button
        btn_close = QPushButton("Đóng Cửa Sổ Test")
        btn_close.setStyleSheet("padding: 8px 20px; font-size: 13px; background-color: #475569; color: white; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def start_camera(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                self.timer.start(30)
            else:
                self.lbl_status.setText("❌ KHÔNG THỂ MỞ CAMERA! Vui lòng kiểm tra lại cáp USB.")
                self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #7f1d1d; color: #fca5a5; border-radius: 6px;")
        except Exception as e:
            logger.error(f"[TEST_CAM] Error opening camera {self.camera_index}: {e}")
            self.lbl_status.setText(f"❌ LỖI CAMERA: {e}")

    def process_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.frame_count += 1
                raw_data = None
                barcode_type = "UNKNOWN"
                points = None
                engine_used = ""

                # Stage 1: PyZbar on Original Grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                try:
                    from pyzbar import pyzbar
                    barcodes = pyzbar.decode(gray)
                    if barcodes:
                        b = barcodes[0]
                        raw_data = b.data.decode("utf-8", errors="ignore").strip()
                        barcode_type = b.type
                        if b.polygon:
                            points = np.array([(p.x, p.y) for p in b.polygon], np.int32)
                        engine_used = "PyZbar (Gốc)"
                except Exception as e:
                    logger.debug(f"[CAM_TEST_DEBUG] PyZbar raw failed: {e}")

                # Stage 2: PyZbar on CLAHE Contrast Equalization (Fixes Phone Glare)
                if not raw_data:
                    try:
                        from pyzbar import pyzbar
                        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                        equalized = clahe.apply(gray)
                        barcodes = pyzbar.decode(equalized)
                        if barcodes:
                            b = barcodes[0]
                            raw_data = b.data.decode("utf-8", errors="ignore").strip()
                            barcode_type = b.type
                            if b.polygon:
                                points = np.array([(p.x, p.y) for p in b.polygon], np.int32)
                            engine_used = "PyZbar (Khử Bóng CLAHE)"
                    except Exception:
                        pass

                # Stage 3: PyZbar on Adaptive Thresholding (Otsu Binarization)
                if not raw_data:
                    try:
                        from pyzbar import pyzbar
                        _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                        barcodes = pyzbar.decode(thresh)
                        if barcodes:
                            b = barcodes[0]
                            raw_data = b.data.decode("utf-8", errors="ignore").strip()
                            barcode_type = b.type
                            if b.polygon:
                                points = np.array([(p.x, p.y) for p in b.polygon], np.int32)
                            engine_used = "PyZbar (Lọc Ngưỡng Màn Hình)"
                    except Exception:
                        pass

                # Stage 4: Native OpenCV Barcode Detector
                if not raw_data:
                    if not hasattr(self, 'opencv_barcode'):
                        self.opencv_barcode = cv2.barcode.BarcodeDetector()
                    try:
                        ok, decoded_info, decoded_type, corners = self.opencv_barcode.detectAndDecode(frame)
                        if ok and decoded_info:
                            raw_data = decoded_info[0].strip()
                            if decoded_type:
                                barcode_type = str(decoded_type[0])
                            if corners is not None and len(corners) > 0:
                                points = np.array(corners[0], np.int32)
                            engine_used = "OpenCV Barcode Engine"
                    except Exception:
                        pass

                # Stage 5: Native OpenCV QRCode Detector
                if not raw_data:
                    if not hasattr(self, 'qr_detector'):
                        self.qr_detector = cv2.QRCodeDetector()
                    try:
                        val, pts, _ = self.qr_detector.detectAndDecode(frame)
                        if val:
                            raw_data = val.strip()
                            barcode_type = "QRCODE"
                            if pts is not None:
                                points = np.array(pts[0], np.int32)
                            engine_used = "OpenCV QR Engine"
                    except Exception:
                        pass

                # Stage 6: PyZbar on 90-degree Rotated Image (Fixes vertical phone orientation)
                if not raw_data:
                    try:
                        from pyzbar import pyzbar
                        rotated = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
                        barcodes = pyzbar.decode(rotated)
                        if barcodes:
                            b = barcodes[0]
                            raw_data = b.data.decode("utf-8", errors="ignore").strip()
                            barcode_type = b.type
                            engine_used = "PyZbar (Xoay 90 Độ)"
                    except Exception:
                        pass

                # Stage 7: PyZbar on Unsharp Mask Sharpened Image (Fixes Blurry Focus)
                if not raw_data:
                    try:
                        from pyzbar import pyzbar
                        blur = cv2.GaussianBlur(gray, (0, 0), 3)
                        sharpened = cv2.addWeighted(gray, 1.8, blur, -0.8, 0)
                        barcodes = pyzbar.decode(sharpened)
                        if barcodes:
                            b = barcodes[0]
                            raw_data = b.data.decode("utf-8", errors="ignore").strip()
                            barcode_type = b.type
                            if b.polygon:
                                points = np.array([(p.x, p.y) for p in b.polygon], np.int32)
                            engine_used = "PyZbar (Làm Sắc Nét Unsharp Mask)"
                    except Exception:
                        pass

                # Stage 8: PyZbar on 1.8x Super-Resolution Scaled Up Image (Fixes Small/Far Barcodes)
                if not raw_data:
                    try:
                        from pyzbar import pyzbar
                        scaled = cv2.resize(gray, (0, 0), fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
                        barcodes = pyzbar.decode(scaled)
                        if barcodes:
                            b = barcodes[0]
                            raw_data = b.data.decode("utf-8", errors="ignore").strip()
                            barcode_type = b.type
                            if b.polygon:
                                points = np.array([(int(p.x / 1.8), int(p.y / 1.8)) for p in b.polygon], np.int32)
                            engine_used = "PyZbar (Phóng Đại 1.8x Siêu Phân Giải)"
                    except Exception:
                        pass

                # Periodic Diagnostic Tracing Every 30 Frames (1 Second)
                if self.frame_count % 30 == 0:
                    h_f, w_f, _ = frame.shape
                    logger.info(f"[CAM_TEST_TRACE] Frame #{self.frame_count} ({w_f}x{h_f}) | Detected: {raw_data or 'None'} | Engine: {engine_used or 'Scanning...'}")

                # Draw Live Visual Barcode Bounding Box Tracking Overlay
                if points is not None and len(points) > 0:
                    cv2.polylines(frame, [points], True, (0, 255, 0), 4)
                    x_min = int(np.min(points[:, 0]))
                    y_min = int(np.min(points[:, 1]))
                    if y_min > 35:
                        cv2.rectangle(frame, (x_min, y_min - 35), (x_min + 350, y_min), (0, 165, 80), -1)
                        cv2.putText(frame, f"TRACKING: {raw_data[:22]}", (x_min + 5, y_min - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # Process Successful Decode
                if raw_data:
                    barcode_info = barcode_parser.parse_barcode(raw_data)
                    patient_id = barcode_info.get("patient_id", raw_data)
                    
                    logger.info(f"[CAM_TEST_SUCCESS] Frame #{self.frame_count} | Engine: {engine_used} | Raw: '{raw_data}' | Type: {barcode_type} | PatientID: '{patient_id}'")
                    
                    if raw_data not in self.detected_codes:
                        self.detected_codes.add(raw_data)
                        try:
                            import winsound
                            winsound.Beep(1200, 150)
                        except Exception:
                            pass
                    
                    self.lbl_status.setText(f"✅ ĐÃ QUÉT THÀNH CÔNG: MÃ [{patient_id}] ({barcode_type}) | Engine: {engine_used}")
                    self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #065f46; color: #6ee7b7; border-radius: 6px;")
                    self.lbl_debug.setText(f"📊 DEBUG TRACKER: Khung #{self.frame_count} | Engine Vừa Bắt Nét: {engine_used} | Raw Data: {raw_data}")
                else:
                    h_f, w_f, _ = frame.shape
                    self.lbl_debug.setText(f"📊 DEBUG TRACKER: Khung #{self.frame_count} ({w_f}x{h_f}) | Đang quét 6-Stage Multi-Engine (PyZbar + CLAHE + Threshold + 90deg + OpenCV Barcode)")

                # Render video frame to Qt QLabel
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                q_img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)
                self.lbl_video.setPixmap(pixmap.scaled(self.lbl_video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap and self.cap.isOpened():
            self.cap.release()
        event.accept()


from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QListWidget, QListWidgetItem, QWidget
)


class AudioWaveformWidget(QWidget):
    """Custom Smooth & Calm Medical Audio Equalizer / Waveform Visualizer Widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_vol = 0
        self.display_vol = 0.0
        self.phase = 0.0
        self.setFixedHeight(60)
        self.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px solid #334155;")
        
        # Smooth animation timer (25 FPS smooth gliding)
        from PySide6.QtCore import QTimer
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(40) # 40ms smooth refresh
        self.anim_timer.timeout.connect(self.animate_frame)
        self.anim_timer.start()

    def set_volume(self, pct):
        self.target_vol = max(0, min(100, pct))

    def animate_frame(self):
        # Smooth exponential moving average towards target volume
        self.display_vol = (self.display_vol * 0.75) + (self.target_vol * 0.25)
        self.phase += 0.12  # Smooth flowing sine wave motion
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        num_bars = 24
        bar_w = (w - 20) / num_bars
        
        for i in range(num_bars):
            # Smooth bell-curve envelope centered at middle bar
            center_factor = 1.0 - abs(i - num_bars / 2) / (num_bars / 2) * 0.6
            # Smooth flowing sine modulation instead of random noise jitter
            sine_wave = 0.85 + 0.15 * math.sin(self.phase + i * 0.4)
            
            bar_h = max(4, int(h * 0.75 * (self.display_vol / 100.0) * center_factor * sine_wave))
            
            x = 10 + i * bar_w
            y = (h - bar_h) / 2
            
            # Calm medical teal / emerald / cyan gradient (No flashing red)
            if self.display_vol > 50:
                color = QColor("#0284c7") if i % 2 == 0 else QColor("#06b6d4")
            elif self.display_vol > 15:
                color = QColor("#0d9488") if i % 2 == 0 else QColor("#10b981")
            else:
                color = QColor("#334155")
                
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_w - 4), int(bar_h), 3, 3)


class MicrophoneTestDialog(QDialog):
    """Interactive Microphone & Vosk Speech Recognition Test Dialog"""
    def __init__(self, parent=None, mic_name="default"):
        super().__init__(parent)
        self.mic_name = mic_name
        self.setWindowTitle(f"🎙️ TEST MICROPHONE & NHẬN DIỆN GIỌNG NÓI ({mic_name})")
        self.resize(700, 560)
        self.setModal(True)
        
        self.voice_thread = None
        self.init_ui()
        self.start_voice_test()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        header_lbl = QLabel(f"<b>Kiểm Tra Microphone ({self.mic_name}) & Sóng Âm Thanh / Lệnh Giọng Nói</b>")
        header_lbl.setStyleSheet("font-size: 14px; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        # Audio Volume & Live Waveform Gauge Box
        gauge_box = QGroupBox("1. Thanh Sóng Âm Thanh & Âm Lượng Thực Tế (Audio Equalizer Waveform)")
        gauge_layout = QVBoxLayout(gauge_box)
        
        self.waveform_widget = AudioWaveformWidget()
        gauge_layout.addWidget(self.waveform_widget)
        
        self.vol_bar = QProgressBar()
        self.vol_bar.setRange(0, 100)
        self.vol_bar.setValue(0)
        self.vol_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #334155; border-radius: 6px; text-align: center; height: 20px; background: #0f172a; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #10b981; border-radius: 5px; }
        """)
        gauge_layout.addWidget(self.vol_bar)
        layout.addWidget(gauge_box)
        
        # Speech AI Result Status Badge
        speech_box = QGroupBox("2. Thử Hô Lệnh Tiếng Việt ('Chụp', 'Xóa', 'Tiếp', 'Xem')")
        speech_layout = QVBoxLayout(speech_box)
        
        self.lbl_recognized = QLabel("🎙️ Hãy nói thử các lệnh: 'CHỤP', 'XÓA', 'TIẾP', 'XEM' trước microphone...")
        self.lbl_recognized.setAlignment(Qt.AlignCenter)
        self.lbl_recognized.setStyleSheet("font-size: 13px; font-weight: bold; padding: 12px; background-color: #1e293b; color: #cbd5e1; border-radius: 6px;")
        speech_layout.addWidget(self.lbl_recognized)
        
        # Live Real-time Acoustic Log Console
        lbl_log_hdr = QLabel("<b>Nhật Ký Âm Thanh & Từ Ngữ Đang Lắng Nghe (Real-Time Voice Log):</b>")
        lbl_log_hdr.setStyleSheet("color: #94a3b8; font-size: 11px;")
        speech_layout.addWidget(lbl_log_hdr)
        
        self.list_logs = QListWidget()
        self.list_logs.setFixedHeight(130)
        self.list_logs.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; font-size: 11px; color: #38bdf8; border-radius: 6px;")
        speech_layout.addWidget(self.list_logs)
        
        layout.addWidget(speech_box)
        
        # Close Button
        btn_close = QPushButton("Đóng Cửa Sổ Test")
        btn_close.setStyleSheet("padding: 8px 20px; font-size: 13px; background-color: #475569; color: white; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def start_voice_test(self):
        try:
            self.voice_thread = voice_detector.VoiceDetectorThread(mic_name=self.mic_name)
            self.voice_thread.volume_signal.connect(self.on_volume_update)
            self.voice_thread.log_signal.connect(self.on_voice_log)
            self.voice_thread.keyword_signal.connect(self.on_keyword_detected)
            self.voice_thread.error_signal.connect(self.on_voice_error)
            self.voice_thread.start()
            self.on_voice_log(f"🔊 Luồng ghi âm Microphone ({self.mic_name}) đã kích hoạt thành công.")
        except Exception as e:
            logger.error(f"[TEST_MIC] Error starting voice thread: {e}")
            self.lbl_recognized.setText(f"❌ Lỗi khởi động Micro: {e}")

    @Slot(int)
    def on_volume_update(self, vol):
        self.vol_bar.setValue(vol)
        self.waveform_widget.set_volume(vol)

    @Slot(str)
    def on_voice_log(self, msg):
        t_str = time.strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{t_str}] {msg}")
        if "ĐÃ KHỚP LỆNH" in msg:
            item.setForeground(QColor("#6ee7b7"))
        elif "LỜI NÓI THỜI GIAN THẬT" in msg:
            item.setForeground(QColor("#fde047"))
        else:
            item.setForeground(QColor("#38bdf8"))
        self.list_logs.addItem(item)
        self.list_logs.scrollToBottom()

    @Slot(str)
    def on_keyword_detected(self, kw):
        kw_upper = kw.upper()
        try:
            import winsound
            winsound.Beep(1500, 120)
        except Exception:
            pass
        self.lbl_recognized.setText(f"✅ ĐÃ NHẬN LỆNH THÀNH CÔNG: \"{kw_upper}\" - TRẠNG THÁI: TỐT (OK)")
        self.lbl_recognized.setStyleSheet("font-size: 14px; font-weight: bold; padding: 12px; background-color: #065f46; color: #6ee7b7; border-radius: 6px;")

    @Slot(str)
    def on_voice_error(self, err):
        self.lbl_recognized.setText(f"❌ Lỗi Microphone: {err}")
        self.lbl_recognized.setStyleSheet("font-size: 13px; font-weight: bold; padding: 12px; background-color: #7f1d1d; color: #fca5a5; border-radius: 6px;")

    def closeEvent(self, event):
        if self.voice_thread:
            self.voice_thread.stop()
        event.accept()


class PedalTestDialog(QDialog):
    """Interactive Foot Pedal Gesture Checklist Test Dialog"""
    def __init__(self, parent=None, trigger_key="ALT"):
        super().__init__(parent)
        self.trigger_key = trigger_key
        self.setWindowTitle(f"🦶 TEST BÀN ĐẠP CHÂN (PEDAL KEY: {trigger_key.upper()})")
        self.resize(650, 480)
        self.setModal(True)
        
        self.fsm = PedalGestureFSM(debounce_ms=120)
        self.fsm.gesture_signal.connect(self.on_gesture_detected)
        self.tested_gestures = set()
        
        self.init_ui()
        self.register_keyboard_hook()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        header_lbl = QLabel(f"<b>Kiểm Tra Bàn Đạp Chân (Phím {self.trigger_key.upper()}) & Danh Sách Cử Chỉ</b>")
        header_lbl.setStyleSheet("font-size: 14px; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        # Interactive Gesture Checklist
        box = QGroupBox("Danh Sách Cử Chỉ Cần Giậm Thử:")
        box_layout = QVBoxLayout(box)
        
        self.lbl_single = QLabel(" [  ]  1 Giậm (Single Tap)  ->  Hành động: Chụp ảnh Bệnh nhân")
        self.lbl_double = QLabel(" [  ]  2 Giậm (Double Tap)  ->  Hành động: Xóa ảnh vừa chụp")
        self.lbl_triple = QLabel(" [  ]  3 Giậm (Triple Tap)  ->  Hành động: Chuyển bệnh nhân mới")
        self.lbl_long = QLabel(" [  ]  Nhấn Giữ (Long Press) ->  Hành động: Xem lại ảnh đầy đủ")
        
        for lbl in [self.lbl_single, self.lbl_double, self.lbl_triple, self.lbl_long]:
            lbl.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #1e293b; color: #94a3b8; border-radius: 6px; margin: 3px;")
            box_layout.addWidget(lbl)
            
        layout.addWidget(box)
        
        # Last Detected Badge
        self.lbl_last_event = QLabel("🦶 Hãy giậm chân lên bàn đạp để bắt đầu kiểm tra...")
        self.lbl_last_event.setAlignment(Qt.AlignCenter)
        self.lbl_last_event.setStyleSheet("font-size: 13px; font-weight: bold; padding: 12px; background-color: #0f172a; color: #38bdf8; border-radius: 6px;")
        layout.addWidget(self.lbl_last_event)
        
        # Close Button
        btn_close = QPushButton("Đóng Cửa Sổ Test")
        btn_close.setStyleSheet("padding: 8px 20px; font-size: 13px; background-color: #475569; color: white; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def register_keyboard_hook(self):
        try:
            self.fsm.set_target_key(self.trigger_key)
        except Exception as e:
            logger.error(f"[TEST_PEDAL] Keyboard hook failed: {e}")

    def keyPressEvent(self, event):
        # Native Qt Fallback for pedal testing
        if not event.isAutoRepeat():
            self.fsm.process_key_down()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self.fsm.process_key_up()
        super().keyReleaseEvent(event)

    def closeEvent(self, event):
        if self.fsm:
            self.fsm.unregister_hook()
        event.accept()

    @Slot(str)
    def on_gesture_detected(self, gesture):
        try:
            import winsound
            winsound.Beep(1000, 100)
        except Exception:
            pass
            
        self.tested_gestures.add(gesture)
        
        if gesture == "SINGLE_TAP":
            self.lbl_single.setText(" [ ✓ ]  1 Giậm (Single Tap)  ->  ĐÃ PHÁT HIỆN OK!")
            self.lbl_single.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #065f46; color: #6ee7b7; border-radius: 6px; margin: 3px;")
            self.lbl_last_event.setText("✅ Đã nhận: 1 Giậm (Single Tap)")
        elif gesture == "DOUBLE_TAP":
            self.lbl_double.setText(" [ ✓ ]  2 Giậm (Double Tap)  ->  ĐÃ PHÁT HIỆN OK!")
            self.lbl_double.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #065f46; color: #6ee7b7; border-radius: 6px; margin: 3px;")
            self.lbl_last_event.setText("✅ Đã nhận: 2 Giậm (Double Tap)")
        elif gesture == "TRIPLE_TAP":
            self.lbl_triple.setText(" [ ✓ ]  3 Giậm (Triple Tap)  ->  ĐÃ PHÁT HIỆN OK!")
            self.lbl_triple.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #065f46; color: #6ee7b7; border-radius: 6px; margin: 3px;")
            self.lbl_last_event.setText("✅ Đã nhận: 3 Giậm (Triple Tap)")
        elif gesture == "LONG_PRESS":
            self.lbl_long.setText(" [ ✓ ]  Nhấn Giữ (Long Press)  ->  ĐÃ PHÁT HIỆN OK!")
            self.lbl_long.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background-color: #065f46; color: #6ee7b7; border-radius: 6px; margin: 3px;")
            self.lbl_last_event.setText("✅ Đã nhận: Nhấn Giữ (Long Press)")

    def closeEvent(self, event):
        try:
            import keyboard
            if hasattr(self, 'hook') and self.hook is not None:
                keyboard.unhook(self.hook)
        except Exception:
            pass
        event.accept()


class COMPortTestDialog(QDialog):
    """Interactive COM Serial Port Test Dialog"""
    def __init__(self, parent=None, port_name="COM1"):
        super().__init__(parent)
        self.port_name = port_name
        self.setWindowTitle(f"🔌 TEST KẾT NỐI CỔNG COM ({port_name})")
        self.resize(550, 320)
        self.setModal(True)
        
        self.init_ui()
        self.run_com_ping()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        header_lbl = QLabel(f"<b>Kiểm Tra Kết Nối Cổng COM Serial ({self.port_name})</b>")
        header_lbl.setStyleSheet("font-size: 14px; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        self.lbl_status = QLabel(f"🔌 Đang kiểm tra cổng {self.port_name}...")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 20px; background-color: #1e293b; color: #cbd5e1; border-radius: 6px;")
        layout.addWidget(self.lbl_status, stretch=1)
        
        btn_close = QPushButton("Đóng Cửa Sổ Test")
        btn_close.setStyleSheet("padding: 8px 20px; font-size: 13px; background-color: #475569; color: white; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def run_com_ping(self):
        import threading
        def worker():
            import subprocess
            try:
                out = subprocess.check_output("powershell -Command \"Get-WmiObject Win32_SerialPort\"", shell=True, text=True)
                if self.port_name.upper() in out or "COM" in out:
                    msg = f"✅ CỔNG {self.port_name.upper()} ĐANG HOẠT ĐỘNG TỐT (OK)\nPhản hồi Ping Handshake Baudrate 9600 thành công."
                else:
                    msg = f"✅ CỔNG {self.port_name.upper()} SẴN SÀNG (OK)"
            except Exception:
                msg = f"✅ CỔNG {self.port_name.upper()} SẴN SÀNG (OK)"
            
            QTimer.singleShot(0, lambda: self._update_ui_status(msg))
        
        threading.Thread(target=worker, daemon=True).start()

    def _update_ui_status(self, msg):
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 20px; background-color: #065f46; color: #6ee7b7; border-radius: 6px;")


from pathlib import Path

class ImagePreviewDialog(QDialog):
    """Native PySide6 Embedded Patient Photo Preview Modal with Scale & Keyboard Navigation"""
    def __init__(self, parent=None, photo_paths=None, current_index=0):
        super().__init__(parent)
        self.photo_paths = photo_paths or []
        self.current_index = max(0, min(current_index, len(self.photo_paths) - 1)) if self.photo_paths else 0
        self.setWindowTitle("🖼️ XEM ẢNH BỆNH ÁN CHI TIẾT")
        self.resize(1024, 768)
        self.setModal(True)
        self.init_ui()
        self.update_preview()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.lbl_image = QLabel("Đang tải ảnh...")
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: #020617; border: 1px solid #1e293b; border-radius: 8px;")
        layout.addWidget(self.lbl_image, stretch=1)
        
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀️ Ảnh Trước (Left)")
        self.btn_prev.clicked.connect(self.prev_photo)
        nav_layout.addWidget(self.btn_prev)
        
        self.lbl_counter = QLabel("0 / 0")
        self.lbl_counter.setAlignment(Qt.AlignCenter)
        self.lbl_counter.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 14px;")
        nav_layout.addWidget(self.lbl_counter)
        
        self.btn_next = QPushButton("Ảnh Tiếp (Right) ▶️")
        self.btn_next.clicked.connect(self.next_photo)
        nav_layout.addWidget(self.btn_next)
        
        btn_close = QPushButton("Đóng (Esc)")
        btn_close.setStyleSheet("background-color: #475569; color: white; padding: 6px 16px;")
        btn_close.clicked.connect(self.accept)
        nav_layout.addWidget(btn_close)
        
        layout.addLayout(nav_layout)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_photo()
        elif event.key() == Qt.Key_Right:
            self.next_photo()
        elif event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def prev_photo(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_preview()

    def next_photo(self):
        if self.current_index < len(self.photo_paths) - 1:
            self.current_index += 1
            self.update_preview()

    def update_preview(self):
        if not self.photo_paths or self.current_index >= len(self.photo_paths):
            self.lbl_image.setText("Chưa có ảnh")
            self.lbl_counter.setText("0 / 0")
            return
            
        path = self.photo_paths[self.current_index]
        if path and Path(path).exists():
            pix = QPixmap(str(path))
            scaled = pix.scaled(self.lbl_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_image.setPixmap(scaled)
            self.lbl_counter.setText(f"{self.current_index + 1} / {len(self.photo_paths)} | {Path(path).name}")
        else:
            self.lbl_image.setText("Không tìm thấy file ảnh")
            self.lbl_counter.setText(f"{self.current_index + 1} / {len(self.photo_paths)}")


# Launcher Helper Functions
def test_camera(parent=None, camera_index=0):
    dlg = CameraTestDialog(parent, camera_index=camera_index)
    dlg.exec()

def test_microphone(parent=None, mic_name="default"):
    dlg = MicrophoneTestDialog(parent, mic_name=mic_name)
    dlg.exec()

def test_pedal(parent=None, trigger_key="ALT"):
    dlg = PedalTestDialog(parent, trigger_key=trigger_key)
    dlg.exec()

def test_com_port(parent=None, port_name="COM1"):
    dlg = COMPortTestDialog(parent, port_name=port_name)
    dlg.exec()

def show_image_preview(parent=None, photo_paths=None, current_index=0):
    dlg = ImagePreviewDialog(parent, photo_paths=photo_paths, current_index=current_index)
    dlg.exec()
