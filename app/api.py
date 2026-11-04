"""Read shipment data for the local web app."""

import csv
import json
import math
from pathlib import Path
import traceback


SHIPMENTS_SOURCE = "data/reference/shipments.csv"
CARRIERS_SOURCE = "data/reference/carriers.csv"
LANES_SOURCE = "data/reference/lanes.csv"
THRESHOLDS_SOURCE = "data/sop/thresholds.json"
LOGGERS_SOURCE = "data/raw/loggers/"
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


def read_csv(root, path):
    with (root / path).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def read_shipments(root):
    return read_csv(root, SHIPMENTS_SOURCE)


def read_thresholds(root):
    with (root / THRESHOLDS_SOURCE).open(encoding="utf-8") as source:
        return json.load(source)


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
    thresholds = read_thresholds(root)
    # Carrier and lane records are looked up by ID only, to show their names next to the IDs.
    carriers = {carrier["carrier_id"]: carrier for carrier in read_csv(root, CARRIERS_SOURCE)}
    lanes = {lane["lane_id"]: lane for lane in read_csv(root, LANES_SOURCE)}
    return 200, {
        "shipment_id": shipment_id,
        "source": SHIPMENTS_SOURCE,
        "thresholds_source": THRESHOLDS_SOURCE,
        "units": thresholds["units"],
        "reading_interval_minutes": thresholds["reading_interval_minutes"],
        "matches": [
            {
                "row": row,
                "carrier": carriers.get(row["carrier_id"]),
                "lane": lanes.get(row["lane_id"]),
                "limits": thresholds["categories"].get(row["product_category"]),
                "logger": read_logger(root, row["logger_file"]),
            }
            for row in matches
        ],
    }


def overview(root):
    """Record counts and date ranges for the home page. Nothing here describes a single shipment."""
    rows = read_shipments(root)
    carriers = read_csv(root, CARRIERS_SOURCE)
    lanes = read_csv(root, LANES_SOURCE)
    thresholds = read_thresholds(root)
    week_ranges = []
    for week in sorted({row["week"] for row in rows}):
        dates = sorted(row["ship_date"] for row in rows if row["week"] == week)
        week_ranges.append({
            "week": week, "first_ship_date": dates[0], "last_ship_date": dates[-1], "rows": len(dates),
        })
    dates = sorted(row["ship_date"] for row in rows)
    return 200, {
        "source": SHIPMENTS_SOURCE,
        "carriers_source": CARRIERS_SOURCE,
        "lanes_source": LANES_SOURCE,
        "thresholds_source": THRESHOLDS_SOURCE,
        "loggers_source": LOGGERS_SOURCE,
        "weeks": week_ranges,
        "latest_week": week_ranges[-1] if week_ranges else None,
        "first_ship_date": dates[0] if dates else None,
        "last_ship_date": dates[-1] if dates else None,
        "shipment_rows": len(rows),
        "carriers": len(carriers),
        "lanes": len(lanes),
        "plants": len({lane["origin"] for lane in lanes}),
        "distribution_centers": len({lane["destination"] for lane in lanes}),
        "categories": list(thresholds["categories"]),
        "units": thresholds["units"],
        "reading_interval_minutes": thresholds["reading_interval_minutes"],
    }


def reference(root):
    """The carrier, lane, and category records that shipment rows refer to, as they are in the files."""
    thresholds = read_thresholds(root)
    return 200, {
        "carriers_source": CARRIERS_SOURCE,
        "lanes_source": LANES_SOURCE,
        "thresholds_source": THRESHOLDS_SOURCE,
        "carriers": read_csv(root, CARRIERS_SOURCE),
        "lanes": read_csv(root, LANES_SOURCE),
        "units": thresholds["units"],
        "reading_interval_minutes": thresholds["reading_interval_minutes"],
        "categories": thresholds["categories"],
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
        elif path == "/api/overview":
            return overview(root)
        elif path == "/api/reference":
            return reference(root)
        else:
            return NOT_FOUND
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        # Print the full error in the server's terminal; the browser only gets a short message.
        traceback.print_exc()
        return 500, {"error": "Could not read shipment data"}
