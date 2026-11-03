---
name: draft-claim
description: Draft a carrier claim for one shipment from its logger evidence, write the payload to claims/, and file it with the claim tool. Use when a person runs /draft-claim with a shipment ID, and optionally hold or reject, to claim against the carrier for a held or rejected load. Do not use to assess an excursion or choose a disposition on its own, and never to file without logger evidence.
argument-hint: "<shipment_id> [hold|reject]"
disable-model-invocation: true
allowed-tools:
  - Bash(python tools/excursion_check.py *)
  - PowerShell(python tools/excursion_check.py *)
  - Bash(python tools/carrier_claim_api.py *)
  - PowerShell(python tools/carrier_claim_api.py *)
---

# Draft claim

Build and file a carrier claim for shipment $0, only when the SOP allows one.

Disposition given: $1

## Steps

1. Use the shipment ID given above. If there isn't one, or it isn't a shipment ID, ask for it. One shipment per run. Do not guess.
2. If `claims/submitted.jsonl` exists and any line's `payload.shipment_id` is $0, stop. No claim: this shipment was already filed. Give the earlier `claim_id` and `filed_at`.
3. Run `python tools/excursion_check.py $0` for the numbers. Do not recompute them by hand.
4. If the script reports an unknown ID, a duplicate ID, or a missing logger file, stop. No claim: report what it said and ask for another identifier or the missing file (SOP section 3). Do not write a payload.
5. If the script reports no excursion, stop. The disposition is release, and the SOP allows no claim for a released load (section 5).
6. Read the shipment's row in `data/reference/shipments.csv` for its `carrier_id`, `product_category`, and `logger_file`.
7. Read the allowance for that category from `data/sop/thresholds.json`. Limits come only from there. Never hardcode them.
8. Settle the disposition. A claim needs `hold` or `reject`. Choosing between them means judging whether the excursion is minor or serious. The SOP makes this a judgment call (section 4), so the person decides.
   - If the disposition given above is `hold` or `reject`, use it.
   - If it's `release`, stop with no claim.
   - Otherwise (no disposition was given), show the product category, minutes out of range, the allowance, and the minimum and maximum temperatures, then ask: hold or reject? Do not choose. Say that because they're answering in a new message, filing will ask for their permission.
   - If they can't decide, stop and recommend escalating to the shift supervisor.
9. Write `claims/$0.json` with the Write tool, using exactly these fields and no others:

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
10. File it: `python tools/carrier_claim_api.py --payload claims/$0.json`. Run it on its own, not chained with another command.
11. If the call is blocked, report the reason word for word and stop. Do not edit the payload to get past the check, and do not file the claim any other way.

## Output

Lead with the outcome: the claim number and "filed", or "No claim" and the reason. Then give the shipment ID, carrier, product category, disposition, minutes out of range against the allowance, and the payload path. Say that the claim tool is a mock and nothing was sent.

## References

- `data/sop/cold-chain-sop.md`: the SOP. Section 3 covers evidence, section 4 disposition, and section 5 carrier claims.
