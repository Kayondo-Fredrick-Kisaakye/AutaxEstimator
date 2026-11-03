-- Manufacturing Brands table
CREATE TABLE IF NOT EXISTS makes (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);
-- Specific vehicle models and specs table
CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    make_id BIGINT REFERENCES makes(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    engine_cc INT NOT NULL,
    fuel_type VARCHAR(20) DEFAULT 'Diesel',
    seating_capacity INT DEFAULT 5,
    UNIQUE(make_id, name, engine_cc)
);
-- Base customs valuation by URA table
CREATE TABLE IF NOT EXISTS valuations (
    id BIGSERIAL PRIMARY KEY,
    model_id BIGINT REFERENCES models(id) ON DELETE CASCADE,
    year_of_manufacture INT NOT NULL,
    cif_value_usd NUMERIC(12, 2) NOT NULL,
    UNIQUE(model_id, year_of_manufacture)
);
--Company user login details table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    bond_name VARCHAR(100) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
-- Historic calcs, mapped to user - table
CREATE TABLE IF NOT EXISTS tax_calculations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    custom_purchase_price_usd NUMERIC(12, 2) NOT NULL,
    calculated_import_duty_ugx NUMERIC(14, 2) NOT NULL,
    calculated_excise_duty_ugx NUMERIC(14, 2) NOT NULL,
    calculated_vat_ugx NUMERIC(14, 2) NOT NULL,
    calculated_env_levy_ugx NUMERIC(14, 2),
    total_tax_payable_ugx NUMERIC(14, 2) NOT NULL,
    engine_cc INT NOT NULL,
    year_of_manufacture INT NOT NULL,
    usd_to_ugx_rate NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
-- Optimization index for fast search
CREATE INDEX IF NOT EXISTS idx_model_search ON models (name);

-- Currency rates used by the estimator
CREATE TABLE IF NOT EXISTS currency_rates (
    id BIGSERIAL PRIMARY KEY,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    rate NUMERIC(14, 4) NOT NULL CHECK (rate > 0),
    source VARCHAR(100) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(base_currency, quote_currency, fetched_at)
);

-- Tax rules can be updated without changing application code
CREATE TABLE IF NOT EXISTS tax_rules (
    id BIGSERIAL PRIMARY KEY,
    import_duty_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.25,
    excise_duty_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.10,
    vat_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.18,
    environmental_levy_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.50,
    withholding_tax_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.06,
    infrastructure_levy_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.015,
    idf_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.01,
    fixed_fees_ugx NUMERIC(14, 2) NOT NULL DEFAULT 1500000,
    age_limit_years INT NOT NULL DEFAULT 15,
    environmental_levy_age INT NOT NULL DEFAULT 9,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    source VARCHAR(255) NOT NULL DEFAULT 'application defaults'
);

INSERT INTO tax_rules (
    import_duty_rate,
    excise_duty_rate,
    vat_rate,
    environmental_levy_rate,
    withholding_tax_rate,
    infrastructure_levy_rate,
    idf_rate,
    fixed_fees_ugx,
    age_limit_years,
    environmental_levy_age,
    effective_from,
    source
)
SELECT 0.25, 0.10, 0.18, 0.50, 0.06, 0.015, 0.01, 1500000,
       15, 9, CURRENT_DATE, 'application defaults'
WHERE NOT EXISTS (SELECT 1 FROM tax_rules);