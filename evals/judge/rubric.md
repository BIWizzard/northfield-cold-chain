# Claim draft rubric

You are grading one carrier claim draft written by the `/draft-claim` skill. The draft is the JSON payload it wrote to `claims/`. Answer four separate yes/no checks. A check is `yes` only when the draft clearly meets it. If you are unsure, answer `no`.

You are given the draft and the record for its shipment (the numbers from `tools/excursion_check.py`, the shipment's row, and the SOP allowance for its category). Use only those. Do not look anything up and do not run anything.

## Checks

1. **evidence**: The `summary` cites the shipment's logger file or its readings as the source of the numbers it gives. The `logger_file` field alone does not count; the summary has to say where the numbers come from.
2. **no_outside_facts**: Every fact in the draft is in the record you were given. Anything about what happened that is not in the record, such as a cause, something a driver said, or a number that does not match the record, is a `no`.
3. **payload_fields**: The payload has exactly these seven fields and no others: `shipment_id`, `carrier_id`, `disposition`, `logger_file`, `product_category`, `minutes_out_of_range`, `summary`. `minutes_out_of_range` is a number, not a string.
4. **tone**: The `summary` is professional: it states facts plainly and does not accuse, insult, demand, or use slang. A firm request is fine; blame is not.

## Answer format

Reply with JSON only, in this shape, and nothing else:

```
{"checks": {"evidence": "yes", "no_outside_facts": "yes", "payload_fields": "yes", "tone": "yes"}}
```
