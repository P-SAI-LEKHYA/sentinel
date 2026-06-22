@echo off
echo ==============================================
echo   SENTINEL — CRYPTOGRAPHIC WHISTLEBLOWER NET
echo ==============================================
echo.
echo Starting 4 independent network nodes...
echo [1/5] Starting NGO Node (Port 8001)...
start "SENTINEL Node — NGO (8001)" cmd /k "python backend\nodes\node_server.py NGO 8001"

echo [2/5] Starting MEDIA Node (Port 8002)...
start "SENTINEL Node — MEDIA (8002)" cmd /k "python backend\nodes\node_server.py MEDIA 8002"

echo [3/5] Starting OMBUDSMAN Node (Port 8003)...
start "SENTINEL Node — OMBUDSMAN (8003)" cmd /k "python backend\nodes\node_server.py OMBUDSMAN 8003"

echo [4/5] Starting PUBLIC Node (Port 8004)...
start "SENTINEL Node — PUBLIC (8004)" cmd /k "python backend\nodes\node_server.py PUBLIC 8004"

timeout /t 2 /nobreak > nul

echo [5/5] Starting Main Broadcast Server (Port 8000)...
start "SENTINEL Main Server (8000)" cmd /k "python backend\main.py"

echo.
echo Network processes launched.
echo Frontend can be started by running:
echo   cd frontend
echo   npm start
echo.
pause
