# Northfield Cold-Chain Exception Desk

## Purpose

TODO: What this project is for and who relies on it.

## Tone

TODO: How Claude should write for the desk: its reports, summaries, and questions.

## Non-negotiables

TODO: The rules Claude must never break here, whatever it's asked.

---

## Running the tests

```
python -m unittest discover -s tests
```

## Where the data lives

- `data/raw/loggers/week-NN/<shipment_id>.csv`: temperature readings every 15 minutes, `timestamp` (UTC) and `temp_c`.
- `data/reference/shipments.csv`: one row per shipment, with its carrier, lane, product category, and logger file.
- `data/reference/carriers.csv` and `data/reference/lanes.csv`: carrier and lane names.
- `data/sop/thresholds.json`: temperature limits and allowed time out of range for each product category.
