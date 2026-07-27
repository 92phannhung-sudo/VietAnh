@echo off
chcp 65001 >nul
title Gỡ Bỏ Ứng Dụng Chụp Ảnh Bệnh Nhân - Bệnh viện 354

:: 1. Check Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI THIẾU QUYỀN ADMINISTRATOR] Vui lòng nhấp chuột phải và chọn "Run as administrator".
    pause
    exit /b 1
)

echo =========================================================================
echo ĐANG GỠ BỎ ỨNG DỤNG - BỆNH VIỆN QUÂN Y 354
echo =========================================================================
echo.

:: 2. Terminate running instance
taskkill /F /IM PatientCaptureApp.exe /T >nul 2>&1

set "INSTALL_DIR=C:\Program Files\PatientCaptureApp"
set "APPDATA_DIR=%APPDATA%\PatientCaptureApp"
set "DESKTOP_LINK=%USERPROFILE%\Desktop\Chụp ảnh Bệnh nhân - BV 354.lnk"
set "START_LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Chụp ảnh Bệnh nhân - BV 354.lnk"

:: 3. Remove Shortcuts
if exist "%DESKTOP_LINK%" del /F /Q "%DESKTOP_LINK%"
if exist "%START_LINK%" del /F /Q "%START_LINK%"

:: 4. Remove Installation Files
if exist "%INSTALL_DIR%" (
    echo [*] Đang xóa tệp ứng dụng cài đặt...
    rmdir /S /Q "%INSTALL_DIR%"
)

:: 5. Prompt for Database Deletion
echo.
echo [CHÚ Ý] Cơ sở dữ liệu bệnh nhân tại: %APPDATA_DIR%
set /p DEL_DB="Bác sĩ có muốn XÓA TOÀN BỘ CSDL bệnh nhân cũ không? (Y/N - Mặc định N): "
if /i "%DEL_DB%"=="Y" (
    if exist "%APPDATA_DIR%" rmdir /S /Q "%APPDATA_DIR%"
    echo [✓] Đã xóa toàn bộ CSDL và nhật ký hệ thống.
) else (
    echo [✓] ĐÃ GIỮ NGUYÊN CƠ SỞ DỮ LIỆU BỆNH NHÂN.
)

echo.
echo =========================================================================
echo ✅ ĐÃ GỠ BỎ ỨNG DỤNG THÀNH CÔNG!
echo =========================================================================
echo.
pause
