"""Read shipment data for the local web app."""

import csv
import json
import math
from pathlib import Path
import traceback


SHIPMENTS_SOURCE = "data/reference/shipments.csv"
THRESHOLDS_SOURCE = "data/sop/thresholds.json"
DETAIL_PREFIX = "/api/shipments/"
NOT_FOUND = 404, {"error": "API endpoint not found"}


def read_logger(root, logger_file):
    logger = {"path": logger_file, "found": False, "readings": []}
    path = (root / logger_file).resolve()
    if not path.is_relative_to((root / "data/raw").resolve()):
        return logger
    try:
        source = path.open(newline="", encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return logger

    with source:
        rows = csv.reader(source)
        # An empty file has no header row; it counts as found, with no readings.
        columns = next(rows, [])
        for row in rows:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(row) != len(columns):
                raise ValueError("Invalid logger row")
            reading = dict(zip(columns, row))
            temperature = float(reading["temp_c"])
            if not math.isfinite(temperature):
                raise ValueError("Invalid temperature")
            logger["readings"].append({
                "timestamp": reading["timestamp"],
                "temp_c": temperature,
            })
    logger["found"] = True
    return logger


def read_shipments(root):
    with (root / SHIPMENTS_SOURCE).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def weeks(root):
    rows = read_shipments(root)
    return 200, {"source": SHIPMENTS_SOURCE, "weeks": sorted({row["week"] for row in rows})}


def shipments(root, query):
    if not query.get("week"):
        return 400, {"error": "Missing week parameter"}
    week = query["week"][0]
    matches = [row for row in read_shipments(root) if row["week"] == week]
    if not matches:
        return 404, {"error": "Week not found"}
    return 200, {"source": SHIPMENTS_SOURCE, "week": week, "shipments": matches}


def shipment_detail(root, shipment_id):
    if not shipment_id or "/" in shipment_id:
        return NOT_FOUND
    matches = [row for row in read_shipments(root) if row["shipment_id"] == shipment_id]
    if not matches:
        return 404, {"error": "Shipment not found"}
    with (root / THRESHOLDS_SOURCE).open(encoding="utf-8") as source:
        thresholds = json.load(source)
    return 200, {
        "shipment_id": shipment_id,
        "source": SHIPMENTS_SOURCE,
        "thresholds_source": THRESHOLDS_SOURCE,
        "units": thresholds["units"],
        "reading_interval_minutes": thresholds["reading_interval_minutes"],
        "matches": [
            {
                "row": row,
                "limits": thresholds["categories"].get(row["product_category"]),
                "logger": read_logger(root, row["logger_file"]),
            }
            for row in matches
        ],
    }


def handle(path, query, root):
    """Return an HTTP status and JSON payload, reading current files each time."""
    root = Path(root)
    try:
        if path == "/api/weeks":
            return weeks(root)
        elif path == "/api/shipments":
            return shipments(root, query)
        elif path.startswith(DETAIL_PREFIX):
            return shipment_detail(root, path[len(DETAIL_PREFIX):])
        else:
            return NOT_FOUND
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        # Print the full error in the server's terminal; the browser only gets a short message.
        traceback.print_exc()
        return 500, {"error": "Could not read shipment data"}
