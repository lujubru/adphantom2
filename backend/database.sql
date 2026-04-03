-- Traffic Guardian PostgreSQL Database Setup
-- Compatible with pgAdmin4

-- Create database
CREATE DATABASE traffic_guardian;

-- Connect to database
\c traffic_guardian;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- Campaigns table
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    target_url TEXT NOT NULL,
    safe_page_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    daily_click_limit INTEGER DEFAULT 10000,
    clicks_today INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    allowed_countries JSONB DEFAULT '[]'::jsonb,
    allowed_devices JSONB DEFAULT '[]'::jsonb,
    allowed_os JSONB DEFAULT '[]'::jsonb,
    block_empty_referrer BOOLEAN DEFAULT FALSE,
    blacklist_ips JSONB DEFAULT '[]'::jsonb,
    whitelist_ips JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_active ON campaigns(is_active);

-- Clicks table
CREATE TABLE clicks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ip VARCHAR(45) NOT NULL,
    country VARCHAR(10),
    user_agent TEXT,
    device VARCHAR(50),
    os VARCHAR(50),
    browser VARCHAR(50),
    referrer TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    is_vpn BOOLEAN DEFAULT FALSE,
    is_datacenter BOOLEAN DEFAULT FALSE,
    is_blocked BOOLEAN DEFAULT FALSE,
    block_reason VARCHAR(255),
    fingerprint_hash VARCHAR(64),
    behavioral_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_clicks_campaign ON clicks(campaign_id);
CREATE INDEX idx_clicks_ip ON clicks(ip);
CREATE INDEX idx_clicks_fingerprint ON clicks(fingerprint_hash);
CREATE INDEX idx_clicks_created ON clicks(created_at);
CREATE INDEX idx_clicks_blocked ON clicks(is_blocked);

-- AI Pages table
CREATE TABLE ai_pages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    prompt TEXT NOT NULL,
    generated_html TEXT NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_pages_campaign ON ai_pages(campaign_id);

-- Insert demo admin user (password: admin123)
INSERT INTO users (email, hashed_password, is_active)
VALUES (
    'admin@trafficguardian.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYE.xjJx2Oy',
    TRUE
);

-- Insert demo campaign
INSERT INTO campaigns (
    name,
    target_url,
    safe_page_url,
    is_active,
    daily_click_limit,
    allowed_countries,
    allowed_devices,
    block_empty_referrer
)
VALUES (
    'Demo Campaign',
    'https://example.com',
    'https://example.com/safe',
    TRUE,
    10000,
    '["US", "GB", "CA"]'::jsonb,
    '["Desktop", "Mobile"]'::jsonb,
    FALSE
);

-- Function to reset daily clicks (run daily via cron)
CREATE OR REPLACE FUNCTION reset_daily_clicks()
RETURNS void AS $$
BEGIN
    UPDATE campaigns SET clicks_today = 0;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE users IS 'Admin users table';
COMMENT ON TABLE campaigns IS 'Traffic campaigns with targeting rules';
COMMENT ON TABLE clicks IS 'Click tracking and traffic analysis data';
COMMENT ON TABLE ai_pages IS 'AI-generated landing pages';
COMMENT ON COLUMN clicks.behavioral_score IS 'Traffic quality score (0-100, higher is better)';
COMMENT ON COLUMN clicks.fingerprint_hash IS 'SHA256 hash of device fingerprint';

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;