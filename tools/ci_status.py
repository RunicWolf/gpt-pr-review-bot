# tools/ci_status.py
from pathlib import Path
from app.settings import settings

STATUS = Path(".review_event")


def main() -> int:
    # Default to comment if status file missing
    event = "COMMENT"
    if STATUS.exists():
        try:
            event = STATUS.read_text("utf-8").strip().upper()
        except Exception:
            pass

    print(f"Review event: {event}")
    if settings.enforce_gate_on_ci and event == "REQUEST_CHANGES":
        print("Gate enforced: failing job because REQUEST_CHANGES.")
        return 1
    print("Gate not enforced or no request-changes; passing job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
