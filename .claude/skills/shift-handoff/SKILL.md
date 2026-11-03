---
name: shift-handoff
description: Write the shift handoff for the next shift in a fixed format, covering open excursions for one week, loads on hold, and claims not yet filed. Use when a person runs /shift-handoff, with an optional week such as week-13. Do not use to assess one shipment, choose a disposition, or draft or file a claim.
argument-hint: "[week-NN]"
arguments: week
disable-model-invocation: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(python tools/excursion_check.py *)
  - PowerShell(python tools/excursion_check.py *)
---

# Shift handoff

Summarize the shift for whoever takes over the desk, in the same format every time.

Week requested: $week

## Steps

1. Work out the week. If none is requested above, use the latest `week` value in `data/reference/shipments.csv`. Read a bare number as a week, so `13` means `week-13`. If no shipment has the requested week, say so and ask for another. Do not guess.
2. List the shipment IDs in that week's rows, each once.
3. Run `python tools/excursion_check.py <shipment_id>` for each one. Run one shipment per command, without `&&` or a loop, so each call matches the pre-approval. Do not recompute the numbers by hand.
4. Sort the results:
   - **Excursion:** the script reports `"excursion": true`.
   - **Could not assess:** the script reports an unknown ID, a duplicate ID, or a missing logger file. Record the reason as `unknown ID`, `duplicate ID`, or `missing logger file`.
   - Anything else is released and stays out of the handoff.
5. Read the allowance for each category from `data/sop/thresholds.json`. Never hardcode limits.
6. Read every `claims/*.json` payload. Read `claims/submitted.jsonl` if it exists: each line is one filed claim, with its `claim_id` and the filed `payload`. A payload is filed when a line's `payload.shipment_id` matches its `shipment_id`, and pending otherwise. Holds and pending claims cover every payload in `claims/`, not just this week's.
7. Use nothing else: not `audit.jsonl`, not earlier sessions, not the raw logger files. Change no files, and do not draft or file a claim.

## Output

Print exactly this, filling in the angle brackets, and nothing before or after it:

```
## Shift handoff: <week>

<M> shipments in <week>. <N> assessed.

### Open excursions

| Shipment | Carrier | Category | Minutes out of range | Allowed minutes | Disposition |
|---|---|---|---|---|---|
| <shipment_id> | <carrier_id> | <product_category> | <minutes_out_of_range> | <allowance> | <hold, reject, or none yet> |

Could not assess: <shipment_id> (<reason>), <shipment_id> (<reason>)

### Holds

| Shipment | Carrier | Category | Minutes out of range | Claim |
|---|---|---|---|---|
| <shipment_id> | <carrier_id> | <product_category> | <minutes_out_of_range> | <claim_id, or pending> |

### Pending claims

| Shipment | Disposition | Payload |
|---|---|---|
| <shipment_id> | <hold or reject> | claims/<shipment_id>.json |
```

- Keep the headings, their order, and the columns as shown.
- Sort every table and list by shipment ID.
- When a table would have no rows, write `None` in its place. When every shipment was assessed, write `Could not assess: None`.
- In Open excursions, Disposition comes from `claims/<shipment_id>.json` if it exists, otherwise `none yet`.
- If a payload can't be read as JSON, list it under Pending claims with the disposition `unreadable`.
