@echo off
echo ============================================
echo   TICKETFLOW - Iniciando todos os servicos
echo ============================================
echo.

set ROOT=%~dp0

echo [1/9] API Gateway + Load Balancer  (porta 8000)
start "Gateway :8000"          cmd /k "cd /d %ROOT%gateway && python main.py"
timeout /t 2 /nobreak >nul

echo [2/9] User Service - instancia 1   (porta 8001)
start "User :8001"             cmd /k "cd /d %ROOT%user-service && python main.py"
timeout /t 1 /nobreak >nul

echo [3/9] User Service - instancia 2   (porta 8011)
start "User :8011"             cmd /k "cd /d %ROOT%user-service && python main.py --port 8011"
timeout /t 1 /nobreak >nul

echo [4/9] Event Service - instancia 1  (porta 8002)
start "Event :8002"            cmd /k "cd /d %ROOT%event-service && python main.py"
timeout /t 1 /nobreak >nul

echo [5/9] Event Service - instancia 2  (porta 8012)
start "Event :8012"            cmd /k "cd /d %ROOT%event-service && python main.py --port 8012"
timeout /t 1 /nobreak >nul

echo [6/9] Purchase Service - instancia 1 (porta 8003)
start "Purchase :8003"         cmd /k "cd /d %ROOT%purchase-service && python main.py"
timeout /t 1 /nobreak >nul

echo [7/9] Purchase Service - instancia 2 (porta 8013)
start "Purchase :8013"         cmd /k "cd /d %ROOT%purchase-service && python main.py --port 8013"
timeout /t 1 /nobreak >nul

echo [8/9] Payment Service (mock)        (porta 8004)
start "Payment :8004"          cmd /k "cd /d %ROOT%payment-service && python main.py"
timeout /t 1 /nobreak >nul

echo [9/9] Notification Service (mock)   (porta 8005)
start "Notification :8005"     cmd /k "cd /d %ROOT%notification-service && python main.py"
timeout /t 2 /nobreak >nul

echo.
echo ============================================
echo   Tudo iniciado!
echo.
echo   Abra o frontend.html no navegador.
echo.
echo   Gateway (entrada unica): http://localhost:8000
echo   Status dos servicos:     http://localhost:8000/status
echo ============================================
pause
