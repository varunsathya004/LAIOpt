@echo off
REM LAIOpt Deployment Script for Windows
REM This script handles local deployment of the LAIOpt application

echo ==========================================
echo LAIOpt - AI-Assisted Chip Layout Optimizer
echo Deployment Script (Windows)
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK] Pip upgraded
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Install LAIOpt as package in development mode
echo Installing LAIOpt as package...
pip install -e . --quiet
if errorlevel 1 (
    echo [WARNING] Could not install LAIOpt as package
    echo [INFO] Will use PYTHONPATH instead
)
echo [OK] Package setup complete
echo.

REM Check if data directory exists
if not exist "laiopt\data" (
    echo Creating data directory...
    mkdir laiopt\data
    echo [OK] Data directory created
)
echo.

REM Run the application
echo ==========================================
echo Starting LAIOpt application...
echo ==========================================
echo.
echo The application will be available at:
echo http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

REM Set PYTHONPATH to include current directory
set PYTHONPATH=%CD%;%PYTHONPATH%

streamlit run laiopt/frontend/app.py

pause
