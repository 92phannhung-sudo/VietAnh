@echo off
chcp 65001 >nul
title Setup Moi Truong Phat Trien - Patient Capture App

echo =========================================================================
echo KHOI TAO MOI TRUONG PHAT TRIEN (DEVELOPMENT SETUP)
echo =========================================================================
echo.

rem 1. Kiem tra Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Chua tim thay Python. Dang tu dong cai dat Python 3.11 qua winget...
    winget install --id Python.Python.3.11 -e --source winget --override "Include_launcher=0 InstallLauncherAllUsers=0 InstallAllUsers=0 /passive /norestart" --accept-source-agreements --accept-package-agreements
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
) else (
    set "PYTHON_EXE=python"
)

rem 2. Khoi tao moi truong ao .venv
if not exist ".venv" (
    echo [*] Dang tao moi truong ao .venv...
    "%PYTHON_EXE%" -E -m venv .venv
)

rem 3. Cai dat cac thu vien phu thuoc
echo [*] Dang cai dat thu vien phu thuoc tu requirements.txt...
.venv\Scripts\python.exe -u -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r requirements.txt

rem 4. Chay Smoke Test xac minh
echo [*] Dang chay kiem tra he thong (Smoke Test)...
.venv\Scripts\python.exe smoke_test.py

echo.
echo =========================================================================
echo [OK] HOAN TAT THIET LAP MOI TRUONG PHAT TRIEN!
echo =========================================================================
pause
