"""
Demo Voice AI Agent Offline (Tiếng Việt - Máy Cấu Hình Thấp - No Ollama)
Dành cho dự án PatientCaptureApp (VietAnh)
"""

import json
import os
import sys

def check_dependencies():
    """Kiểm tra xem các thư viện cần thiết đã được cài đặt chưa"""
    missing = []
    try:
        import faster_whisper
    except ImportError:
        missing.append("faster-whisper")
    try:
        import llama_cpp
    except ImportError:
        missing.append("llama-cpp-python")
        
    if missing:
        print(f"[CẢNH BÁO] Thiếu các thư viện: {', '.join(missing)}")
        print(f"[HƯỚNG DẪN] Vui lòng chạy lệnh: pip install {' '.join(missing)}")
        return False
    return True

SYSTEM_PROMPT = """Bạn là Trợ lý Voice AI Y tế Offline cho phòng khám VietAnh.
Nhiệm vụ của bạn là lắng nghe yêu cầu giọng nói từ Bác sĩ và trích xuất thành lệnh JSON để hệ thống thực thi.

Nếu Bác sĩ yêu cầu làm thao tác, CHỈ TRẢ VỀ ĐỊNH DẠNG JSON:
- Đặt lịch khám: {"action": "book_appointment", "patient_name": "...", "date": "..."}
- Tạo phiếu xét nghiệm: {"action": "create_lab_order", "patient_name": "...", "test_type": "..."}
- Tạo hồ sơ bệnh nhân: {"action": "create_patient", "name": "...", "age": "..."}

Nếu là câu hỏi thông thường: Trả lời ngắn gọn bằng Tiếng Việt.
"""

def execute_action(action_json):
    """Giả lập hàm thực thi kết nối với database.py / action_registry.py"""
    try:
        data = json.loads(action_json)
        action = data.get("action")
        
        if action == "book_appointment":
            print(f"\n[HỆ THỐNG VIETANH] ---> THỰC THI THÀNH CÔNG:")
            print(f"                     Hành động: Đặt lịch khám")
            print(f"                     Bệnh nhân: {data.get('patient_name')}")
            print(f"                     Ngày: {data.get('date')}\n")
            return f"Đã đặt lịch thành công cho bệnh nhân {data.get('patient_name')} vào ngày {data.get('date')}."
            
        elif action == "create_lab_order":
            print(f"\n[HỆ THỐNG VIETANH] ---> THỰC THI THÀNH CÔNG:")
            print(f"                     Hành động: Tạo phiếu xét nghiệm")
            print(f"                     Bệnh nhân: {data.get('patient_name')}")
            print(f"                     Loại xét nghiệm: {data.get('test_type')}\n")
            return f"Đã tạo phiếu xét nghiệm {data.get('test_type')} cho bệnh nhân {data.get('patient_name')}."
            
    except Exception:
        pass
    return action_json

def run_demo():
    if not check_dependencies():
        return

    from faster_whisper import WhisperModel
    from llama_cpp import Llama

    model_path = "./qwen2.5-3b-instruct-q4_k_m.gguf"
    if not os.path.exists(model_path):
        print(f"[LỖI] Không tìm thấy file model '{model_path}'!")
        print("Vui lòng tải file từ HuggingFace:")
        print("https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf")
        return

    print("--> 1. Đang nạp mô hình STT (Faster-Whisper Small)...")
    stt_model = WhisperModel("small", device="cpu", compute_type="int8")

    print("--> 2. Đang nạp mô hình LLM (llama-cpp-python Qwen 2.5 3B)...")
    llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)

    print("\n=== HỆ THỐNG VOICE AI OFFLINE ĐÃ SẴN SÀNG ===")
    
    # Test câu lệnh giả lập từ bác sĩ
    sample_text = "Tạo phiếu xét nghiệm công thức máu cho bệnh nhân Nguyễn Văn A"
    print(f"\n[Giả lập Bác sĩ nói]: '{sample_text}'")
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sample_text}
    ]
    
    response = llm.create_chat_completion(messages=messages, temperature=0.1)
    output = response['choices'][0]['message']['content'].strip()
    
    print(f"[AI LLM Output]: {output}")
    res = execute_action(output)
    print(f"[Phản hồi Voice Agent]: {res}")

if __name__ == "__main__":
    run_demo()
