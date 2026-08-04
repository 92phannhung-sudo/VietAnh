# NHẬT KÝ HOẠT ĐỘNG DỰ ÁN (WORK LOG)
*Cập nhật tự động bởi Agent - 354 EMR Workstation Redesign*

## [2026-08-04] - Phiên Rà Soát Tỉ Lệ UI/UX Desktop & Dọn Dẹp Figma Canvas
- **Trạng thái chung:** Dọn dẹp hoàn toàn các khung giao diện cũ/lỗi trên Figma. Chuẩn hóa tỉ lệ UI/UX ứng dụng Desktop chuẩn QDarkTheme PySide6.
- **Cơ cấu Giao diện Desktop Chuẩn:**
  1. **Screen 1:** Unified Clinical Cockpit (Bảng điều khiển chính PySide6 QDarkTheme với tỉ lệ Input 38px, Split Live Feed 60% & Baseline Photo 40%).
  2. **Screen 2:** Patient History Grid Search Modal (Thẻ kết quả dạng lưới 3 cột kèm thông tin và ngày khám cũ).
  3. **Screen 3:** System Settings & Hardware Diagnostics Modal (Bảng kiểm chẩn 4 thiết bị phần cứng thực tế F4).

### 1. Các việc đã hoàn thành
- [x] **DỌN DẸP FIGMA CANVAS:** Quét và xóa sạch 8 khung giao diện rác/tạm trên Figma. Chỉ giữ lại 3 màn hình Desktop UI/UX Promax đạt tỷ lệ tiêu chuẩn.
- [x] **CHUẨN HÓA UI/UX DESKTOP (PYSIDE6 QDARKTHEME):** Áp dụng hệ bảng màu QDarkTheme (`#0F172A`, `#1E293B`, `#0284C7`, `#16A34A`, `#334155`, `#F8FAFC`).
- [x] **KIỂM THỬ TDD:** Bộ unit test chạy hoàn toàn **PASS 100% (3/3 tests)**.

### 2. Nợ kỹ thuật phát sinh (Technical Debt)
- [ ] `ponytail: optional auto-reconnect fallback for legacy Vosk grammar on non-standard micro input`
