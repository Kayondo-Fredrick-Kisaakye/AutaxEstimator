import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from app.currency_sync import fetch_currency_rate
from app.scraper import parse_vehicle_records
from app.utils.tax_engine import calculate_ura_car_tax
from app.web_server import app


class TaxEngineTests(unittest.TestCase):
    def test_calculates_standard_vehicle_taxes(self):
        result = calculate_ura_car_tax(1000, 1500, datetime.now().year - 5, 1000)

        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["breakdown"]["import_duty_ugx"], 250000)
        self.assertEqual(result["breakdown"]["excise_duty_ugx"], 0)

    def test_applies_excise_duty_to_high_engine_vehicle(self):
        result = calculate_ura_car_tax(1000, 2500, datetime.now().year - 5, 1000)

        self.assertEqual(result["breakdown"]["excise_duty_ugx"], 125000)
        self.assertEqual(result["breakdown"]["total_payable_to_ura_ugx"], 2207500)

    def test_rejects_vehicle_over_age_limit(self):
        result = calculate_ura_car_tax(1000, 1500, datetime.now().year - 16, 1000)

        self.assertEqual(result["status"], "BANNED")

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            calculate_ura_car_tax(0, 1500, datetime.now().year, 1000)
        with self.assertRaises(ValueError):
            calculate_ura_car_tax("nan", 1500, datetime.now().year, 1000)

    def test_accepts_updated_tax_rules(self):
        result = calculate_ura_car_tax(
            1000,
            1500,
            datetime.now().year - 5,
            1000,
            {"import_duty_rate": 0.30},
        )

        self.assertEqual(result["breakdown"]["import_duty_ugx"], 300000)

    def test_accepts_database_decimal_tax_rules(self):
        result = calculate_ura_car_tax(
            1000,
            1500,
            datetime.now().year - 5,
            1000,
            {"import_duty_rate": Decimal("0.30")},
        )

        self.assertEqual(result["breakdown"]["import_duty_ugx"], 300000)


class EstimatorRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_estimator_page_and_stylesheet_load(self):
        self.assertEqual(self.client.get("/estimate").status_code, 200)
        with self.client.get("/static/style.css") as stylesheet:
            self.assertEqual(stylesheet.status_code, 200)
            self.assertTrue(stylesheet.content_type.startswith("text/css"))

    def test_estimator_renders_approved_result(self):
        response = self.client.post(
            "/estimate",
            data={
                "cif_usd": "1000",
                "engine_cc": "2500",
                "year_of_manufacture": str(datetime.now().year - 5),
                "usd_to_ugx_rate": "1000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"UGX 2,207,500", response.data)

    def test_estimator_renders_banned_result(self):
        response = self.client.post(
            "/estimate",
            data={
                "cif_usd": "1000",
                "engine_cc": "1500",
                "year_of_manufacture": str(datetime.now().year - 16),
                "usd_to_ugx_rate": "1000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Import not approved", response.data)

    def test_health_reports_missing_database_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)

    def test_post_requests_require_csrf_outside_testing(self):
        app.config["TESTING"] = False
        try:
            response = self.client.post("/login", data={"username": "demo"})
            self.assertEqual(response.status_code, 400)
        finally:
            app.config["TESTING"] = True


class IntegrationInputTests(unittest.TestCase):
    def test_currency_payload_is_validated(self):
        with patch("app.currency_sync.urlopen") as open_url:

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def read(self):
                    return b'{"rate": 3700}'

            open_url.return_value = FakeResponse()
            self.assertEqual(fetch_currency_rate("https://example.test/rate"), 3700)

    def test_vehicle_records_require_expected_fields(self):
        records = parse_vehicle_records(
            '[{"make": "Toyota", "model": "Aqua", "engine_cc": 1500, '
            '"year_of_manufacture": 2022, "cif_value_usd": 10000}]'
        )

        self.assertEqual(records[0]["make"], "Toyota")
        with self.assertRaises(ValueError):
            parse_vehicle_records('[{"make": "Toyota"}]')


if __name__ == "__main__":
    unittest.main()
