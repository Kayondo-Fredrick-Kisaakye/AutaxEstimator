from datetime import datetime
from math import isfinite


DEFAULT_TAX_RULES = {
    "import_duty_rate": 0.25,
    "excise_duty_rate": 0.10,
    "vat_rate": 0.18,
    "environmental_levy_rate": 0.50,
    "withholding_tax_rate": 0.06,
    "infrastructure_levy_rate": 0.015,
    "idf_rate": 0.01,
    "fixed_fees_ugx": 1500000.0,
    "age_limit_years": 15,
    "environmental_levy_age": 9,
}


def calculate_ura_car_tax(
    cif_usd,
    engine_cc,
    year_of_manufacture,
    usd_to_ugx_rate,
    tax_rules=None,
):

    # A. Convert and validate the base vehicle values
    cif_usd = float(cif_usd)
    engine_cc = int(engine_cc)
    year_of_manufacture = int(year_of_manufacture)
    usd_to_ugx_rate = float(usd_to_ugx_rate)
    tax_rules = {**DEFAULT_TAX_RULES, **(tax_rules or {})}
    for rule_name in (
        "import_duty_rate",
        "excise_duty_rate",
        "vat_rate",
        "environmental_levy_rate",
        "withholding_tax_rate",
        "infrastructure_levy_rate",
        "idf_rate",
        "fixed_fees_ugx",
    ):
        tax_rules[rule_name] = float(tax_rules[rule_name])
    tax_rules["age_limit_years"] = int(tax_rules["age_limit_years"])
    tax_rules["environmental_levy_age"] = int(tax_rules["environmental_levy_age"])

    if (
        not isfinite(cif_usd)
        or not isfinite(usd_to_ugx_rate)
        or cif_usd <= 0
        or engine_cc <= 0
        or usd_to_ugx_rate <= 0
    ):
        raise ValueError(
            "CIF, engine capacity, and exchange rate must be greater than zero."
        )

    # B. Statutory age limit
    current_year = datetime.now().year
    if year_of_manufacture > current_year:
        raise ValueError("Year of manufacture cannot be in the future.")

    cif_ugx = cif_usd * usd_to_ugx_rate
    vehicle_age = current_year - year_of_manufacture

    # Limit is 15 years
    if vehicle_age > tax_rules["age_limit_years"]:
        return {
            "status": "BANNED",
            "message": (
                f"This vehicle is {vehicle_age} years old. Uganda's "
                f"Import-Age-Limit is {tax_rules['age_limit_years']} years."
            ),
        }

    # Environmental Levy - applies when the car reaches the configured age
    if vehicle_age >= tax_rules["environmental_levy_age"]:
        env_levy_ugx = cif_ugx * tax_rules["environmental_levy_rate"]
    else:
        env_levy_ugx = 0.0

    # C. Calc sequential tax components
    # 1. Import duty always 25% of initial UGX CIF value
    import_duty_ugx = cif_ugx * tax_rules["import_duty_rate"]

    # 2. Excise duty 10% layer applied if engine displacement exceeds 2000cc
    if engine_cc > 2000:
        excise_duty_ugx = (cif_ugx + import_duty_ugx) * tax_rules["excise_duty_rate"]
    else:
        excise_duty_ugx = 0.0

    # 3. Value Added Tax 18% applied on a combined taxable base
    vat_base = cif_ugx + import_duty_ugx + excise_duty_ugx
    vat_ugx = vat_base * tax_rules["vat_rate"]

    # 4. Flat statutory clearing levies based directly on original CIF
    withholding_tax_ugx = cif_ugx * tax_rules["withholding_tax_rate"]
    infrastructure_levy_ugx = cif_ugx * tax_rules["infrastructure_levy_rate"]
    idf_fee_ugx = cif_ugx * tax_rules["idf_rate"]

    # 5. fixed local registration costs (plates and stamp duties)
    fixed_fees_ugx = tax_rules["fixed_fees_ugx"]

    # D. Aggregate the entire stack
    total_customs_taxes = (
        import_duty_ugx
        + excise_duty_ugx
        + vat_ugx
        + withholding_tax_ugx
        + infrastructure_levy_ugx
        + idf_fee_ugx
        + env_levy_ugx
    )
    total_payable_ugx = total_customs_taxes + fixed_fees_ugx

    return {
        "status": "APPROVED",
        "breakdown": {
            "cif_value_ugx": round(cif_ugx),
            "import_duty_ugx": round(import_duty_ugx),
            "excise_duty_ugx": round(excise_duty_ugx),
            "vat_ugx": round(vat_ugx),
            "environmental_levy_ugx": round(env_levy_ugx),
            "withholding_tax_ugx": round(withholding_tax_ugx),
            "infrastructure_levy_ugx": round(infrastructure_levy_ugx),
            "idf_fee_ugx": round(idf_fee_ugx),
            "fixed_fees_ugx": round(fixed_fees_ugx),
            "total_payable_to_ura_ugx": round(total_payable_ugx),
        },
    }
