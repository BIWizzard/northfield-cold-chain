---
name: excursion-assessment
description: Assess whether a refrigerated shipment had a temperature excursion and recommend a disposition (release, hold, or reject). Use when asked if a shipment is an excursion, whether to release, hold, or reject a load, or what the SOP says about a temperature problem. Do not use for simply finding or listing shipments.
---

# Excursion assessment

Decide whether one shipment had a temperature excursion, then recommend a disposition under the SOP.

## Steps

1. Get one shipment ID from the user. If there isn't one, ask for it.
2. Run `python tools/excursion_check.py <shipment_id>` for the numbers. Do not recompute them by hand.
3. If the script reports an unknown ID, a duplicate ID, or a missing logger file, stop. Report what it said, do not assess, and ask for another identifier or the missing file.
4. Otherwise read `references/cold-chain-sop.md` and apply section 4 (Disposition) to the result.
5. Limits come only from `data/sop/thresholds.json`. Never hardcode them.

## Output

Lead with the disposition (release, hold, or reject). Then give the shipment ID, product category, minutes out of range, and the allowance for that category. If an excursion's severity is a judgment call the SOP does not settle, say so and recommend escalating to the shift supervisor rather than choosing silently.

## References

- `references/cold-chain-sop.md`: the SOP, including the disposition rules.
