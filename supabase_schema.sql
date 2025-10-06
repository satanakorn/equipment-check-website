-- ============================================
-- Supabase Database Schema for Network Monitoring
-- ============================================

-- Enable Row Level Security
ALTER TABLE IF EXISTS uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS users ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 1. UPLOADS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS uploads (
    id BIGSERIAL PRIMARY KEY,
    upload_date TEXT NOT NULL,
    orig_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    file_size BIGINT,
    file_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_uploads_date ON uploads(upload_date);
CREATE INDEX IF NOT EXISTS idx_uploads_created_at ON uploads(created_at);

-- ============================================
-- 2. ANALYSIS RESULTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGSERIAL PRIMARY KEY,
    analysis_type TEXT NOT NULL, -- 'cpu', 'fan', 'msu', 'line', 'client', 'fiber', 'eol', 'core', 'apo'
    file_id BIGINT REFERENCES uploads(id) ON DELETE CASCADE,
    data JSONB NOT NULL, -- Store analysis results as JSON
    status TEXT DEFAULT 'completed', -- 'processing', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_analysis_type ON analysis_results(analysis_type);
CREATE INDEX IF NOT EXISTS idx_analysis_file_id ON analysis_results(file_id);
CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_results(status);
CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_results(created_at);

-- ============================================
-- 3. REPORTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    report_name TEXT NOT NULL,
    report_type TEXT DEFAULT 'network_inspection', -- 'network_inspection', 'summary', 'custom'
    report_data JSONB NOT NULL, -- Store report data as JSON
    file_ids JSONB, -- Array of file IDs used in this report
    pdf_path TEXT, -- Path to generated PDF file
    status TEXT DEFAULT 'generated', -- 'generating', 'generated', 'failed'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

-- ============================================
-- 4. USERS TABLE (for future authentication)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'user', -- 'admin', 'user', 'viewer'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================
-- 5. NETWORK SITES TABLE (Reference Data)
-- ============================================
CREATE TABLE IF NOT EXISTS network_sites (
    id BIGSERIAL PRIMARY KEY,
    site_name TEXT UNIQUE NOT NULL,
    site_code TEXT UNIQUE,
    location TEXT,
    ip_address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 6. THRESHOLDS TABLE (Reference Data)
-- ============================================
CREATE TABLE IF NOT EXISTS thresholds (
    id BIGSERIAL PRIMARY KEY,
    device_type TEXT NOT NULL, -- 'cpu', 'fan', 'msu', 'line', 'client'
    parameter_name TEXT NOT NULL,
    min_value DECIMAL,
    max_value DECIMAL,
    unit TEXT,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_thresholds_device_type ON thresholds(device_type);
CREATE INDEX IF NOT EXISTS idx_thresholds_parameter ON thresholds(parameter_name);

-- ============================================
-- 7. ALERTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL, -- 'threshold_exceeded', 'device_failure', 'network_issue'
    severity TEXT DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    device_type TEXT,
    site_name TEXT,
    parameter_name TEXT,
    current_value DECIMAL,
    threshold_value DECIMAL,
    message TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(is_resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);

-- ============================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================

-- Allow all operations for authenticated users (adjust as needed)
CREATE POLICY "Enable all operations for authenticated users" ON uploads
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Enable all operations for authenticated users" ON analysis_results
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Enable all operations for authenticated users" ON reports
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Enable all operations for authenticated users" ON users
    FOR ALL USING (auth.role() = 'authenticated');

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_uploads_updated_at BEFORE UPDATE ON uploads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_results_updated_at BEFORE UPDATE ON analysis_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- SAMPLE DATA
-- ============================================

-- Insert sample network sites
INSERT INTO network_sites (site_name, site_code, location, ip_address) VALUES
('HYI-4', 'HYI4', 'Bangkok', '30.10.90.6'),
('Jasmine', 'JAS', 'Bangkok', '30.10.10.6'),
('Phu Nga', 'PNG', 'Phuket', '30.10.30.6'),
('SNI-POI', 'SNI', 'Bangkok', '30.10.50.6'),
('NKS', 'NKS', 'Nakhon Ratchasima', '30.10.70.6'),
('PKT', 'PKT', 'Phuket', '30.10.110.6')
ON CONFLICT (site_name) DO NOTHING;

-- Insert sample thresholds
INSERT INTO thresholds (device_type, parameter_name, min_value, max_value, unit, description) VALUES
('cpu', 'CPU utilization ratio', 0, 90, '%', 'CPU utilization should not exceed 90%'),
('fan', 'FCC Fan Speed', 0, 120, 'Rps', 'FCC fan speed threshold'),
('fan', 'FCPP Fan Speed', 0, 250, 'Rps', 'FCPP fan speed threshold'),
('fan', 'FCPL Fan Speed', 0, 120, 'Rps', 'FCPL fan speed threshold'),
('fan', 'FCPS Fan Speed', 0, 230, 'Rps', 'FCPS fan speed threshold'),
('msu', 'Laser Bias Current', 0, 100, 'mA', 'MSU laser bias current threshold'),
('line', 'BER Threshold', 0, 1e-12, 'ratio', 'Bit Error Rate threshold'),
('client', 'Input Power', -20, 5, 'dBm', 'Client input power range'),
('client', 'Output Power', -15, 5, 'dBm', 'Client output power range')
ON CONFLICT DO NOTHING;
