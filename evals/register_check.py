"""Check a month-end register for completeness (Lab 15).

The register is a CSV with columns shipment_id, ship_date, carrier_id, and
disposition: one row for every row of data/reference/shipments.csv with an
October 2026 ship_date. Rows are matched on (shipment_id, ship_date, carrier_id),
so a shipment ID that appears twice needs both of its rows.

Prints missing, duplicated, and unexpected rows, and exits 0 only when there are
none. It doesn't judge dispositions; the eval suite does that.

    python evals/register_check.py register.csv

Exit codes: 0 complete, 1 problems found, 2 the register can't be read.
"""

import argparse
from collections import Counter
import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SHIPMENTS = ROOT / "data" / "reference" / "shipments.csv"
MONTH = "2026-10"
KEY = ("shipment_id", "ship_date", "carrier_id")
COLUMNS = KEY + ("disposition",)


def read_keys(path):
    """Return the (shipment_id, ship_date, carrier_id) of every row in a CSV.

    Raises ValueError naming any of the columns that are missing.
    """
    with open(path, encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        header = [name.strip() for name in reader.fieldnames or []]
        missing = [name for name in COLUMNS if name not in header]
        if missing:
            raise ValueError(f"{path} is missing column(s): {', '.join(missing)}. "
                             f"Expected: {', '.join(COLUMNS)}")
        reader.fieldnames = header
        return [tuple((row[name] or "").strip() for name in KEY) for row in reader]


def expected_keys(shipments=SHIPMENTS):
    """The register a complete run produces: every October 2026 row of shipments.csv."""
    with open(shipments, encoding="utf-8-sig", newline="") as source:
        return [tuple(row[name] for name in KEY)
                for row in csv.DictReader(source) if row["ship_date"].startswith(MONTH)]


def show(title, keys):
    print(f"{title} ({len(keys)}):")
    for shipment_id, ship_date, carrier_id in sorted(keys):
        print(f"  {shipment_id}  {ship_date}  {carrier_id}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("register", type=Path, help="the register CSV to check")
    args = parser.parse_args(argv)

    try:
        found = read_keys(args.register)
    except OSError as exc:
        print(f"Can't read the register {args.register}: {exc.strerror or exc}")
        return 2
    except ValueError as exc:
        print(exc)
        return 2

    expected = set(expected_keys())
    counts = Counter(found)
    missing = expected - set(counts)
    duplicated = [key for key, count in counts.items() if count > 1]
    unexpected = set(counts) - expected

    if not (missing or duplicated or unexpected):
        print(f"Register complete: all {len(expected)} October shipments accounted for, once each.")
        return 0

    print(f"Register incomplete: {len(found)} rows checked against {len(expected)} October shipments.")
    if missing:
        show("Missing", missing)
    if duplicated:
        show("Duplicate", duplicated)
    if unexpected:
        show("Unexpected (not an October 2026 shipment)", unexpected)
    return 1


if __name__ == "__main__":
    sys.exit(main())
