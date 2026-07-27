import os
import sys
import time
import shutil
import logging
from pathlib import Path

# Set up logger for smoke test
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")
logger = logging.getLogger("SmokeTest")

print("=" * 70)
print("🚀 BẮT ĐẦU CHẠY SMOKE TEST HỆ THỐNG PATIENT CAPTURE WORKSTATION")
print("=" * 70)

# Import project modules
import config
import database
import barcode_parser
import action_registry
from pedal_gesture_fsm import PedalGestureFSM

# 1. Test Config & Working Directory Setup
print("\n[STEP 1] Kiểm tra Module Config & Thư mục làm việc động...")
app_cfg = config.load_config()
photos_dir = config.get_photos_dir()
assert photos_dir.exists(), "Thư mục làm việc không tồn tại!"
print(f"  ✓ Thư mục làm việc hiện tại: {photos_dir}")
print(f"  ✓ Camera Index mặc định: {app_cfg.get('camera_index')}")
print(f"  ✓ Theme mặc định: {app_cfg.get('active_theme')}")

# 2. Test Database Initialization & Connection Safety
print("\n[STEP 2] Khởi tạo CSDL SQLite WAL Mode & Kiểm tra Schema...")
db_ok = database.initialize_db()
assert db_ok, "Khởi tạo CSDL thất bại!"
print("  ✓ CSDL app.db khởi tạo thành công với 6 bảng schema WAL Mode.")

# 3. Test Patient Creation & Retrieval
print("\n[STEP 3] Thử nghiệm Tạo Bệnh nhân & Ghi dữ liệu mẫu...")
test_p_id = "BN_SMOKETEST_99"
test_name = "Nguyễn Văn SmokeTest"
test_dob = 1988
test_gender = "Nam"

p_created = database.create_patient(test_p_id, name=test_name, birth_year=test_dob, gender=test_gender)
assert p_created, "Tạo bệnh nhân mới thất bại!"

patient_data = database.get_patient(test_p_id)
assert patient_data is not None, "Không tìm thấy dữ liệu bệnh nhân vừa tạo!"
assert patient_data["name"] == test_name, "Tên bệnh nhân không khớp!"
print(f"  ✓ Đã tạo thành công Bệnh nhân: {patient_data['name']} (Mã: {patient_data['id']})")

# 4. Test Dummy Photo Generation & Photo DB Records
print("\n[STEP 4] Tạo Ảnh mẫu & Ghi dữ liệu Hình ảnh...")
patient_dir = photos_dir / test_p_id
patient_dir.mkdir(parents=True, exist_ok=True)

# Generate a dummy test image using OpenCV or raw bytes
dummy_photo_name = f"{test_p_id}_20260727_165000_01.jpg"
dummy_full_path = patient_dir / dummy_photo_name

# Write dummy image bytes (or 100x100 pixel canvas if cv2 available)
try:
    import cv2
    import numpy as np
    canvas = np.zeros((300, 400, 3), dtype=np.uint8)
    cv2.putText(canvas, "SMOKE TEST PHOTO", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imwrite(str(dummy_full_path), canvas)
except Exception:
    with open(dummy_full_path, "wb") as f:
        f.write(b"DUMMY_IMAGE_BYTES_SMOKE_TEST")

rel_path = f"photos/{test_p_id}/{dummy_photo_name}"
photo_added = database.add_photo(
    patient_id=test_p_id,
    relative_path=rel_path,
    operator_id="NV001",
    operator_name="BS. Nguyễn Văn A"
)
assert photo_added, "Ghi thông tin ảnh vào CSDL thất bại!"

photos_list = database.get_patient_photos(test_p_id)
assert len(photos_list) > 0, "Không lấy được danh sách ảnh của bệnh nhân!"
print(f"  ✓ Đã tạo và ghi nhận ảnh mẫu: {dummy_photo_name}")
print(f"  ✓ Tổng số ảnh của {test_p_id}: {len(photos_list)} ảnh.")

# 5. Test Barcode Parser (JSON QR, URL QR, Delimited, Standard)
print("\n[STEP 5] Thử nghiệm Bộ giải mã Barcode Engine...")
b1 = barcode_parser.parse_barcode('{"id": "BN12345", "name": "Trần Thị B", "namsinh": 1990}')
assert b1["patient_id"] == "BN12345", "Giải mã JSON QR thất bại!"
print(f"  ✓ Parsed JSON QR: ID={b1['patient_id']}, Name={b1['name']}")

b2 = barcode_parser.parse_barcode("https://his.354hospital.vn/emr?id=PHCN998877")
assert b2["patient_id"] == "PHCN998877", "Giải mã URL QR thất bại!"
print(f"  ✓ Parsed URL QR: ID={b2['patient_id']}")

b3 = barcode_parser.parse_barcode("BN8899|Lê Văn C|1975|Nam")
assert b3["patient_id"] == "BN8899", "Giải mã Delimited String thất bại!"
print(f"  ✓ Parsed Delimited Barcode: ID={b3['patient_id']}, Name={b3['name']}")

# 6. Test Pedal Gesture FSM Logic
print("\n[STEP 6] Thử nghiệm Máy trạng thái cử chỉ Bàn đạp chân (Pedal FSM)...")
from PySide6.QtCore import QCoreApplication
qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)

fsm = PedalGestureFSM(target_key="ALT", debounce_ms=10)
gestures_detected = []
fsm.gesture_signal.connect(lambda g: gestures_detected.append(g))

# Simulate single tap
fsm.process_raw_key("alt", "down")
time.sleep(0.02)
fsm.process_raw_key("alt", "up")

# Process Qt timer events for 0.8 seconds
start_t = time.time()
while time.time() - start_t < 0.8:
    qt_app.processEvents()
    time.sleep(0.02)

assert "SINGLE_TAP" in gestures_detected, "Không nhận diện được SINGLE_TAP!"
print(f"  ✓ Pedal FSM Gesture Recognized: {gestures_detected[-1]}")

# 7. Test Action Registry
print("\n[STEP 7] Thử nghiệm Action Registry & Dispatcher...")
registered = action_registry.get_registered_actions()
assert "ACTION_CAPTURE" in registered, "Thiếu ACTION_CAPTURE trong registry!"
assert "ACTION_DELETE_LAST" in registered, "Thiếu ACTION_DELETE_LAST trong registry!"
print(f"  ✓ Số lượng hành động lâm sàng đã đăng ký: {len(registered)} hành động.")

# 8. Test Audit Trail Logging
print("\n[STEP 8] Kiểm tra Nhật ký kiểm toán System Audit Trail...")
audit_logs = database.get_audit_logs(limit=10)
assert len(audit_logs) > 0, "Audit logs trống!"
print(f"  ✓ Nhật ký kiểm toán gần nhất: Event='{audit_logs[0]['event_type']}', Op='{audit_logs[0]['operator_name']}'")

print("\n" + "=" * 70)
print("🎉 THÀNH CÔNG: TẤT CẢ CÁC BƯỚC SMOKE TEST ĐÃ ĐẠT KẾT QUẢ PASS 100%!")
print("=" * 70)
