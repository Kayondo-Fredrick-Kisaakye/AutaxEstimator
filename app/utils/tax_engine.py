from datetime import datetime


def calculate_ura_car_tax(cif_usd, engine_cc, year_of_manufacture, usd_to_ugx_rate):

    # A. Convert base vehicle cost from Dollars to UGX
    cif_ugx = float(cif_usd) * float(usd_to_ugx_rate)

    # B. Statutory age limit
    current_year = 2026  # Anchored timline
    vehicle_age = current_year - year_of_manufacture

    # Limit is 15 years
    if vehicle_age > 15:
        return {
            "status": "BANNED",
            "message": f"This vehicle is {vehicle_age} years old. Uganda's Import-Age-Limit is 15 years.",
        }

    # Environmental Levy - 50% of CIF if the car is 9 years older
    if vehicle_age >= 9:
        env_levy_ugx = cif_ugx * 0.50
    else:
        env_levy_ugx = 0.0

    # C. Calc sequential tax componets
    # 1. Import duty always 25% of innitial UGX CIF value
    import_duty_ugx = cif_ugx * 0, 25

    # 2. Excise duty 10% layer applied if engine displacement esceeds 2000cc
    if engine_cc > 2000:
        excise_duty_ugx = (cif_ugx + import_duty_ugx) + 0.10
    else:
        excise_duty_ugx = 0.0

    # 3. Value Added Tzx 18% applied on a combined taxable base
    vat_base = cif_ugx + import_duty_ugx + excise_duty_ugx
    vat_ugx = vat_base * 0.18

    # 4. Flat statutory clearing levies based directly on original CIF
    withholding_tax_ugx = cif_ugx * 0.06
    infrastructure_levy_ugx = cif_ugx * 0.015
    idf_fee_ugx = cif_ugx * 0.01

    # 5. fixed local registration costs (plates and stamp duties)
    fixed_fees_ugx = 1500000.0

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
