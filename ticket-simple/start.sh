#!/bin/bash
echo "============================================"
echo "  SISTEMA DE INGRESSOS - Iniciando..."
echo "============================================"

# Para qualquer processo anterior nas portas usadas
for port in 8001 8002 8003 8004 8005; do
  pid=$(lsof -ti tcp:$port 2>/dev/null)
  if [ -n "$pid" ]; then
    echo "Encerrando processo na porta $port (pid $pid)..."
    kill -9 $pid 2>/dev/null
  fi
done

sleep 1

echo "[1/5] User Service        → porta 8001"
cd user-service && python main.py &
cd ..

echo "[2/5] Event Service       → porta 8002"
cd event-service && python main.py &
cd ..

echo "[3/5] Purchase Service    → porta 8003"
cd purchase-service && python main.py &
cd ..

echo "[4/5] Payment Service     → porta 8004"
cd payment-service && python main.py &
cd ..

echo "[5/5] Notification Service → porta 8005"
cd notification-service && python main.py &
cd ..

echo ""
echo "============================================"
echo "  Todos os serviços iniciados!"
echo ""
echo "  User Service:         http://localhost:8001/docs"
echo "  Event Service:        http://localhost:8002/docs"
echo "  Purchase Service:     http://localhost:8003/docs"
echo "  Payment Service:      http://localhost:8004/docs"
echo "  Notification Service: http://localhost:8005/docs"
echo "============================================"
echo ""
echo "Pressione Ctrl+C para encerrar todos."
wait
