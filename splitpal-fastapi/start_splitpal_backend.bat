REM Start the FastAPI server

call "C:\MyFiles\PythonEnv\.splitpal-env\Scripts\activate.bat"
start "cloudflared" cmd /c "cloudflared tunnel run puru-backend"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
