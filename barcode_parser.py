import re
import json
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("PatientApp")

def sanitize_folder_name(name_str):
    r"""
    Remove or replace characters that are illegal in Windows folder paths:
    \ / : * ? " < > |
    """
    if not name_str:
        return "UNKNOWN_ID"
    # Replace illegal characters with underscores
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', str(name_str).strip())
    # Remove consecutive underscores or trailing spaces/dots
    sanitized = re.sub(r'_+', '_', sanitized).strip(' .')
    return sanitized if sanitized else "UNKNOWN_ID"

def parse_barcode(raw_data):
    """
    Parses arbitrary raw barcode or QR code data from various hospital systems.
    Handles:
    1. JSON QR strings (e.g. {"id": "BN123", "name": "Nguyễn Văn A", "dob": 1952})
    2. URL QR strings (e.g. https://his.hospital.vn/emr?id=BN123&name=Vuong)
    3. Delimited strings (e.g. BN123|Nguyễn Văn A|1952|Nam)
    4. Standard 1D/2D Code strings (e.g. PHCN2647781, KCB-2026-0912)
    """
    if not raw_data:
        return {
            "patient_id": "UNKNOWN",
            "raw_data": "",
            "name": "",
            "birth_year": None,
            "gender": ""
        }

    raw_str = str(raw_data).strip()
    result = {
        "patient_id": sanitize_folder_name(raw_str),
        "raw_data": raw_str,
        "name": "",
        "birth_year": None,
        "gender": ""
    }

    # Case 1: JSON formatted QR
    if raw_str.startswith("{") and raw_str.endswith("}"):
        try:
            data = json.loads(raw_str)
            p_id = data.get("id") or data.get("patient_id") or data.get("mabn") or data.get("maba")
            if p_id:
                result["patient_id"] = sanitize_folder_name(p_id)
            result["name"] = data.get("name") or data.get("hoten") or ""
            
            dob = data.get("birth_year") or data.get("namsinh") or data.get("dob")
            if dob:
                try:
                    result["birth_year"] = int(str(dob)[:4])
                except ValueError:
                    pass
                    
            result["gender"] = data.get("gender") or data.get("gioitinh") or ""
            logger.info(f"[PARSER] Parsed JSON QR: {result['patient_id']}")
            return result
        except Exception as e:
            logger.debug(f"[PARSER] Failed to parse as JSON: {e}")

    # Case 2: URL formatted QR (e.g. https://.../patient?id=BN123)
    if raw_str.startswith("http://") or raw_str.startswith("https://"):
        try:
            parsed_url = urlparse(raw_str)
            params = parse_qs(parsed_url.query)
            p_id = params.get("id", [None])[0] or params.get("mabn", [None])[0] or params.get("maba", [None])[0]
            if p_id:
                result["patient_id"] = sanitize_folder_name(p_id)
            if "name" in params:
                result["name"] = params["name"][0]
            logger.info(f"[PARSER] Parsed URL QR: {result['patient_id']}")
            return result
        except Exception as e:
            logger.debug(f"[PARSER] Failed to parse as URL: {e}")

    # Case 3: Delimited string (e.g. ID|NAME|YOB|GENDER)
    delimiter = None
    if "|" in raw_str:
        delimiter = "|"
    elif ";" in raw_str:
        delimiter = ";"

    if delimiter:
        parts = [p.strip() for p in raw_str.split(delimiter)]
        if len(parts) >= 1 and parts[0]:
            result["patient_id"] = sanitize_folder_name(parts[0])
        if len(parts) >= 2:
            result["name"] = parts[1]
        if len(parts) >= 3:
            try:
                result["birth_year"] = int(parts[2][:4])
            except ValueError:
                pass
        if len(parts) >= 4:
            result["gender"] = parts[3]
            
        logger.info(f"[PARSER] Parsed Delimited Barcode: {result['patient_id']}")
        return result

    # Case 4: Standard Code String (e.g. PHCN2647781)
    logger.info(f"[PARSER] Parsed Standard Barcode: {result['patient_id']}")
    return result
