@echo off
chcp 65001 >nul
title Cài Đặt Ứng Dụng Chụp Ảnh Bệnh Nhân - Bệnh viện 354

:: 1. Check Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo =========================================================================
    echo [LỖI THIẾU QUYỀN ADMINISTRATOR]
    echo.
    echo Vui lòng nhấp chuột phải vào tệp 'install_admin.bat' và chọn:
    echo "Run as administrator" (Chạy dưới quyền Quản trị viên)
    echo =========================================================================
    echo.
    pause
    exit /b 1
)

echo =========================================================================
echo ĐANG THỰC HIỆN CÀI ĐẶT TỰ ĐỘNG - BỆNH VIỆN QUÂN Y 354
echo =========================================================================
echo.

:: 2. Terminate running instance if any
echo [*] Đang đóng ứng dụng cũ nếu đang chạy...
taskkill /F /IM PatientCaptureApp.exe /T >nul 2>&1

:: 3. Target Installation Directories
set "INSTALL_DIR=C:\Program Files\PatientCaptureApp"
set "APPDATA_DIR=%APPDATA%\PatientCaptureApp"

echo [*] Tạo thư mục cài đặt hệ thống: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: 4. Copy Standalone Application Package
echo [*] Đang sao chép các tệp chương trình trọn gói...
xcopy "%~dp0app_dist\*" "%INSTALL_DIR%\" /E /I /Y /Q >nul

:: 5. Database Persistence Guard
echo [*] Kiểm tra cơ sở dữ liệu bệnh nhân (%APPDATA_DIR%)...
if not exist "%APPDATA_DIR%" (
    mkdir "%APPDATA_DIR%"
)

if exist "%APPDATA_DIR%\patients.db" (
    echo [✓] Đã phát hiện Cơ sở dữ liệu cũ. GIỮ NGUYÊN 100%% CSDL (KHÔNG GHI ĐÈ).
) else (
    echo [✓] Khởi tạo Cơ sở dữ liệu mới cho hệ thống.
)

:: 6. Create Desktop & Start Menu Shortcuts via VBScript
echo [*] Đang tạo lối tắt (Shortcut) ngoài Desktop & Start Menu...
set "VBS_SCRIPT=%TEMP%\create_shortcuts.vbs"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLink = oWS.SpecialFolders("Desktop") ^& "\Chụp ảnh Bệnh nhân - BV 354.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLink) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%INSTALL_DIR%\PatientCaptureApp.exe" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS_SCRIPT%"
echo oLink.Description = "Phần mềm Quản lý & Chụp ảnh Bệnh nhân - Bệnh viện 354" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

echo sMenu = oWS.SpecialFolders("StartMenu") ^& "\Programs\Chụp ảnh Bệnh nhân - BV 354.lnk" >> "%VBS_SCRIPT%"
echo Set oLinkMenu = oWS.CreateShortcut(sMenu) >> "%VBS_SCRIPT%"
echo oLinkMenu.TargetPath = "%INSTALL_DIR%\PatientCaptureApp.exe" >> "%VBS_SCRIPT%"
echo oLinkMenu.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS_SCRIPT%"
echo oLinkMenu.Save >> "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%"
if exist "%VBS_SCRIPT%" del "%VBS_SCRIPT%"

echo.
echo =========================================================================
echo ✅ CÀI ĐẶT HOÀN TẤT THÀNH CÔNG!
echo - Vị trí cài đặt: %INSTALL_DIR%
echo - Cơ sở dữ liệu:  %APPDATA_DIR%\patients.db
echo - Đã tạo Icon Shortcut trên Màn hình chính (Desktop) & Start Menu.
echo =========================================================================
echo.
set /p RUN_NOW="Bác sĩ có muốn khởi chạy ứng dụng ngay bây giờ không? (Y/N): "
if /i "%RUN_NOW%"=="Y" (
    start "" "%INSTALL_DIR%\PatientCaptureApp.exe"
)

pause
