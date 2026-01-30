@echo off
REM Simple Run Script - Use this to start LAIOpt
REM This script properly sets up the Python path

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run deploy.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Set Python path to current directory
set PYTHONPATH=%CD%;%PYTHONPATH%

echo Starting LAIOpt...
echo Access at: http://localhost:8501
echo.

streamlit run laiopt/frontend/app.py

pause
