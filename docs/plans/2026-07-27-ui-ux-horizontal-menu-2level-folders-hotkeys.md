# UI/UX Redesign: Horizontal Top Menu, 2-Level Visual Folder Explorer & F1-F11 Hotkeys Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the application UI/UX into a modern top horizontal navigation layout, build a visual 2-level patient folder explorer, and integrate a comprehensive F1-F11 hotkey system for doctors.

**Architecture:** Replace vertical sidebar with top horizontal header bar, build custom `FolderCardWidget` visual cards for Level 1, detailed photo grid view for Level 2, and bind global `QShortcut` / `keyPressEvent` for F1-F11 hotkeys.

**Tech Stack:** Python 3.10+, PySide6, OpenCV, SQLite (WAL mode).

---

### Task 1: Reconstruct MainWindow Layout with Top Horizontal Navigation Bar

**Files:**
- Modify: `main.py:340-435`

**Step 1: Replace vertical sidebar with Top Horizontal Header Bar**
Change `main_layout` from `QHBoxLayout` with 220px sidebar to `QVBoxLayout` with 55px top header bar + `QStackedWidget`.
Add top bar tabs: `F1 📷 Chụp Ảnh`, `F2 📂 Thư Mục`, `F3 👨‍⚕️ Nhân Viên`, `F4 ⚙️ Cài Đặt`, `F7 ✅ Hoàn Thành`, `Esc 🚪 Thoát`.

---

### Task 2: Implement Tab 2 Visual 2-Level Folder Explorer

**Files:**
- Modify: `main.py:565-596`
- Modify: `main.py:833-860`

**Step 1: Build Level 1 Patient Folder Grid Cards**
Create custom visual folder card widget displaying cover thumbnail, Patient ID badge, Name, Birth Year, Photo Count Badge, and Creation Date.

**Step 2: Build Level 2 Detailed Patient Photo Gallery Grid**
Add Breadcrumb navigation (`📁 Tất cả Thư mục > 📂 [Mã BA]`), Back button (`Backspace`), Switch to Capture button, and Export Report button.

**Step 3: Add Fuzzy Search & Camera QR Auto-Filtering**
Support partial text searching by ID/Name/QR string and auto-selecting folder on barcode camera scan.

---

### Task 3: Implement Doctor F1-F11 Hotkey System

**Files:**
- Modify: `main.py:1005-1030`

**Step 1: Bind F1-F11, Space, Delete, Esc, Ctrl+F, Backspace hotkeys**
Register `QShortcut` bindings and `keyPressEvent` overrides in `MainWindow` for instant action execution.
