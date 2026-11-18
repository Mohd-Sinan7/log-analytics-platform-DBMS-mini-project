-- 006_auth_and_rbac.sql
-- Role-Based Access Control (RBAC), User Management, and Dimension Tables

-- 1. Create PostgreSQL Database Roles for RBAC
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'log_admin') THEN
        CREATE ROLE log_admin;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'log_analyst') THEN
        CREATE ROLE log_analyst;
    END IF;
END
$$;

-- 2. Services Dimension Table (Relational Normalization)
CREATE TABLE IF NOT EXISTS services_dim (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(64) UNIQUE NOT NULL,
    tier VARCHAR(32) NOT NULL CHECK (tier IN ('critical', 'standard', 'background')),
    owner_team VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed services
INSERT INTO services_dim (service_name, tier, owner_team) VALUES
('auth', 'critical', 'Security Team'),
('payments', 'critical', 'FinTech Platform'),
('orders', 'critical', 'Checkout Team'),
('inventory', 'standard', 'Warehouse Systems'),
('search', 'standard', 'Catalog Team'),
('notifications', 'background', 'Messaging Ops')
ON CONFLICT (service_name) DO NOTHING;

-- 3. Hosts Dimension Table
CREATE TABLE IF NOT EXISTS hosts_dim (
    host_id SERIAL PRIMARY KEY,
    hostname VARCHAR(64) UNIQUE NOT NULL,
    datacenter VARCHAR(32) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'healthy' CHECK (status IN ('healthy', 'degraded', 'offline'))
);

-- Seed hosts
INSERT INTO hosts_dim (hostname, datacenter, ip_address) VALUES
('host-00', 'us-east-1', '10.0.1.10'),
('host-01', 'us-east-1', '10.0.1.11'),
('host-02', 'us-east-2', '10.0.2.20'),
('host-03', 'us-east-2', '10.0.2.21'),
('host-04', 'eu-west-1', '10.1.1.40'),
('host-05', 'eu-west-1', '10.1.1.41'),
('host-06', 'ap-south-1', '10.2.1.60'),
('host-07', 'ap-south-1', '10.2.1.61')
ON CONFLICT (hostname) DO NOTHING;

-- 4. Users Table (for Web App Authentication & Role Authorization)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('admin', 'analyst')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Passwords:
-- admin: admin123  (SHA-256 / bcrypt hash format)
-- analyst: analyst123
INSERT INTO users (username, password_hash, full_name, role) VALUES
('admin', '$2b$12$e6yqX9y0nBskWpCsqJ7p4.U0d1L9zBqy8bZ8Xo4JjA2h8J2b.gqG6', 'System Administrator', 'admin'),
('analyst', '$2b$12$hC/6e/lI4F3f4rFqIekE4.fG1Uo9bBsy8bZ8Xo4JjA2h8J2b.gqG6', 'Security & Log Analyst', 'analyst')
ON CONFLICT (username) DO NOTHING;

-- 5. Audit Log Table (Tracks User Actions & Administrative Changes)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity VARCHAR(64) NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Apply Database-Level RBAC Permissions
-- Admin Role: Full access to all tables, sequences, functions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO log_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO log_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO log_admin;

-- Analyst Role: Read-only access to logs, dimensions, rollups, and anomalies
-- DENIED access to users, dead_letter, and audit_log
GRANT USAGE ON SCHEMA public TO log_analyst;
GRANT SELECT ON logs, log_counts_minute, anomalies, services_dim, hosts_dim TO log_analyst;
REVOKE ALL PRIVILEGES ON users, dead_letter, audit_log FROM log_analyst;
