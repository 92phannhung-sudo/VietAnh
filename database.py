import sqlite3
import os
import re
from datetime import datetime
import logging
from pathlib import Path
import config

logger = logging.getLogger("PatientApp")

def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def initialize_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create patients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                name TEXT,
                birth_year INTEGER,
                gender TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create staff table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT,
                department TEXT,
                status TEXT DEFAULT 'ACTIVE'
            )
        """)
        
        # Create photos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                operator_id TEXT,
                operator_name TEXT,
                file_path TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
            )
        """)
        
        # Create audit_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                operator_name TEXT,
                patient_id TEXT,
                details TEXT
            )
        """)

        # Create staff_action_mappings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_action_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                trigger_source TEXT NOT NULL,
                trigger_value TEXT NOT NULL,
                action_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE,
                UNIQUE(staff_id, trigger_source, trigger_value)
            )
        """)
        
        # Create hardware_devices cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hardware_devices (
                device_type TEXT NOT NULL,
                device_name TEXT NOT NULL,
                device_index INTEGER DEFAULT 0,
                device_info TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_type, device_name, device_index)
            )
        """)
        
        # Insert default sample staff if table is empty
        cursor.execute("SELECT COUNT(*) FROM staff")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO staff (id, name, title, department) VALUES ('NV001', 'BS. Nguyễn Văn A', 'Bác sĩ chuyên khoa', 'Khoa PHCN')"
            )
            cursor.execute(
                "INSERT INTO staff (id, name, title, department) VALUES ('NV002', 'KTV. Trần Thị B', 'Kỹ thuật viên', 'Khoa PHCN')"
            )

        # Seed default action mappings for NV001 if empty
        cursor.execute("SELECT COUNT(*) FROM staff_action_mappings WHERE staff_id = 'NV001'")
        if cursor.fetchone()[0] == 0:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            defaults = [
                ("NV001", "PEDAL_GESTURE", "SINGLE_TAP", "ACTION_CAPTURE", ts),
                ("NV001", "PEDAL_GESTURE", "DOUBLE_TAP", "ACTION_DELETE_LAST", ts),
                ("NV001", "PEDAL_GESTURE", "TRIPLE_TAP", "ACTION_NEXT_PATIENT", ts),
                ("NV001", "PEDAL_GESTURE", "LONG_PRESS", "ACTION_VIEW_PHOTO", ts),
                ("NV001", "VOICE_KEYWORD", "chụp", "ACTION_CAPTURE", ts),
                ("NV001", "VOICE_KEYWORD", "xóa", "ACTION_DELETE_LAST", ts),
                ("NV001", "VOICE_KEYWORD", "tiếp", "ACTION_NEXT_PATIENT", ts),
                ("NV001", "VOICE_KEYWORD", "xem", "ACTION_VIEW_PHOTO", ts),
            ]
            cursor.executemany(
                "INSERT INTO staff_action_mappings (staff_id, trigger_source, trigger_value, action_id, updated_at) VALUES (?, ?, ?, ?, ?)",
                defaults
            )
        
        conn.commit()
        conn.close()
        logger.info("[DB] Database initialized successfully with Staff & Audit Log schema.")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error initializing database: {str(e)}", exc_info=True)
        return False

def log_audit_event(event_type, operator_name="", patient_id="", details=""):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO audit_logs (timestamp, event_type, operator_name, patient_id, details) VALUES (?, ?, ?, ?, ?)",
            (ts, event_type, operator_name, patient_id, details)
        )
        conn.commit()
        logger.info(f"[AUDIT_LOG] Event: {event_type} | Op: {operator_name} | Patient: {patient_id} | Details: {details}")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error logging audit event: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def get_full_photo_path(relative_path):
    if not relative_path:
        return None
    p = Path(relative_path)
    if p.is_absolute():
        return p
    return config.get_photos_dir().parent / relative_path

def get_patient(patient_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"[DB_ERROR] Error getting patient {patient_id}: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def create_patient(patient_id, name="", birth_year=None, gender=""):
    conn = None
    try:
        patient_dir = config.get_photos_dir() / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO patients (id, name, birth_year, gender, created_at) VALUES (?, ?, ?, ?, ?)",
            (patient_id, name, birth_year, gender, created_at)
        )
        conn.commit()
        logger.info(f"[DB] Created new patient record: {patient_id}")
        return True
    except sqlite3.IntegrityError:
        (config.get_photos_dir() / patient_id).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error creating patient {patient_id}: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def upsert_patient(patient_id, name="", birth_year=None, gender=""):
    """Ensure patients row exists before photos FK insert (needed at F2 lock, not only F4)."""
    patient_id = (patient_id or "").strip()
    if not patient_id:
        return False
    if get_patient(patient_id):
        return update_patient(patient_id, name or "", birth_year, gender or "")
    return create_patient(patient_id, name=name or "", birth_year=birth_year, gender=gender or "")

def update_patient(patient_id, name, birth_year, gender):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE patients SET name = ?, birth_year = ?, gender = ? WHERE id = ?",
            (name, birth_year, gender, patient_id)
        )
        conn.commit()
        logger.info(f"[DB] Updated patient info: {patient_id}")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error updating patient {patient_id}: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def add_photo(patient_id, relative_path, operator_id="", operator_name=""):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO photos (patient_id, operator_id, operator_name, file_path, captured_at) VALUES (?, ?, ?, ?, ?)",
            (patient_id, operator_id, operator_name, relative_path, captured_at)
        )
        conn.commit()
        
        # Log to audit trail
        log_audit_event("PHOTO_CAPTURE", operator_name=operator_name, patient_id=patient_id, details=f"File: {relative_path}")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error adding photo for {patient_id}: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def delete_photo(photo_id, operator_name=""):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id, file_path FROM photos WHERE id = ?", (photo_id,))
        row = cursor.fetchone()
        
        if row:
            p_id = row["patient_id"]
            rel_path = row["file_path"]
            full_path = get_full_photo_path(rel_path)
            
            cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
            conn.commit()
            
            if full_path and full_path.exists():
                full_path.unlink()
                
            log_audit_event("PHOTO_DELETE", operator_name=operator_name, patient_id=p_id, details=f"Deleted file: {rel_path}")
            logger.info(f"[DB] Deleted photo file and record: {full_path}")
                
        conn.close()
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error deleting photo ID {photo_id}: {str(e)}")
        return False

def get_patient_photos(patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM photos WHERE patient_id = ? ORDER BY captured_at ASC", (patient_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[DB_ERROR] Error fetching photos for {patient_id}: {str(e)}")
        return []

def get_next_photo_index(patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM photos WHERE patient_id = ?", (patient_id,))
        rows = cursor.fetchall()
        conn.close()
        
        max_idx = 0
        for row in rows:
            filename = os.path.basename(row["file_path"])
            match = re.search(r'_(\d+)\.jpg$', filename, re.IGNORECASE)
            if match:
                idx = int(match.group(1))
                if idx > max_idx:
                    max_idx = idx
                    
        return max_idx + 1
    except Exception as e:
        logger.error(f"[DB_ERROR] Error getting max photo index for {patient_id}: {str(e)}")
        return 1

# STAFF FUNCTIONS
def get_staff_list():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staff WHERE status = 'ACTIVE' ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[DB_ERROR] Error fetching staff list: {str(e)}")
        return []

def add_staff(staff_id, name, title="Bác sĩ", department="Khoa PHCN"):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO staff (id, name, title, department) VALUES (?, ?, ?, ?)",
            (staff_id, name, title, department)
        )
        conn.commit()
        conn.close()
        log_audit_event("STAFF_ADD", details=f"Added staff: {name} ({staff_id})")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error adding staff {staff_id}: {str(e)}")
        return False

def delete_staff(staff_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE staff SET status = 'INACTIVE' WHERE id = ?", (staff_id,))
        conn.commit()
        conn.close()
        log_audit_event("STAFF_REMOVE", details=f"Deactivated staff: {staff_id}")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error deactivating staff {staff_id}: {str(e)}")
        return False

# AUDIT LOG FUNCTIONS
def get_audit_logs(limit=100):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[DB_ERROR] Error fetching audit logs: {str(e)}")
        return []

# STAFF ACTION MAPPING FUNCTIONS
def get_staff_action_mappings(staff_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staff_action_mappings WHERE staff_id = ?", (staff_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[DB_ERROR] Error getting action mappings for {staff_id}: {str(e)}")
        return []

def save_staff_action_mapping(staff_id, trigger_source, trigger_value, action_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO staff_action_mappings (staff_id, trigger_source, trigger_value, action_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(staff_id, trigger_source, trigger_value)
            DO UPDATE SET action_id = excluded.action_id, updated_at = excluded.updated_at
        """, (staff_id, trigger_source, trigger_value, action_id, ts))
        conn.commit()
        conn.close()
        logger.info(f"[DB] Saved mapping: {staff_id} | {trigger_source}:{trigger_value} -> {action_id}")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error saving mapping for {staff_id}: {str(e)}")
        return False

def get_mapped_action(staff_id, trigger_source, trigger_value):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT action_id FROM staff_action_mappings WHERE staff_id = ? AND trigger_source = ? AND trigger_value = ?",
            (staff_id, trigger_source, trigger_value)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row["action_id"]
        return None
    except Exception as e:
        logger.error(f"[DB_ERROR] Error getting mapped action for {staff_id}: {str(e)}")
        return None

def save_scanned_hardware_list(device_list):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM hardware_devices")
        for dev in device_list:
            cursor.execute("""
                INSERT OR REPLACE INTO hardware_devices (device_type, device_name, device_index, device_info, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (dev.get("type", "UNKNOWN"), dev.get("name", "Unknown"), dev.get("index", 0), dev.get("info", ""), now_str))
        conn.commit()
        conn.close()
        logger.info(f"[DB] Persisted {len(device_list)} scanned hardware devices into SQLite database cache.")
        return True
    except Exception as e:
        logger.error(f"[DB_ERROR] Error saving scanned hardware list: {str(e)}", exc_info=True)
        return False

def get_cached_hardware_devices(device_type=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if device_type:
            cursor.execute("SELECT * FROM hardware_devices WHERE device_type = ? ORDER BY device_index ASC", (device_type,))
        else:
            cursor.execute("SELECT * FROM hardware_devices ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[DB_ERROR] Error fetching cached hardware devices: {str(e)}", exc_info=True)
        return []
