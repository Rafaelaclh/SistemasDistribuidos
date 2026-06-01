# 🎟 TicketFlow — Sistema Distribuído de Venda de Ingressos
> UNISUL — Sistemas Distribuídos e Mobile — A3

---

## 📦 O que instalar (apenas uma vez)

### 1. Python 3.10 ou superior
Baixe em: https://www.python.org/downloads/
> ⚠ Durante a instalação, marque **"Add Python to PATH"**

### 2. Instalar as bibliotecas
Abra o terminal (cmd) na pasta do projeto e execute:
```
pip install -r requirements.txt
```

Não precisa instalar banco de dados — o SQLite já vem com o Python
e cria o arquivo `banco.db` automaticamente na primeira execução.

---

## ▶️ Como rodar

Dê duplo clique em `start.bat` — abre 9 janelas de terminal.

Aguarde todos os serviços iniciarem (uns 5 segundos).

---

## 🧪 Como testar — Postman ou Swagger

### Opção 1 — Swagger (mais visual, só abrir no navegador)
```
http://localhost:8000/docs
```

### Opção 2 — Postman

**1. Login (obter token):**
```
POST http://localhost:8000/users/login
Body: { "email": "admin@tickets.com", "password": "admin123" }
```
Copie o token retornado e use nos próximos requests como:
```
Header → Authorization: Bearer SEU_TOKEN
```

**2. Listar eventos (público):**
```
GET http://localhost:8000/events
```

**3. Criar evento (admin):**
```
POST http://localhost:8000/events
Authorization: Bearer SEU_TOKEN
Body: {
  "name": "Show do Iron Maiden",
  "event_date": "2026-10-20 21:00:00",
  "price": 250.00,
  "available_tickets": 50
}
```

**4. Editar evento (admin):**
```
PUT http://localhost:8000/events/1
Authorization: Bearer SEU_TOKEN
Body: { "price": 300.00, "available_tickets": 80 }
```

**5. Cadastrar usuário:**
```
POST http://localhost:8000/users/register
Body: {
  "name": "João Silva",
  "email": "joao@email.com",
  "password": "123456"
}
```

**6. Comprar ingresso:**
```
POST http://localhost:8000/purchases
Authorization: Bearer SEU_TOKEN
Body: {
  "event_id": 1,
  "quantity": 2,
  "payment_method": "pix"
}
```
> payment_method aceita: `pix`, `boleto`, `credit_card`

**7. Ver minhas compras:**
```
GET http://localhost:8000/purchases
Authorization: Bearer SEU_TOKEN
```

**8. Status de todos os serviços:**
```
GET http://localhost:8000/status
```

---

## 🏗 Arquitetura

```
         CLIENTE (Postman / Swagger)
                    │
             ┌──────▼──────┐
             │ API GATEWAY │  porta 8000
             │ + LOAD BAL. │  round-robin entre instâncias
             └──┬───┬───┬──┘
                │   │   │
   ┌────────────▼┐ ┌▼──────────┐ ┌▼──────────────┐
   │user-service │ │event-serv.│ │purchase-service│
   │ :8001 :8011 │ │:8002 :8012│ │  :8003  :8013  │
   └─────────────┘ └───────────┘ └───────┬────────┘
                                         │ (async)
                        ┌────────────────┴──────────────┐
               ┌────────▼────────┐       ┌──────────────▼──────┐
               │payment-service  │       │notification-service  │
               │  :8004 (mock)   │       │    :8005 (mock)      │
               └─────────────────┘       └─────────────────────┘
                        │                        │
                 ┌──────▼────────────────────────▼──────┐
                 │            SQLite (banco.db)           │
                 └───────────────────────────────────────┘
```

---

## 📡 Portas

| Serviço                 | Porta 1 | Porta 2 |
|-------------------------|---------|---------|
| API Gateway             | 8000    | —       |
| User Service            | 8001    | 8011    |
| Event Service           | 8002    | 8012    |
| Purchase Service        | 8003    | 8013    |
| Payment Service (mock)  | 8004    | —       |
| Notification Service    | 8005    | —       |

---

## ✅ Requisitos do professor atendidos

| Requisito                  | Implementação                                         |
|----------------------------|-------------------------------------------------------|
| API Gateway                | `gateway/main.py` porta 8000                          |
| Load Balancer              | Round-robin entre 2 instâncias de cada serviço        |
| Banco de dados             | SQLite — `banco.db` criado automaticamente            |
| Múltiplos microsserviços   | 5 serviços independentes                              |
| Múltiplas instâncias       | user, event e purchase em 2 portas cada               |
| Comunicação assíncrona     | Thread separada para pagamento e notificação          |
| Logs estruturados          | Todos os serviços com request_id rastreável           |
| Métricas                   | Tabela `metrics` com latência por requisição          |
| Controle de concorrência   | `BEGIN EXCLUSIVE` no SQLite — sem overselling         |
| Idempotência               | `transaction_id` único — rejeita compra duplicada     |
| Resiliência                | Retry 3x com backoff exponencial entre serviços       |
| Mock pagamento             | Aprova/rejeita com taxa por método                    |
| Mock notificação           | Simula e-mail via log no terminal                     |
| Autenticação JWT           | Token validado no gateway em rotas protegidas         |

---

## 🔑 Login padrão

```
E-mail: admin@tickets.com
Senha:  admin123
```
