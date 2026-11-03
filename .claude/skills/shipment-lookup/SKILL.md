---
name: shipment-lookup
description: Look up shipment records by shipment ID, carrier, lane, or date range. Use when asked to find, list, or show shipments, or who carried or which lane a shipment used. Do not use to judge excursions or recommend a disposition.
---

# Shipment lookup

Find shipments by reading the data files. Nothing here judges temperatures.

## Steps

1. Work out what the user is searching by: shipment ID, carrier, lane, or date range (`ship_date`).
2. Search `data/reference/shipments.csv`. Use `data/reference/carriers.csv` and `data/reference/lanes.csv` to turn names into IDs and back.
3. Report each match with its shipment ID, ship date, week, carrier, lane, product category, and logger file.
4. If nothing matches, say so and ask for another identifier. Do not guess a near match.
5. If a shipment ID matches more than one row, show every matching row and ask which one is meant. Do not pick one.
6. Do not open or change files under `data/raw/`.

## Output

A short list of matches, newest first, with a count. Say what you searched by.
