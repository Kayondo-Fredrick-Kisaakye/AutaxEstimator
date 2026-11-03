import unittest
from datetime import datetime

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


if __name__ == "__main__":
    unittest.main()
