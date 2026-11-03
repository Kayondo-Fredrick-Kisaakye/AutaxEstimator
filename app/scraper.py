import csv
import io
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_source(source_url, timeout=15):
    # A. Fetch an approved source with an identifiable client header
    request = Request(source_url, headers={"User-Agent": "AutaxEstimator/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("The configured data source could not be reached.") from exc


def parse_vehicle_records(payload, source_format="json"):
    # B. Parse only structured records before any database update
    if source_format == "csv":
        records = list(csv.DictReader(io.StringIO(payload)))
    else:
        records = json.loads(payload)

    if not isinstance(records, list):
        raise ValueError("The source must contain a list of vehicle records.")
    required_fields = {
        "make",
        "model",
        "engine_cc",
        "year_of_manufacture",
        "cif_value_usd",
    }
    if any(not required_fields.issubset(record) for record in records):
        raise ValueError("Every vehicle record must contain the required fields.")
    return records


def fetch_vehicle_records(source_url, source_format="json"):
    # C. Return validated records for an approved importer to persist
    return parse_vehicle_records(fetch_source(source_url), source_format)


if __name__ == "__main__":
    source_url = os.environ.get("VEHICLE_DATA_URL")
    source_format = os.environ.get("VEHICLE_DATA_FORMAT", "json")
    if not source_url:
        raise SystemExit("VEHICLE_DATA_URL is required.")
    records = fetch_vehicle_records(source_url, source_format)
    print(f"Validated {len(records)} vehicle records")
