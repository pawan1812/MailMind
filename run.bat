@echo off
echo =======================================
echo   MailMind OpenEnv v2.0
echo   Email Triage ^& Response AI Agent
echo =======================================
echo.

IF NOT EXIST "venv" (
    echo Creating Python Virtual Environment...
    python -m venv venv
)

echo Activating Virtual Environment...
call venv\Scripts\activate.bat

echo Installing Dependencies...
pip install -r requirements.txt -q

echo.
echo Starting MailMind Server on http://localhost:7860
echo API Docs: http://localhost:7860/docs
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
