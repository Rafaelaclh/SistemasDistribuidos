-- ============================================================
-- SISTEMA DE VENDA DE INGRESSOS - Banco de Dados
-- Execute no MySQL Workbench ou via terminal:
--   mysql -u root -p < init.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS tickets_db;
USE tickets_db;

-- ─── Usuários ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(150) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    role       ENUM('admin','user') NOT NULL DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ─── Eventos ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(200) NOT NULL,
    event_date        DATETIME NOT NULL,
    price             DECIMAL(10,2) NOT NULL,
    available_tickets INT NOT NULL,
    created_by        INT NOT NULL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- ─── Compras ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchases (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(36) NOT NULL UNIQUE,
    user_id        INT NOT NULL,
    event_id       INT NOT NULL,
    quantity       INT NOT NULL DEFAULT 1,
    total_price    DECIMAL(10,2) NOT NULL,
    payment_method ENUM('boleto','pix','credit_card') NOT NULL,
    status         ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

-- ─── Métricas (observabilidade) ──────────────────────────────
CREATE TABLE IF NOT EXISTS metrics (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    service     VARCHAR(50) NOT NULL,
    endpoint    VARCHAR(100) NOT NULL,
    method      VARCHAR(10) NOT NULL,
    status_code INT NOT NULL,
    latency_ms  INT NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ─── Admin padrão ────────────────────────────────────────────
-- Senha: admin123
INSERT IGNORE INTO users (name, email, password, role) VALUES
    ('Administrador', 'admin@tickets.com',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBpj2sTZ0Gi2eK', 'admin');

-- ─── Eventos de exemplo ───────────────────────────────────────
INSERT IGNORE INTO events (name, event_date, price, available_tickets, created_by) VALUES
    ('Show do Metallica - São Paulo', '2026-08-15 20:00:00', 350.00, 100, 1),
    ('Festival de Jazz - Floripa',    '2026-09-01 18:00:00', 120.00,  50, 1),
    ('Jogo Flamengo x Palmeiras',     '2026-07-20 16:00:00',  80.00, 200, 1);
