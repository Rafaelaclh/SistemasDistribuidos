#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Iniciando TicketFlow em $DIR"

cd "$DIR/gateway"              && python main.py &
sleep 2

cd "$DIR/user-service"         && python main.py &
cd "$DIR/user-service"         && python main.py --port 8011 &
sleep 1

cd "$DIR/event-service"        && python main.py &
cd "$DIR/event-service"        && python main.py --port 8012 &
sleep 1

cd "$DIR/purchase-service"     && python main.py &
cd "$DIR/purchase-service"     && python main.py --port 8013 &
sleep 1

cd "$DIR/payment-service"      && python main.py &
cd "$DIR/notification-service" && python main.py &

echo ""
echo "============================================================"
echo "  TicketFlow iniciado! Abra frontend.html no navegador"
echo "============================================================"
wait
