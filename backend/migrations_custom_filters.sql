-- Agregar tabla de custom filters
CREATE TABLE IF NOT EXISTS custom_filters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    conditions JSONB DEFAULT '{}'::jsonb,
    action VARCHAR(50) DEFAULT 'block',
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    times_triggered INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_custom_filters_active ON custom_filters(is_active);
CREATE INDEX idx_custom_filters_priority ON custom_filters(priority DESC);

-- Insert filtros demo
INSERT INTO custom_filters (name, description, conditions, action, priority, is_active)
VALUES (
    'Bloquear VPNs',
    'Bloquea todo el tráfico que venga de VPN o Proxy',
    '{"is_vpn": true}'::jsonb,
    'block',
    10,
    TRUE
);

INSERT INTO custom_filters (name, description, conditions, action, priority, is_active)
VALUES (
    'Solo USA y Canadá',
    'Permite solo tráfico de Estados Unidos y Canadá',
    '{"countries": ["US", "CA"]}'::jsonb,
    'allow',
    5,
    FALSE
);

COMMENT ON TABLE custom_filters IS 'Filtros personalizados para traffic filtering avanzado';
