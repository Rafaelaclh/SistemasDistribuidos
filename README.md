# TicketFlow — Venda de Ingressos Distribuída

Trabalho da disciplina de Sistemas Distribuídos — UNISUL 2026.

O projeto simula uma plataforma de venda de ingressos usando arquitetura de microsserviços. A ideia foi dividir as responsabilidades em serviços separados (usuários, eventos, compras, pagamento e notificação), com um gateway na frente centralizando as requisições e fazendo o balanceamento de carga entre as instâncias.

## Como o sistema funciona

```
Cliente (frontend.html ou curl)
         │
         ▼
  ┌─────────────┐
  │ API Gateway │  :8000
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

O gateway recebe tudo na porta 8000 e redireciona para o serviço correto. Cada serviço principal sobe em duas portas para simular múltiplas instâncias — o gateway alterna entre elas em round-robin e, se uma cair, tenta a outra.

## Serviços

| Serviço              | Porta(s)    | O que faz                                   |
| -------------------- | ----------- | ------------------------------------------- |
| API Gateway          | 8000        | Recebe tudo, valida o JWT, faz o roteamento |
| user-service         | 8001 / 8011 | Cadastro e login (retorna o token JWT)      |
| event-service        | 8002 / 8012 | Criar, editar, deletar e listar eventos     |
| purchase-service     | 8003 / 8013 | Compra de ingressos e controle de estoque   |
| payment-service      | 8004        | Simula aprovação/rejeição do pagamento      |
| notification-service | 8005        | Simula envio de e-mail de confirmação       |

## Instalação

```bash
pip install -r requirements.txt
```

## Rodando o projeto

**Windows:** execute o `start.bat` (Windows) ou `start.sh` (Mac e Linux).

Depois é só abrir o `frontend.html` no navegador ou usar os exemplos abaixo.

## Exemplos de uso

### Verificar se os serviços estão online

```bash
curl http://localhost:8000/status
```

### Cadastrar usuário

```bash
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"name": "João Silva", "email": "joao@email.com", "password": "123456"}'
```

### Login (guarde o token retornado)

```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "joao@email.com", "password": "123456"}'

TOKEN="eyJ..."
```

### Login como admin

```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@tickets.com", "password": "admin123"}'

ADMIN_TOKEN="eyJ..."
```

### Listar eventos (não precisa de token)

```bash
curl http://localhost:8000/events
```

### Criar evento (só admin)

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "Rock in Rio 2027", "event_date": "2027-01-15 20:00:00", "price": 500.00, "available_tickets": 50}'
```

### Editar evento (só admin)

```bash
curl -X PUT http://localhost:8000/events/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"price": 450.00, "available_tickets": 80}'
```

### Deletar evento (só admin)

```bash
curl -X DELETE http://localhost:8000/events/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Comprar ingresso

```bash
curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"event_id": 1, "quantity": 2, "payment_method": "pix"}'
```

### Ver minhas compras

```bash
curl http://localhost:8000/purchases \
  -H "Authorization: Bearer $TOKEN"
```

### Testar idempotência

Manda a mesma `transaction_id` duas vezes — a segunda retorna a compra original sem duplicar.

```bash
TX="teste-123"

curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"event_id\": 1, \"quantity\": 1, \"payment_method\": \"pix\", \"transaction_id\": \"$TX\"}"

curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"event_id\": 1, \"quantity\": 1, \"payment_method\": \"pix\", \"transaction_id\": \"$TX\"}"
```

### Rastrear uma requisição pelos logs

Todo request tem um `X-Request-ID` que aparece nos logs de todos os serviços por onde ele passa.

```bash
curl -X POST http://localhost:8000/purchases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: teste-rastreio-1" \
  -d '{"event_id": 1, "quantity": 1, "payment_method": "credit_card"}'
```

Nos logs do gateway, purchase-service, payment-service e notification-service vai aparecer `request_id=teste-rastreio-1`.

## Credenciais padrão

| E-mail            | Senha    | Perfil |
| ----------------- | -------- | ------ |
| admin@tickets.com | admin123 | admin  |
