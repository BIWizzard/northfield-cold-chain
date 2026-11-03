"""Record a mock carrier claim locally without checking its evidence."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, help="Path to a JSON payload")
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.payload.replace("\\", "/")).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Cannot read claim payload: {exc}", file=sys.stderr)
        return 1

    claim_id = f"CLM-{secrets.randbelow(1_000_000):06d}"
    record = {
        "filed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "claim_id": claim_id,
        "payload": payload,
    }
    try:
        submitted = ROOT / "claims" / "submitted.jsonl"
        submitted.parent.mkdir(parents=True, exist_ok=True)
        with submitted.open("a", encoding="utf-8") as destination:
            destination.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"Cannot record mock claim: {exc}", file=sys.stderr)
        return 1

    shipment_id = payload.get("shipment_id", "unknown") if isinstance(payload, dict) else "unknown"
    print(f"Claim {claim_id} filed for {shipment_id}. Mock only: nothing was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
