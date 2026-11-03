"""Check a shipment's cumulative time outside its temperature limits."""

import argparse
import csv
import json
import sys


def load_thresholds(path="data/sop/thresholds.json"):
    """Read the temperature policy from JSON."""
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def load_readings(csv_path):
    """Read temperatures in their original file order."""
    with open(csv_path, newline="", encoding="utf-8") as source:
        return [float(row["temp_c"]) for row in csv.DictReader(source)]


def assess(temps_c, limits, interval_minutes=15):
    """Summarize temperatures and cumulative time outside inclusive bounds."""
    out_of_range = 0
    for temp in temps_c:
        below = limits["min_c"] is not None and temp < limits["min_c"]
        above = limits["max_c"] is not None and temp > limits["max_c"]
        if below or above:
            out_of_range += 1

    minutes = out_of_range * interval_minutes
    return {
        "min_temp_c": min(temps_c),
        "max_temp_c": max(temps_c),
        "minutes_out_of_range": minutes,
        "excursion": minutes > limits["max_minutes_out_of_range"],
    }


def main():
    """Find one shipment and print its assessment as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shipment_id")
    args = parser.parse_args()

    with open("data/reference/shipments.csv", newline="", encoding="utf-8") as source:
        matches = [
            row for row in csv.DictReader(source)
            if row["shipment_id"] == args.shipment_id
        ]

    if not matches:
        print(f"Unknown shipment ID: {args.shipment_id}", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"Duplicate shipment ID: {args.shipment_id}. Matching rows:", file=sys.stderr)
        for row in matches:
            print(
                f"  week={row['week']}, carrier_id={row['carrier_id']}, "
                f"lane_id={row['lane_id']}",
                file=sys.stderr,
            )
        return 1

    shipment = matches[0]
    try:
        readings = load_readings(shipment["logger_file"])
    except FileNotFoundError:
        print(f"Missing logger file: {shipment['logger_file']}", file=sys.stderr)
        return 1

    thresholds = load_thresholds()
    category = shipment["product_category"]
    result = assess(
        readings,
        thresholds["categories"][category],
        thresholds["reading_interval_minutes"],
    )
    result.update(shipment_id=args.shipment_id, product_category=category)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
