@echo off
REM Double-click to start the copilot + dashboard, then open it in your browser.
cd /d "%~dp0..\.."
if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
    venv\Scripts\pip install -q --upgrade pip
    venv\Scripts\pip install -q -r requirements.txt
)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"
venv\Scripts\python -m jobcopilot.orchestrator
