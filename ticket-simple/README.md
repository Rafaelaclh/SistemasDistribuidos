# 🎟 Sistema de Venda de Ingressos

> UNISUL — Sistemas Distribuídos e Mobile — A3

---

## 📋 Estrutura de portas

| Serviço              | Porta | Descrição                      |
|----------------------|-------|--------------------------------|
| User Service         | 8001  | Cadastro e login               |
| Event Service        | 8002  | Criar e listar eventos         |
| Purchase Service     | 8003  | ⭐ Compra de ingressos          |
| Payment Service      | 8004  | Mock de pagamento              |
| Notification Service | 8005  | Mock de envio de e-mail        |

---

## ⚙️ Instalação (faça uma vez só)

### 1. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 2. Configurar o banco de dados

Abra o MySQL Workbench (ou terminal) e execute o arquivo `init.sql`:

```bash
mysql -u root -p < init.sql
```

Ou cole o conteúdo do `init.sql` direto no Workbench.

### 3. Ajustar senha do MySQL

Abra o arquivo `shared/db.py` e troque `root123` pela sua senha:

```python
DB_CONFIG = {
    "user":     "root",
    "password": "SUA_SENHA_AQUI",   # ← troque aqui
    ...
}
```

Depois copie o `shared/db.py` para dentro de cada pasta de serviço
(ou o script abaixo faz isso automaticamente).

---

## ▶️ Como rodar

### Windows — dê duplo clique em:
```
start.bat
```

### Mac / Linux:
```bash
chmod +x start.sh
./start.sh
```

Isso abre **5 janelas de terminal**, uma para cada serviço.

---

## 🌐 Documentação automática (Swagger)

Com os serviços rodando, acesse no navegador:

- http://localhost:8001/docs — User Service
- http://localhost:8002/docs — Event Service
- http://localhost:8003/docs — Purchase Service

Lá você consegue testar todos os endpoints com interface gráfica!

---

## 📡 Exemplos de uso (Postman ou curl)

### Cadastrar usuário
```
POST http://localhost:8001/register
{
  "name": "João Silva",
  "email": "joao@email.com",
  "password": "123456",
  "role": "user"
}
```

### Login
```
POST http://localhost:8001/login
{
  "email": "admin@tickets.com",
  "password": "admin123"
}
```

### Listar eventos
```
GET http://localhost:8002/events
```

### Criar evento (admin)
```
POST http://localhost:8002/events
{
  "name": "Show do Iron Maiden",
  "event_date": "2026-10-20 21:00:00",
  "price": 250.00,
  "available_tickets": 50,
  "created_by": 1
}
```

### Comprar ingresso
```
POST http://localhost:8003/purchases
{
  "user_id": 2,
  "event_id": 1,
  "quantity": 2,
  "payment_method": "pix"
}
```

> `payment_method` aceita: `pix`, `boleto`, `credit_card`

### Ver minhas compras
```
GET http://localhost:8003/purchases?user_id=2
```

---

## ✅ Requisitos implementados

| Requisito | Como foi feito |
|---|---|
| Múltiplos microsserviços | 5 serviços independentes em portas diferentes |
| Banco de dados | MySQL com tabelas estruturadas |
| Comunicação assíncrona | Purchase-service chama pagamento em thread separada (não bloqueia o usuário) |
| Controle de concorrência | `SELECT FOR UPDATE` no banco — impede overselling |
| Idempotência | `transaction_id` único — compra duplicada é detectada e ignorada |
| Resiliência | Retry automático (3 tentativas) nas chamadas entre serviços |
| Logs estruturados | Todos os serviços logam método, rota, status e tempo de resposta |
| Métricas | Tabela `metrics` no banco registra latência de cada requisição |
| Mock de pagamento | Simula aprovação/rejeição com taxa por método |
| Mock de notificação | Simula envio de e-mail via log no terminal |

---

## 🔑 Usuário admin padrão

```
E-mail: admin@tickets.com
Senha:  admin123
```

---

## 👥 Equipe

- ...
