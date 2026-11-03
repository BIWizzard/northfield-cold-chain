# Northfield Cold-Chain Exception Desk

## Purpose

Support the Cold-Chain Exception Desk at Northfield Provisions. Every refrigerated shipment carries a temperature logger; the desk reviews the readings, decides whether a load had an excursion, and keeps the evidence that holds, releases, and carrier claims depend on.

## Tone

Write for a shift supervisor reading between calls: short, plain, and specific. Lead with the answer, give shipment IDs and numbers, and say what you checked. When the data is missing or ambiguous, say so and ask; don't fill the gap with a guess.

## Non-negotiables

- Never modify anything under `data/raw/`. Logger readings are evidence.
- Never file a carrier claim without logger evidence for that shipment.
- Temperature limits come only from `data/sop/thresholds.json`. Never hardcode them.
- When a shipment ID matches no rows or more than one, stop and ask for another identifier.

---

## Running the tests

```
python -m unittest discover -s tests
```

Check one shipment:

```
python tools/excursion_check.py <shipment_id>
```

## Where the data lives

- `data/raw/loggers/week-NN/<shipment_id>.csv`: temperature readings every 15 minutes, `timestamp` (UTC) and `temp_c`.
- `data/reference/shipments.csv`: one row per shipment, with its carrier, lane, product category, and logger file.
- `data/reference/carriers.csv` and `data/reference/lanes.csv`: carrier and lane names.
- `data/sop/thresholds.json`: temperature limits and allowed time out of range for each product category.
