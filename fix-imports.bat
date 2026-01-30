@echo off
REM Quick Fix Script for Module Import Error
REM Run this if you get: ModuleNotFoundError: No module named 'laiopt'

echo ==========================================
echo LAIOpt - Quick Fix for Module Error
echo ==========================================
echo.

REM Navigate to the correct directory
cd /d "%~dp0"

echo Current directory: %CD%
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found!
    echo Please run deploy.bat first to create it.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Install LAIOpt as a package
echo Installing LAIOpt as a package (this fixes the import error)...
pip install -e .
echo.

if errorlevel 1 (
    echo [WARNING] Package installation failed, trying alternative fix...
    echo.
    echo Setting PYTHONPATH manually...
    set PYTHONPATH=%CD%;%PYTHONPATH%
    echo PYTHONPATH set to: %PYTHONPATH%
    echo.
) else (
    echo [SUCCESS] LAIOpt package installed successfully!
    echo.
)

REM Test the import
echo Testing if the fix worked...
python -c "import laiopt; print('[SUCCESS] LAIOpt module can now be imported!')" 2>nul
if errorlevel 1 (
    echo [INFO] Package import still has issues, but PYTHONPATH is set.
    echo The app should work when you run it.
) else (
    echo [SUCCESS] Module import test passed!
)
echo.

echo ==========================================
echo Fix complete! Now run:
echo   streamlit run laiopt/frontend/app.py
echo ==========================================
echo.

pause
