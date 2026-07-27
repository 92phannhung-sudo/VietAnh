import os
import shutil
import zipfile
import subprocess
from pathlib import Path

def build_package():
    print("=========================================================================")
    print("BUILDING OFFLINE INSTALLER PACKAGE - 354 MILITARY HOSPITAL EMR APP")
    print("=========================================================================")
    
    root_dir = Path(__file__).parent.resolve()
    dist_dir = root_dir / "dist"
    pkg_dir = dist_dir / "PatientCaptureApp_v1.0_Offline"
    app_dist_dir = pkg_dir / "app_dist"
    
    # 1. Clean previous build folders
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Run PyInstaller
    print("[1/4] Running PyInstaller build...")
    pyinstaller_cmd = [
        str(root_dir / ".venv" / "Scripts" / "pyinstaller.exe"),
        "PatientCaptureApp.spec",
        "--clean",
        "--noconfirm"
    ]
    
    result = subprocess.run(pyinstaller_cmd, cwd=root_dir)
    if result.returncode != 0:
        print("[ERROR] PyInstaller build failed!")
        return False
        
    print("[OK] PyInstaller build completed successfully.")
    
    # 3. Copy compiled output into app_dist
    built_app = dist_dir / "PatientCaptureApp"
    if not built_app.exists():
        print("[ERROR] Built output directory not found!")
        return False
        
    print("[2/4] Assembling installer package layout...")
    shutil.copytree(built_app, app_dist_dir, dirs_exist_ok=True)
    
    # Clean temporary build folders immediately to save disk space
    if built_app.exists():
        shutil.rmtree(built_app, ignore_errors=True)
    build_temp = root_dir / "build"
    if build_temp.exists():
        shutil.rmtree(build_temp, ignore_errors=True)
        
    # 4. Copy admin installer scripts into package root
    install_script = root_dir / "install_admin.bat"
    uninstall_script = root_dir / "uninstall_admin.bat"
    
    if install_script.exists():
        shutil.copy2(install_script, pkg_dir / "install_admin.bat")
    if uninstall_script.exists():
        shutil.copy2(uninstall_script, pkg_dir / "uninstall_admin.bat")
        
    # 5. Create distribution zip archive if disk space allows
    zip_path = dist_dir / "PatientCaptureApp_v1.0_Offline.zip"
    if zip_path.exists():
        zip_path.unlink()
        
    print("[3/4] Creating distribution zip archive...")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(pkg_dir):
                for file in files:
                    abs_path = Path(root) / file
                    rel_path = abs_path.relative_to(dist_dir)
                    zipf.write(abs_path, rel_path)
    except Exception as e:
        print(f"[NOTE] Zip compression skipped or low space: {e}")
        print(f"[NOTE] Uncompressed folder 'dist/PatientCaptureApp_v1.0_Offline' is ready for USB copy!")
                
    print("[4/4] Package assembly completed successfully!")
    print("=========================================================================")
    print(f"[OK] PACKAGE LOCATION: {zip_path}")
    print(f"     UNCOMPRESSED FOLDER: {pkg_dir}")
    print("=========================================================================")
    return True

if __name__ == "__main__":
    build_package()
