@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [MyStat API] Creating virtual environment...
    python -m venv .venv
)
call ".venv\Scripts\activate.bat"
rem Залежності ставляться без --upgrade (версії фіксуйте в requirements.txt через ==)
pip install -q -r requirements.txt

echo.
echo ============================================================
echo  MyStat API (FastAPI)
echo  Swagger UI : http://127.0.0.1:8000/docs   ^(Try it out^)
echo  ReDoc      : http://127.0.0.1:8000/redoc
echo  Mode       : mock by default; proxy to real API via:
echo               set MYSTAT_MODE=proxy
echo               ^(token: Authorize button in Swagger or Authorization header^)
echo ============================================================
echo.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
