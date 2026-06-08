@echo off
echo Iniciando TicketFlow...

cd /d %~dp0

start "gateway"              cmd /k "cd gateway && python main.py"
timeout /t 2 /nobreak >nul

start "user-service-1"       cmd /k "cd user-service && python main.py"
start "user-service-2"       cmd /k "cd user-service && python main.py --port 8011"
timeout /t 1 /nobreak >nul

start "event-service-1"      cmd /k "cd event-service && python main.py"
start "event-service-2"      cmd /k "cd event-service && python main.py --port 8012"
timeout /t 1 /nobreak >nul

start "purchase-service-1"   cmd /k "cd purchase-service && python main.py"
start "purchase-service-2"   cmd /k "cd purchase-service && python main.py --port 8013"
timeout /t 1 /nobreak >nul

start "payment-service"      cmd /k "cd payment-service && python main.py"
start "notification-service" cmd /k "cd notification-service && python main.py"

timeout /t 3 /nobreak >nul
echo.
echo ============================================================
echo   TicketFlow iniciado!
echo   Abra o arquivo frontend.html no navegador
echo ============================================================
start frontend.html
