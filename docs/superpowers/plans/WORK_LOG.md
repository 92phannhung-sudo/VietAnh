# NHẬT KÝ HOẠT ĐỘNG DỰ ÁN (WORK LOG)
*Cập nhật tự động bởi Agent - 354 EMR Workstation Redesign*

## [2026-08-04] - Phiên Tinh Chỉnh Giao Diện theo Yêu Cầu (Giữ Ô Ảnh Baseline trên Màn hình 1)
- **Trạng thái chung:** Hoàn thành giữ lại ô Ảnh Baseline so sánh song song trên Màn hình 1 (Unified Clinical Cockpit).
- **Cấu trúc Màn hình 1:** Khung Live Stream Camera 60% (bên trái) + Ô So sánh Ảnh Baseline cũ 40% (bên phải) + Thanh cuộn Filmstrip dưới cùng.

### 1. Các việc đã hoàn thành
- [x] **CẬP NHẬT FIGMA CANVAS:** Đã vẽ trực tiếp Khung giao diện mới **`Screen 1: Unified Clinical Cockpit (WITH BASELINE)`** lên phần mềm Figma Desktop qua MCP Server.
- [x] **CẬP NHẬT PYSIDE6:** Cập nhật `src/ui_clinical_cockpit.py` giữ lại ô so sánh Baseline và tự động cập nhật khi nạp hồ sơ bệnh nhân.
- [x] **KIỂM THỬ TDD:** Chạy lại toàn bộ unit tests $\rightarrow$ **PASS 100% (3/3 tests)**.

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- [ ] `ponytail: optional auto-reconnect fallback for legacy Vosk grammar on non-standard micro input`
