-- Manufacturing Brands table
CREATE TABLE IF NOT EXISTS makes (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);
-- Specific vehicle models and specs table
CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    make_id INT REFERENCES makes(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    engine_cc INT NOT NULL,
    fuel_type VARCHAR(20) DEFAULT 'Diesel',
    seating_capacity INT DEEFAULT 5,
    UNIQUE(make_id, name, engine_cc)
);
-- Base customs valuation by URA table
CREATE TABLE IF NOT EXISTS valuations (
    id BIGSERIAL PRIMARY KEY,
    model_id INT REFERENCES models(id) ON DELETE CASCADE,
    year_of_manufacture INT NOT NULL,
    cif_value_usd NUMERIC(12, 2) NOT NULL,
    UNIQUE(model_id, year_of_manufacture)
);
--Company user login details table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
-- Historic calcs, mapped to user - table
CREATE TABLE IF NOT EXISTS tax_calculations (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    custom_purchase_price_usd NUMERIC(12, 2) NOT NULL,
    calculated_import_duty_ugx NUMERIC(14, 2) NOT NULL,
    calculated_vat_ugx NUMERIC(14, 2) NOT NULL,
    calculated_env_levy_ugx NUMERIC(14, 2),
    total_tax_payable_ugx NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
-- Optimization index for fast search
CREATE INDEX IF NOT EXISTS idx_model_search ON (name);