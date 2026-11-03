---
name: draft-claim
description: Draft a carrier claim for one shipment from its logger evidence, write the payload to claims/, and file it with the claim tool. Use when a person runs /draft-claim with a shipment ID to claim against the carrier for a held or rejected load. Do not use to assess an excursion or choose a disposition on its own, and never to file without logger evidence.
argument-hint: "<shipment_id>"
arguments: shipment_id
disable-model-invocation: true
allowed-tools:
  - Read
  - Grep
  - Bash(python tools/excursion_check.py *)
  - PowerShell(python tools/excursion_check.py *)
  - Bash(python tools/carrier_claim_api.py *)
  - PowerShell(python tools/carrier_claim_api.py *)
---

# Draft claim

Build and file a carrier claim for shipment $0, only when the SOP allows one.

## Steps

1. Use the shipment ID given above. If there isn't one, or it isn't a shipment ID, ask for it. One shipment per run. Do not guess.
2. If `claims/submitted.jsonl` exists and any line's `payload.shipment_id` is $0, stop. No claim: this shipment was already filed. Give the earlier `claim_id` and `filed_at`.
3. Run `python tools/excursion_check.py $0` for the numbers. Do not recompute them by hand.
4. If the script reports an unknown ID, a duplicate ID, or a missing logger file, stop. No claim: report what it said and ask for another identifier or the missing file (SOP section 3). Do not write a payload.
5. If the script reports no excursion, stop. The disposition is release, and the SOP allows no claim for a released load (section 5).
6. Read the shipment's row in `data/reference/shipments.csv` for its `carrier_id`, `product_category`, and `logger_file`.
7. Settle the disposition. A claim needs `hold` or `reject`, and choosing between them means judging whether the excursion is minor or serious, which the SOP leaves to people (section 4).
   - If the person already gave `hold` or `reject` for this shipment, use it.
   - Otherwise show the product category, minutes out of range, the allowance for that category, and the minimum and maximum temperatures, then ask: hold or reject? Do not choose.
   - If they say release, stop with no claim. If they can't decide, stop and recommend escalating to the shift supervisor.
8. Write `claims/$0.json` with the Write tool, using exactly these fields and no others:

   ```
   {
     "shipment_id": "<the shipment ID>",
     "carrier_id": "<from the shipments row>",
     "disposition": "<hold or reject>",
     "logger_file": "<from the shipments row, exactly as written there>",
     "product_category": "<from the shipments row>",
     "minutes_out_of_range": <number from step 3>,
     "summary": "<one or two sentences>"
   }
   ```

   `minutes_out_of_range` is a number, not a string. The summary states the facts: category, minutes out of range against the allowance, and the disposition.
9. File it: `python tools/carrier_claim_api.py --payload claims/$0.json`.
10. If the call is blocked, report the reason word for word and stop. Do not edit the payload to get past the check, and do not file the claim any other way.
11. Limits come only from `data/sop/thresholds.json`. Never hardcode them.

## Output

Lead with the outcome: the claim number and "filed", or "No claim" and the reason. Then give the shipment ID, carrier, product category, disposition, minutes out of range against the allowance, and the payload path. Say that the claim tool is a mock and nothing was sent.

## References

- `data/sop/cold-chain-sop.md`: the SOP. Section 3 covers evidence, section 4 disposition, and section 5 carrier claims.
