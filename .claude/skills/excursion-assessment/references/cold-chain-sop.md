# Northfield Cold-Chain SOP: Excursion Assessment

This is the desk's standard operating procedure for deciding what happens to a refrigerated shipment after its temperature logger is read. All data and limits here are fictional and are not food-safety guidance.

The numeric limits live in `data/sop/thresholds.json`. This document states the same limits in prose for judgment calls; if the two ever disagree, the JSON wins.

## 1. Limits by product category

| Category | Allowed temperature range | Allowed time out of range |
|---|---|---|
| Fresh | -2.0 C to 4.0 C | 60 minutes |
| Frozen | -18.0 C or colder (no lower bound) | 30 minutes |
| Marinated | -1.0 C to 3.0 C | 45 minutes |

## 2. How time out of range is counted

- A reading equal to a limit is in range. Only readings warmer than the upper limit or colder than the lower limit are out of range.
- The logger records a reading every 15 minutes. Each out-of-range reading counts as 15 minutes.
- Time out of range is cumulative across the whole trip, not the longest continuous stretch.
- A shipment has an excursion when its total time out of range is more than the allowance for its category. A total equal to the allowance is not an excursion.

## 3. Evidence

- Assess a shipment only from its own logger file. Do not estimate readings that are not there.
- If the shipment ID matches no rows, or more than one row, or its logger file is missing, the shipment cannot be assessed. Hold it and ask for another identifier or the missing file.
- Never edit logger data.

## 4. Disposition

Every assessed shipment gets one of three outcomes.

- **Release.** There is no excursion. Record the shipment as released.
- **Hold.** There is an excursion that is minor. Hold the load for QA review and keep the logger file with the record.
- **Reject.** There is an excursion that is serious. Reject the load and keep the logger file as evidence for a carrier claim.

Judge whether an excursion is minor or serious from the size of the overage, the product category, and anything else on the record. Escalate to the shift supervisor when you cannot decide.

## 5. Carrier claims

A carrier claim needs logger evidence for that shipment and a reject or hold disposition. Never file a claim without both.
