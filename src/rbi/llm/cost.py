"""`make cost` — print spend by stage and by model from the ledger (PROJECT_SPEC.md §7)."""
from __future__ import annotations

from .ledger import CostLedger


def main() -> None:
    led = CostLedger()
    total = led.spend_to_date()
    print(f"Spend cap:      ${led.cap_usd:.2f}")
    print(f"Spent to date:  ${total:.4f}  ({total / led.cap_usd * 100:.1f}% of cap)")

    print("\nBy stage:")
    for stage, cost, n in led.by_stage() or [("(none yet)", 0.0, 0)]:
        print(f"  {stage:16} ${cost:.4f}  ({n} calls)")

    print("\nBy model:")
    for model, cost, n in led.by_model() or [("(none yet)", 0.0, 0)]:
        print(f"  {model:48} ${cost:.4f}  ({n} calls)")


if __name__ == "__main__":
    main()
