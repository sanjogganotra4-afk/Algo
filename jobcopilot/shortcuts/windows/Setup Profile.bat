@echo off
REM Double-click to run the setup wizard.
cd /d "%~dp0..\.."
if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
    venv\Scripts\pip install -q --upgrade pip
    venv\Scripts\pip install -q -r requirements.txt
)
venv\Scripts\python -m jobcopilot.setup_wizard
pause
