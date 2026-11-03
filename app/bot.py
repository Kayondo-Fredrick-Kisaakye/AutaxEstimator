from app.utils.tax_engine import calculate_ura_car_tax


def handle_estimate_command(command, usd_to_ugx_rate):
    # A. Parse a provider-neutral command format for future bot adapters
    values = command.split()
    if len(values) != 3:
        return "Use: estimate CIF_USD ENGINE_CC YEAR_OF_MANUFACTURE"

    try:
        result = calculate_ura_car_tax(values[0], values[1], values[2], usd_to_ugx_rate)
    except (TypeError, ValueError) as exc:
        return str(exc)

    if result["status"] == "BANNED":
        return result["message"]
    return f"Estimated total payable: UGX {result['breakdown']['total_payable_to_ura_ugx']:,}"


if __name__ == "__main__":
    print(
        "Bot adapter ready. Connect a messaging provider to handle incoming commands."
    )
