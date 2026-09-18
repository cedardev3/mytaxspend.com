"""
Validate federal-outlays.json tree math and UI percentage consistency.

Checks:
  1. Every parent's amountMillions equals the sum of its children (tree integrity).
  2. For parents with a positive net total, each child's share-of-parent-net is
     reported (what the UI now displays). Also lists offset children so you can
     confirm positive shares + offset shares = 100%.

Run: python scripts/validate-budget-totals.py
  or: npm run validate-budget
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATHS = [
    ROOT / "src" / "data" / "federal-outlays.json",
    ROOT / "src" / "data" / "federal-receipts.json",
    ROOT / "src" / "data" / "canada-federal-outlays.json",
    ROOT / "src" / "data" / "canada-federal-receipts.json",
]

# Flag when positive shares + offset shares do not sum to ~100% of parent net.
SUM_TOLERANCE_PP = 0.15


def billions(millions: float) -> str:
    if abs(millions) >= 1_000_000:
        return f"${millions / 1_000_000:.3f}T"
    if abs(millions) >= 1_000:
        return f"${millions / 1_000:.2f}B"
    return f"${millions:.0f}M"


def pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def walk(node: dict, path: list[str], total_issues: list, offset_parents: list) -> None:
    children = node.get("children") or []
    if not children:
        return

    child_sum = sum(c["amountMillions"] for c in children)
    parent_amt = node["amountMillions"]
    # Match assertTreeTotals in src/lib/spend.ts (one decimal of millions)
    if round(child_sum * 10) != round(parent_amt * 10):
        total_issues.append(
            {
                "path": " / ".join(path + [node["name"]]),
                "id": node["id"],
                "parent": parent_amt,
                "children_sum": child_sum,
                "delta": child_sum - parent_amt,
            }
        )

    offsets = [c for c in children if c["amountMillions"] <= 0]
    if offsets and parent_amt > 0:
        shares = []
        for child in children:
            share = child["amountMillions"] / parent_amt
            shares.append(
                {
                    "name": child["name"],
                    "amount": child["amountMillions"],
                    "of_parent_net": share,
                    "is_offset": child["amountMillions"] <= 0,
                }
            )
        share_sum = sum(s["of_parent_net"] for s in shares)
        offset_parents.append(
            {
                "path": " / ".join(path + [node["name"]]),
                "id": node["id"],
                "parent_net": parent_amt,
                "shares": shares,
                "share_sum": share_sum,
                "sum_ok": abs(share_sum - 1.0) * 100 <= SUM_TOLERANCE_PP,
            }
        )

    for child in children:
        walk(child, path + [node["name"]], total_issues, offset_parents)


def validate_dataset(data_path: Path) -> int:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    root = data["root"]

    total_issues: list = []
    offset_parents: list = []
    walk(root, [], total_issues, offset_parents)

    print(f"Dataset: {data_path.relative_to(ROOT)}")
    print(f"Generated: {data.get('generatedAt', '?')}")
    print(
        f"OMB FY: {data.get('omb', {}).get('fiscalYear', '?')} "
        f"({data.get('omb', {}).get('status', '?')})"
    )
    print()

    print("=" * 72)
    print("1) Child sums vs parent totals")
    print("=" * 72)
    if not total_issues:
        print("OK - every parent equals the sum of its children.")
    else:
        print(f"FAIL - {len(total_issues)} parent(s) do not equal child sum:\n")
        for issue in total_issues:
            print(f"  {issue['path']}")
            print(f"    id: {issue['id']}")
            print(
                f"    parent={billions(issue['parent'])}  "
                f"children={billions(issue['children_sum'])}  "
                f"delta={billions(issue['delta'])}"
            )
            print()

    print()
    print("=" * 72)
    print("2) UI % of parent net (incl. offsets) - should sum to ~100%")
    print("=" * 72)
    print(
        "UI labels use amount / parent net. Positive amounts fill the pie;\n"
        "negative offsets are hatched overlays on top (they do not expand it).\n"
    )

    sum_failures = 0
    if not offset_parents:
        print("OK - no parents with offsets.")
    else:
        print(f"Parents with offsets: {len(offset_parents)}\n")
        for parent in offset_parents:
            status = "OK" if parent["sum_ok"] else "FAIL"
            if not parent["sum_ok"]:
                sum_failures += 1
            print(f"  [{status}] {parent['path']}")
            print(f"    parent net: {billions(parent['parent_net'])}")
            for share in parent["shares"]:
                tag = " offset" if share["is_offset"] else ""
                print(
                    f"      {share['name']}: {billions(share['amount'])}  "
                    f"{pct(share['of_parent_net'])}{tag}"
                )
            print(f"    sum of shares: {pct(parent['share_sum'])}")
            print()

    print("=" * 72)
    print("Summary")
    print("=" * 72)
    print(f"  Tree total failures:     {len(total_issues)}")
    print(f"  Offset parents:          {len(offset_parents)}")
    print(f"  Share-sum failures:      {sum_failures}")
    print()

    if total_issues or sum_failures:
        return 1
    return 0


def main() -> int:
    exit_code = 0
    for data_path in DATA_PATHS:
        if not data_path.exists():
            print(f"MISSING {data_path}")
            exit_code = 1
            continue
        exit_code = max(exit_code, validate_dataset(data_path))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
