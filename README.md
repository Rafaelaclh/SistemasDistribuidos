# TicketFlow — Sistema Distribuído de Venda de Ingressos

## Arquitetura

```
Cliente (Postman / curl / frontend.html)
         │
         ▼
  ┌─────────────┐
  │ API Gateway │  :8000  ← valida JWT, round-robin LB, propaga X-Request-ID
  └──────┬──────┘
         │
   ┌─────┴──────────────────┐
   ▼                        ▼                        ▼
user-service           event-service          purchase-service
:8001 / :8011          :8002 / :8012          :8003 / :8013
                                                    │
                                          ┌─────────┴─────────┐
                                          ▼                   ▼
                                   payment-service   notification-service
                                        :8004              :8005
```

## Serviços

| Serviço              | Porta(s)       | Responsabilidade                          |
|----------------------|----------------|-------------------------------------------|
| API Gateway          | 8000           | Roteamento, LB, JWT, tracing              |
| user-service         | 8001 / 8011    | Cadastro, login (retorna JWT)             |
| event-service        | 8002 / 8012    | CRUD de eventos                           |
| purchase-service     | 8003 / 8013    | Compra de ingressos, controle de estoque  |
| payment-service      | 8004           | Mock de gateway de pagamento              |
| notification-service | 8005           | Mock de envio de e-mail                   |

## Requisitos atendidos

| Requisito                          | Implementação                                                      |
|------------------------------------|--------------------------------------------------------------------|
| API Gateway                        | `gateway/main.py` — ponto único de entrada na porta 8000          |
| Load Balancer                      | Round-robin entre 2 instâncias por serviço; failover automático   |
| Múltiplos microsserviços           | 5 serviços independentes                                          |
| Múltiplas instâncias               | user, event e purchase sobem em 2 portas cada                     |
| Banco de dados                     | SQLite com WAL mode em cada serviço                               |
| Comunicação assíncrona             | Threads em background com retry exponencial (payment/notification)|
| Logs estruturados                  | Formato padronizado com timestamp, serviço e request_id           |
| Métricas (latência/status)         | Tabela `metrics` gravada por middleware HTTP em cada serviço      |
| Tracing distribuído                | `X-Request-ID` gerado no gateway e propagado a todos os serviços  |
| Controle de concorrência           | `BEGIN EXCLUSIVE` no SQLite — impede overselling                  |
| Resiliência a falhas               | Retry com backoff 2^n no async; gateway tenta 3x com failover     |
| Idempotência                       | `transaction_id` único — duplicata retorna resposta original      |
| Autenticação (JWT)                 | Login retorna Bearer token; gateway valida antes de rotear        |
| Autorização por perfil             | Rotas de escrita de eventos exigem `role=admin`                   |
| Compra exige login                 | POST /purchases exige token válido                                |
| Gateway de pagamento mockado       | payment-service com taxa de aprovação por método                  |
| E-mail simulado                    | notification-service imprime nos logs                             |

## Instalação

```bash
pip install -r requirements.txt
```

## Iniciando todos os serviços

**Windows** — use o `start.bat` existente.

**Linux/macOS:**
```bash
# Terminal 1 — Gateway
cd gateway && python main.py &

# Terminal 2/3 — User Service (2 instâncias)
cd user-service && python main.py &
cd user-service && python main.py --port 8011 &

# Terminal 4/5 — Event Service (2 instâncias)
cd event-service && python main.py &
cd event-service && python main.py --port 8012 &

# Terminal 6/7 — Purchase Service (2 instâncias)
cd purchase-service && python main.py &
cd purchase-service && python main.py --port 8013 &

# Terminal 8 — Payment Service
cd payment-service && python main.py &

# Terminal 9 — Notification Service
cd notification-service && python main.py &
```

## Exemplos de uso (curl)

### 1. Verificar saúde do sistema
```bash
curl http://localhost:8000/status
```

### 2. Cadastrar usuário
```bash
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"name": "João Silva", "email": "joao@email.com", "password": "123456"}'
```

### 3. Login — obtém o token JWT
```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "joao@email.com", "password": "123456"}'

# Resposta: { "token": "eyJ...", "role": "user", ... }
# Guarde o token para os próximos passos.
TOKEN="eyJ..."
```

### 4. Login como admin (conta criada automaticamente)
```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@tickets.com", "password": "admin123"}'

ADMIN_TOKEN="eyJ..."
```

### 5. Listar eventos (público — sem token)
```bash
curl http://localhost:8000/events
```

### 6. Criar evento (exige admin)
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "Rock in Rio 2027", "event_date": "2027-01-15 20:00:00", "price": 500.00, "available_tickets": 50}'
```

### 7. Alterar preço e quantidade (exige admin)
```bash
curl -X PUT http://localhost:8000/events/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"price": 450.00, "available_tickets": 80}'
```

### 8. Comprar ingresso (exige login)
```bash
curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"event_id": 1, "quantity": 2, "payment_method": "pix"}'
```

### 9. Ver minhas compras
```bash
curl http://localhost:8000/purchases \
  -H "Authorization: Bearer $TOKEN"
```

### 10. Testar idempotência (enviar a mesma transaction_id duas vezes)
```bash
TX="meu-id-unico-123"

curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"event_id\": 1, \"quantity\": 1, \"payment_method\": \"pix\", \"transaction_id\": \"$TX\"}"

# Segunda chamada — retorna a compra já existente sem duplicar
curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"event_id\": 1, \"quantity\": 1, \"payment_method\": \"pix\", \"transaction_id\": \"$TX\"}"
```

## Tracing distribuído

Todo request recebe um `X-Request-ID`. Você pode rastreá-lo nos logs de todos os serviços:

```bash
# Envie um request com ID customizado
curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: meu-trace-abc123" \
  -d '{"event_id": 1, "quantity": 1, "payment_method": "credit_card"}'

# Nos logs de gateway, purchase-service, payment-service e notification-service
# aparecerá: request_id=meu-trace-abc123
```

## Credenciais padrão

| Conta                 | E-mail                 | Senha    | Role  |
|-----------------------|------------------------|----------|-------|
| Administrador padrão  | admin@tickets.com      | admin123 | admin |
