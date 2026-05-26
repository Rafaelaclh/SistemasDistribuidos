@echo off
echo ============================================
echo   SISTEMA DE INGRESSOS - Iniciando...
echo ============================================
echo.

echo [1/5] Iniciando User Service        (porta 8001)...
start "User Service"        cmd /k "cd user-service && python main.py"

timeout /t 1 /nobreak >nul

echo [2/5] Iniciando Event Service       (porta 8002)...
start "Event Service"       cmd /k "cd event-service && python main.py"

timeout /t 1 /nobreak >nul

echo [3/5] Iniciando Purchase Service    (porta 8003)...
start "Purchase Service"    cmd /k "cd purchase-service && python main.py"

timeout /t 1 /nobreak >nul

echo [4/5] Iniciando Payment Service     (porta 8004)...
start "Payment Service"     cmd /k "cd payment-service && python main.py"

timeout /t 1 /nobreak >nul

echo [5/5] Iniciando Notification Service (porta 8005)...
start "Notification Service" cmd /k "cd notification-service && python main.py"

echo.
echo ============================================
echo   Todos os servicos iniciados!
echo.
echo   User Service:         http://localhost:8001
echo   Event Service:        http://localhost:8002
echo   Purchase Service:     http://localhost:8003
echo   Payment Service:      http://localhost:8004
echo   Notification Service: http://localhost:8005
echo.
echo   Documentacao automatica (Swagger):
echo   http://localhost:8001/docs
echo   http://localhost:8002/docs
echo   http://localhost:8003/docs
echo ============================================
pause
