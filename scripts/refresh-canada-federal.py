"""
Build Canadian federal spending + revenue trees (multi-layer) and write:
  src/data/canada-federal-outlays.json
  src/data/canada-federal-receipts.json

Sources (FY 2024-25 actuals):
  - Finance Canada Fiscal Reference Tables (October 2025) for spending category spine
  - Public Accounts revenues/expenses CSV for revenue + public debt detail
  - Public Accounts Other transfer payments by ministry (OTP)
  - Public Accounts Ministerial expenditures by type (MET) for other direct program

Run: python scripts/refresh-canada-federal.py
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTLAYS_PATH = ROOT / "src" / "data" / "canada-federal-outlays.json"
RECEIPTS_PATH = ROOT / "src" / "data" / "canada-federal-receipts.json"

PUBLIC_ACCOUNTS_URL = (
    "https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/revenuesdeficit/revenuesdeficit-2025.csv"
)
PUBLIC_ACCOUNTS_DATASET = (
    "https://open.canada.ca/data/en/dataset/2599fe61-0e6e-40b9-958a-f56dd7f1fa09"
)
OTP_URL = (
    "https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/otpmopeom-apdtmacdpam/"
    "otpmopeom-apdtmacdpam-2025.csv"
)
OTP_DATASET = "https://open.canada.ca/data/en/dataset/f6db2071-1f97-4d88-8af0-1deeb949ee2f"
MET_URL = "https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/dmc-met/dmc-met-2025.csv"
MET_DATASET = "https://open.canada.ca/data/en/dataset/2599fe61-0e6e-40b9-958a-f56dd7f1fa09"
FRT_PAGE_URL = (
    "https://www.canada.ca/en/department-finance/services/publications/"
    "fiscal-reference-tables/2025.html"
)
FRT_PDF_URL = "https://www.canada.ca/content/dam/fin/publications/frt-trf/2025/frt-trf-25-eng.pdf"

FISCAL_YEAR_LABEL = "2024-25"
FISCAL_YEAR = 2025
STATUS = "actual"

# FRT Table 7 / 10 / 11 / 12 / 13 — FY 2024-25 (millions of dollars).
FRT_SPENDING = {
    "major_transfers_persons": {
        "name": "Major transfers to persons",
        "amount": 131579.0,
        "children": [
            {"name": "Old Age Security benefits", "amount": 80294.0},
            {"name": "Children's benefits", "amount": 28574.0},
            {"name": "Employment Insurance", "amount": 24880.0},
            {"name": "Relief for heating expenses", "amount": -2169.0},
        ],
    },
    "major_transfers_provinces": {
        "name": "Major transfers to provinces, territories and municipalities",
        "amount": 105101.0,
        "children": [
            {"name": "Canada Health Transfer", "amount": 68979.0},
            {"name": "Fiscal arrangements", "amount": 30457.0},
            {"name": "Canada-wide early learning and child care", "amount": 6639.0},
            {"name": "Other", "amount": 6568.0},
            {"name": "Quebec Abatement", "amount": -7542.0},
        ],
    },
    "other_transfer_payments": {
        "name": "Other transfer payments",
        "amount": 15595.0,
        "children": [],
    },
    "direct_program": {
        "name": "Direct program expenses",
        "amount": 237594.0,
        "other_transfer_payments": 107140.0,
        "other_direct": 130454.0,
    },
    "pollution_pricing": {
        "name": "Pollution pricing proceeds returned to Canadians",
        "amount": 4020.0,
        "children": [],
    },
    "public_debt": {
        "name": "Public debt charges",
        "amount": 53410.0,
    },
}

# Department of National Defence FY 2024-25 actuals (millions) for interest-vs-defense strip.
CANADA_NATIONAL_DEFENCE_MILLIONS = 33924.8

# FRT Table 1: budgetary deficit -36,348 is -1.2% of GDP → GDP ≈ 3,029 billion.
CANADA_GDP_BILLIONS = 3029.0

CTX = ssl.create_default_context()

COLORS = [
    "#c45c26",
    "#2a6f97",
    "#2f7d6d",
    "#c4922a",
    "#5c6b73",
    "#6b5b95",
    "#4a7c59",
    "#245d82",
    "#7a6a58",
    "#3b6d9a",
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mytaxspend.com canada refresh"})
    with urllib.request.urlopen(req, context=CTX, timeout=120) as resp:
        return resp.read()


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:96]


def clean_label(text: str) -> str:
    text = (text or "").replace("\ufffd", "–").replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def mix_hex(color: str, toward: str, t: float) -> str:
    def parts(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    a = parts(color)
    b = parts(toward)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def round1(value: float) -> float:
    return round(value, 1)


def assert_sum(label: str, total: float, parts: list[float]) -> None:
    got = round1(sum(parts))
    want = round1(total)
    if got != want:
        raise RuntimeError(f"{label}: parts sum {got} != total {want}")


def reconcile_amounts(target: float, amounts: list[float]) -> list[float]:
    """Round to 1 decimal and adjust the largest absolute item so parts sum to target."""
    if not amounts:
        return amounts
    rounded = [round1(value) for value in amounts]
    delta = round1(target) - round1(sum(rounded))
    if delta != 0:
        index = max(range(len(rounded)), key=lambda i: abs(rounded[i]))
        rounded[index] = round1(rounded[index] + delta)
    return rounded


def sources_pa() -> list[dict[str, str]]:
    return [
        {
            "label": f"Public Accounts of Canada, FY {FISCAL_YEAR_LABEL}",
            "url": PUBLIC_ACCOUNTS_DATASET,
        },
        {"label": "Revenues / expenses CSV", "url": PUBLIC_ACCOUNTS_URL},
    ]


def sources_otp() -> list[dict[str, str]]:
    return [
        {
            "label": f"Public Accounts — other transfer payments by ministry, FY {FISCAL_YEAR_LABEL}",
            "url": OTP_DATASET,
        },
        {"label": "OTP by ministry CSV", "url": OTP_URL},
    ]


def sources_met() -> list[dict[str, str]]:
    return [
        {
            "label": f"Public Accounts — ministerial expenditures by type, FY {FISCAL_YEAR_LABEL}",
            "url": MET_DATASET,
        },
        {"label": "MET CSV", "url": MET_URL},
    ]


def sources_frt() -> list[dict[str, str]]:
    return [
        {
            "label": f"Fiscal Reference Tables, October 2025 (FY {FISCAL_YEAR_LABEL})",
            "url": FRT_PAGE_URL,
        },
        {"label": "FRT PDF", "url": FRT_PDF_URL},
    ]


def leaf(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
) -> dict:
    return {
        "id": node_id,
        "name": name,
        "amountMillions": round1(amount),
        "color": color,
        "description": description,
        "sources": sources,
    }


def branch(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
    children: list[dict],
) -> dict:
    if children:
        assert_sum(name, amount, [c["amountMillions"] for c in children])
    node = {
        "id": node_id,
        "name": name,
        "amountMillions": round1(amount),
        "color": color,
        "description": description,
        "sources": sources,
    }
    if children:
        node["children"] = children
    return node


def parse_amount(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).replace(",", "").strip()
    if text in {"", "N/A", "n/a", ".."}:
        return None
    return float(text)


def load_csv(url: str) -> list[dict]:
    text = fetch(url).decode("utf-8-sig")
    return list(csv.DictReader(StringIO(text)))


def load_public_accounts() -> list[dict]:
    return load_csv(PUBLIC_ACCOUNTS_URL)


def otp_consolidated_millions(row: dict) -> float:
    """OTP CSV units are x1000; consolidation formula matches FRT Other TP."""

    def num(key: str) -> float:
        return parse_amount(row.get(key)) or 0.0

    total_thousands = (
        num("Ttl-min-net-exp_Ttl-dep-min-nettes")
        + num("Cons-special-accnts_Cmpts-determinees-cons")
        + num("Accrual-and-other-adjs_Redressements-courus-et-autres")
        + num("Xpns-CC-other-ents_Dep-SE-autres-ents")
        + num("Tax-credits-and-repay_Credits-et-rembours-fiscaux")
    )
    return total_thousands / 1000.0


def other_transfer_payment_ministries(color: str) -> list[dict]:
    """Ministry rows from PAC Table 2b, including the valuation provision line.

    Public Accounts Table 2b lists ministries then a separate
    "Provision for valuation and other items" row (blank ministry name,
    Provision_eng filled). That line bridges ministry subtotal → FRT total.
    Indigenous Services is fully present in the CSV; it is not omitted.
    """
    rows = load_csv(OTP_URL)
    buckets: dict[str, float] = defaultdict(float)
    for row in rows:
        if (row.get("Xpns-type_Type-dep_eng") or "") != "Other transfer payments":
            continue
        ministry = clean_label(row.get("Min-portfolio_Portefeuille-min_eng") or "")
        provision = clean_label(row.get("Provision_eng") or "")
        name = ministry or provision
        if not name:
            continue
        buckets[name] += otp_consolidated_millions(row)

    target = FRT_SPENDING["direct_program"]["other_transfer_payments"]
    ordered = sorted(buckets.items(), key=lambda item: -abs(item[1]))
    amounts = reconcile_amounts(target, [amount for _, amount in ordered])
    sources = sources_otp()
    children = []
    for index, ((name, _), amount) in enumerate(zip(ordered, amounts)):
        if amount == 0:
            continue
        children.append(
            leaf(
                node_id=slug(f"ca-otp-{name}"),
                name=name,
                amount=amount,
                color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.16),
                description=(
                    f"Public Accounts FY {FISCAL_YEAR_LABEL}: other transfer payments — {name}."
                ),
                sources=sources,
            )
        )
    assert_sum("Other transfer payments (ministries)", target, [c["amountMillions"] for c in children])
    return children


def other_direct_program_ministries(color: str) -> list[dict]:
    """MET other-program spending by ministry → entity, plus residual to FRT."""
    rows = load_csv(MET_URL)
    by_ministry: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        amount = (parse_amount(row.get("Other-prog-xpend_Autres-depenses-prog")) or 0.0) / 1000.0
        if abs(amount) < 0.05:
            continue
        ministry = clean_label(row.get("Min-portfolio_Portefeuille-min_eng") or "")
        entity = clean_label(row.get("Entity_Entite_eng") or "") or ministry
        if not ministry:
            continue
        by_ministry[ministry][entity] += amount

    met_total = sum(sum(entities.values()) for entities in by_ministry.values())
    target = FRT_SPENDING["direct_program"]["other_direct"]
    residual = round1(target - round1(met_total))
    sources = sources_met()

    ministry_items = sorted(
        ((name, entities) for name, entities in by_ministry.items()),
        key=lambda item: -abs(sum(item[1].values())),
    )
    ministry_raw = [sum(entities.values()) for _, entities in ministry_items]
    residual_note: str | None = None
    if residual != 0:
        ministry_raw.append(residual)
        ministry_items.append(
            (
                "Consolidation and other adjustments",
                {"Consolidation and other adjustments": residual},
            )
        )
        residual_note = (
            f"Bridge to Fiscal Reference Tables: ministerial other-program lines sum to "
            f"{round1(met_total):,.1f} million; FRT other direct program expenses are "
            f"{round1(target):,.1f} million. This {round1(residual):,.1f} million residual "
            f"covers consolidation and other items not allocated to a ministry in the MET file."
        )
    ministry_amounts = reconcile_amounts(target, ministry_raw)

    children: list[dict] = []
    for index, ((ministry, entities), ministry_amount) in enumerate(
        zip(ministry_items, ministry_amounts)
    ):
        entity_items = sorted(entities.items(), key=lambda item: -abs(item[1]))
        is_residual = ministry == "Consolidation and other adjustments"
        description = (
            residual_note
            if is_residual and residual_note
            else (
                f"Public Accounts FY {FISCAL_YEAR_LABEL}: other direct program — {ministry}."
            )
        )
        if is_residual or (
            len(entity_items) == 1 and entity_items[0][0] == ministry
        ):
            children.append(
                leaf(
                    node_id=slug(f"ca-ode-{ministry}"),
                    name=ministry,
                    amount=ministry_amount,
                    color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.16),
                    description=description,
                    sources=sources,
                )
            )
            continue

        entity_amounts = reconcile_amounts(
            ministry_amount, [amount for _, amount in entity_items]
        )
        entity_children = []
        for j, ((entity, _), amount) in enumerate(zip(entity_items, entity_amounts)):
            entity_children.append(
                leaf(
                    node_id=slug(f"ca-ode-{ministry}-{entity}"),
                    name=entity,
                    amount=amount,
                    color=mix_hex(color, "#ffffff" if j % 2 == 0 else "#1f3d4d", 0.22),
                    description=(
                        f"Public Accounts FY {FISCAL_YEAR_LABEL}: {ministry} — {entity}."
                    ),
                    sources=sources,
                )
            )
        children.append(
            branch(
                node_id=slug(f"ca-ode-{ministry}"),
                name=ministry,
                amount=ministry_amount,
                color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.12),
                description=description,
                sources=sources,
                children=entity_children,
            )
        )

    assert_sum("Other direct program expenses", target, [c["amountMillions"] for c in children])
    return children


def public_debt_children(rows: list[dict]) -> list[dict]:
    """Public debt → Type-detail2 → Type-detail3/4."""
    nested: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        if row.get("Account_Compte_eng") != "Expenses":
            continue
        if (row.get("Type-detail_eng") or "") != "Public debt charges":
            continue
        amount = parse_amount(row.get("2024/2025"))
        if amount is None:
            continue
        group = clean_label(row.get("Type-detail2_eng") or "") or "Other public debt charges"
        detail3 = clean_label(row.get("Type-detail3_eng") or "")
        detail4 = clean_label(row.get("Type-detail4_eng") or "")
        leaf_name = detail4 or detail3 or group
        nested[group][leaf_name] += amount

    color = COLORS[5]
    sources = sources_pa()
    children: list[dict] = []
    for index, (group, details) in enumerate(
        sorted(nested.items(), key=lambda item: -abs(sum(item[1].values())))
    ):
        group_total = sum(details.values())
        detail_items = sorted(details.items(), key=lambda item: -abs(item[1]))
        if len(detail_items) == 1 and detail_items[0][0] == group:
            children.append(
                leaf(
                    node_id=slug(f"ca-debt-{group}"),
                    name=group,
                    amount=group_total,
                    color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.16),
                    description=(
                        f"Public Accounts FY {FISCAL_YEAR_LABEL}: public debt charges — {group}."
                    ),
                    sources=sources,
                )
            )
            continue

        detail_amounts = reconcile_amounts(
            group_total, [amount for _, amount in detail_items]
        )
        detail_children = []
        for j, ((name, _), amount) in enumerate(zip(detail_items, detail_amounts)):
            detail_children.append(
                leaf(
                    node_id=slug(f"ca-debt-{group}-{name}"),
                    name=name,
                    amount=amount,
                    color=mix_hex(color, "#ffffff" if j % 2 == 0 else "#1f3d4d", 0.22),
                    description=(
                        f"Public Accounts FY {FISCAL_YEAR_LABEL}: {group} — {name}."
                    ),
                    sources=sources,
                )
            )
        children.append(
            branch(
                node_id=slug(f"ca-debt-{group}"),
                name=group,
                amount=group_total,
                color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.12),
                description=(
                    f"Public Accounts FY {FISCAL_YEAR_LABEL}: public debt charges — {group}."
                ),
                sources=sources,
                children=detail_children,
            )
        )

    assert_sum(
        "Public debt charges",
        FRT_SPENDING["public_debt"]["amount"],
        [c["amountMillions"] for c in children],
    )
    return children


def build_direct_program(color: str) -> dict:
    frt = sources_frt()
    otp_color = mix_hex(color, "#ffffff", 0.08)
    ode_color = mix_hex(color, "#1f3d4d", 0.08)
    otp_amount = FRT_SPENDING["direct_program"]["other_transfer_payments"]
    ode_amount = FRT_SPENDING["direct_program"]["other_direct"]
    kids = [
        branch(
            node_id="ca-direct-other-transfer-payments",
            name="Other transfer payments",
            amount=otp_amount,
            color=otp_color,
            description=(
                f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: other transfer payments "
                "inside direct program, detailed by ministry from Public Accounts."
            ),
            sources=frt + sources_otp(),
            children=other_transfer_payment_ministries(otp_color),
        ),
        branch(
            node_id="ca-direct-other-direct-program-expenses",
            name="Other direct program expenses",
            amount=ode_amount,
            color=ode_color,
            description=(
                f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: other direct program expenses, "
                "detailed by ministry and entity from Public Accounts. A consolidation residual "
                "bridges the MET ministry total to the FRT figure."
            ),
            sources=frt + sources_met(),
            children=other_direct_program_ministries(ode_color),
        ),
    ]
    return branch(
        node_id="ca-direct-program-expenses",
        name="Direct program expenses",
        amount=FRT_SPENDING["direct_program"]["amount"],
        color=color,
        description=f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: Direct program expenses.",
        sources=frt,
        children=kids,
    )


def build_spending_tree(rows: list[dict]) -> dict:
    frt = sources_frt()
    pa = sources_pa()
    children: list[dict] = []

    order = [
        "major_transfers_persons",
        "major_transfers_provinces",
        "other_transfer_payments",
        "direct_program",
        "pollution_pricing",
        "public_debt",
    ]
    for index, key in enumerate(order):
        spec = FRT_SPENDING[key]
        color = COLORS[index % len(COLORS)]
        if key == "public_debt":
            kids = public_debt_children(rows)
            src = frt + pa[1:]
            desc = (
                f"Finance Canada Fiscal Reference Tables, FY {FISCAL_YEAR_LABEL}. "
                "Public debt charge detail from Public Accounts."
            )
            children.append(
                branch(
                    node_id=slug(f"ca-{spec['name']}"),
                    name=spec["name"],
                    amount=spec["amount"],
                    color=color,
                    description=desc,
                    sources=src,
                    children=kids,
                )
            )
        elif key == "direct_program":
            children.append(build_direct_program(color))
        elif spec.get("children"):
            kids = []
            for j, child in enumerate(spec["children"]):
                kids.append(
                    leaf(
                        node_id=slug(f"ca-{key}-{child['name']}"),
                        name=child["name"],
                        amount=child["amount"],
                        color=mix_hex(color, "#ffffff" if j % 2 == 0 else "#1f3d4d", 0.16),
                        description=(
                            f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: "
                            f"{spec['name']} — {child['name']}."
                        ),
                        sources=frt,
                    )
                )
            children.append(
                branch(
                    node_id=slug(f"ca-{spec['name']}"),
                    name=spec["name"],
                    amount=spec["amount"],
                    color=color,
                    description=f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: {spec['name']}.",
                    sources=frt,
                    children=kids,
                )
            )
        else:
            children.append(
                leaf(
                    node_id=slug(f"ca-{spec['name']}"),
                    name=spec["name"],
                    amount=spec["amount"],
                    color=color,
                    description=f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: {spec['name']}.",
                    sources=frt,
                )
            )

    total = sum(FRT_SPENDING[k]["amount"] for k in order)
    assert_sum("Canadian federal spending", total, [c["amountMillions"] for c in children])

    return branch(
        node_id="ca-federal-outlays",
        name="Canadian Federal Spending",
        amount=total,
        color="#1f3d4d",
        description=(
            f"FY {FISCAL_YEAR_LABEL} actual Canadian federal expenses from Finance Canada "
            "Fiscal Reference Tables, with Public Accounts ministry and debt detail. "
            "Click a category to open its components."
        ),
        sources=frt,
        children=children,
    )


def nest_from_rows(
    rows: list[dict],
    *,
    path_keys: list[str],
    color: str,
    id_prefix: str,
    sources: list[dict[str, str]],
) -> list[dict]:
    """Build a nested SpendNode forest from PA rows using successive detail columns."""
    tree: dict = {}

    def amount_of(row: dict) -> float:
        value = parse_amount(row.get("2024/2025"))
        if value is None:
            raise RuntimeError(f"Missing amount for {row}")
        return value

    for row in rows:
        labels = []
        for key in path_keys:
            label = clean_label(row.get(key) or "")
            if label:
                labels.append(label)
        if not labels:
            continue
        cursor = tree
        for label in labels[:-1]:
            cursor = cursor.setdefault(label, {"__children__": {}, "__amount__": 0.0})[
                "__children__"
            ]
        leaf_label = labels[-1]
        node = cursor.setdefault(leaf_label, {"__children__": {}, "__amount__": 0.0})
        node["__amount__"] += amount_of(row)

    def node_total(payload: dict) -> float:
        if payload["__children__"]:
            return payload["__amount__"] + sum(
                node_total(child) for child in payload["__children__"].values()
            )
        return payload["__amount__"]

    def to_nodes(mapping: dict, prefix: str, depth: int) -> list[dict]:
        items = [(name, payload, node_total(payload)) for name, payload in mapping.items()]
        items.sort(key=lambda item: -abs(item[2]))
        nodes: list[dict] = []
        for index, (name, payload, total) in enumerate(items):
            child_map = payload["__children__"]
            node_id = slug(f"{prefix}-{name}")
            tint = mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.12 + 0.04 * depth)
            if child_map:
                kids = to_nodes(child_map, node_id, depth + 1)
                own = round1(payload["__amount__"])
                if own != 0:
                    kids.append(
                        leaf(
                            node_id=slug(f"{node_id}-other"),
                            name="Other",
                            amount=own,
                            color=mix_hex(color, "#1f3d4d", 0.28),
                            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: {name} — other.",
                            sources=sources,
                        )
                    )
                    kids.sort(key=lambda node: -abs(node["amountMillions"]))
                nodes.append(
                    branch(
                        node_id=node_id,
                        name=name,
                        amount=total,
                        color=tint,
                        description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: {name}.",
                        sources=sources,
                        children=kids,
                    )
                )
            else:
                nodes.append(
                    leaf(
                        node_id=node_id,
                        name=name,
                        amount=total,
                        color=tint,
                        description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: {name}.",
                        sources=sources,
                    )
                )
        return nodes

    return to_nodes(tree, id_prefix, 0)


def build_revenue_tree(rows: list[dict]) -> dict:
    """Multi-layer Public Accounts revenue tree."""
    pa = sources_pa()
    revenue_rows = [r for r in rows if r.get("Account_Compte_eng") == "Revenues"]

    def amount_of(row: dict) -> float:
        value = parse_amount(row.get("2024/2025"))
        if value is None:
            raise RuntimeError(f"Missing amount for {row}")
        return value

    tax_rows = [r for r in revenue_rows if (r.get("Type-detail_eng") or "") == "Tax revenues"]
    tax_children = nest_from_rows(
        tax_rows,
        path_keys=[
            "Type-detail2_eng",
            "Type-detail3_eng",
            "Type-detail4_eng",
            "Type-detail5_eng",
        ],
        color=COLORS[0],
        id_prefix="ca-tax",
        sources=pa,
    )
    tax_total = sum(c["amountMillions"] for c in tax_children)

    ei = next(
        amount_of(r)
        for r in revenue_rows
        if (r.get("Type-detail_eng") or "") == "Employment insurance premiums"
    )
    pollution = next(
        amount_of(r)
        for r in revenue_rows
        if (r.get("Type-detail_eng") or "") == "Pollution pricing proceeds"
    )

    other_rows = [r for r in revenue_rows if (r.get("Type-detail_eng") or "") == "Other revenues"]
    other_children = nest_from_rows(
        other_rows,
        path_keys=[
            "Type-detail2_eng",
            "Type-detail3_eng",
            "Type-detail4_eng",
            "Type-detail5_eng",
        ],
        color=COLORS[3],
        id_prefix="ca-other-rev",
        sources=pa,
    )
    other_total = sum(c["amountMillions"] for c in other_children)

    children = [
        branch(
            node_id="ca-tax-revenues",
            name="Tax revenues",
            amount=tax_total,
            color=COLORS[0],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Tax revenues.",
            sources=pa,
            children=tax_children,
        ),
        leaf(
            node_id="ca-employment-insurance-premiums",
            name="Employment insurance premiums",
            amount=ei,
            color=COLORS[1],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Employment insurance premiums.",
            sources=pa,
        ),
        leaf(
            node_id="ca-pollution-pricing-proceeds",
            name="Pollution pricing proceeds",
            amount=pollution,
            color=COLORS[2],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Pollution pricing proceeds.",
            sources=pa,
        ),
        branch(
            node_id="ca-other-revenues",
            name="Other revenues",
            amount=other_total,
            color=COLORS[3],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Other revenues.",
            sources=pa,
            children=other_children,
        ),
    ]
    total = tax_total + ei + pollution + other_total
    assert_sum("Canadian federal revenue", total, [c["amountMillions"] for c in children])

    return branch(
        node_id="ca-federal-receipts",
        name="Canadian Federal Revenue",
        amount=total,
        color="#1f3d4d",
        description=(
            f"FY {FISCAL_YEAR_LABEL} actual Canadian federal revenues from the Public Accounts "
            "of Canada. Click a source to open income-tax, GST, and other revenue detail."
        ),
        sources=pa,
        children=children,
    )


def dataset_shell(
    *,
    root: dict,
    table: str,
    title: str,
    spreadsheet_url: str,
    historical_url: str,
    extra: dict | None = None,
) -> dict:
    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omb": {
            "table": table,
            "title": title,
            "fiscalYear": FISCAL_YEAR,
            "fiscalYearLabel": FISCAL_YEAR_LABEL,
            "status": STATUS,
            "units": "millions of dollars",
            "publication": "Public Accounts of Canada / Fiscal Reference Tables",
            "dateIssued": None,
            "zipUrl": spreadsheet_url,
            "spreadsheetUrl": spreadsheet_url,
            "detailsUrl": historical_url,
            "historicalTablesUrl": historical_url,
            "amountMillions": root["amountMillions"],
            "onBudgetMillions": root["amountMillions"],
            "offBudgetMillions": 0.0,
        },
        "treasuryMts": {
            "recordDate": f"{FISCAL_YEAR}-03-31",
            "fiscalYear": FISCAL_YEAR,
            "periodLabel": f"FY {FISCAL_YEAR_LABEL} annual (Public Accounts)",
            "receipts": root["amountMillions"] * 1_000_000
            if "Revenue" in root["name"]
            else 0.0,
            "netOutlays": root["amountMillions"] * 1_000_000
            if "Spending" in root["name"]
            else 0.0,
            "queryUrl": spreadsheet_url,
            "datasetUrl": historical_url,
            "latestRecordQueryUrl": spreadsheet_url,
        },
        "root": root,
    }
    if extra:
        payload.update(extra)
    return payload


def main() -> None:
    rows = load_public_accounts()
    spending_root = build_spending_tree(rows)
    revenue_root = build_revenue_tree(rows)

    pa_revenue = sum(
        parse_amount(r.get("2024/2025")) or 0.0
        for r in rows
        if r.get("Account_Compte_eng") == "Revenues"
    )
    if round1(pa_revenue) != round1(revenue_root["amountMillions"]):
        raise RuntimeError("Revenue tree total does not match Public Accounts CSV sum")

    outlays = dataset_shell(
        root=spending_root,
        table="FRT 7 / 10–13 + Public Accounts OTP/MET",
        title="Federal expenses by major category (Fiscal Reference Tables + Public Accounts)",
        spreadsheet_url=FRT_PDF_URL,
        historical_url=FRT_PAGE_URL,
        extra={
            "gdp": {
                "fiscalYear": FISCAL_YEAR,
                "status": STATUS,
                "table": "FRT Table 1 / 2",
                "title": "Canadian GDP (implied from budgetary balance as % of GDP)",
                "units": "billions of dollars",
                "amountBillions": CANADA_GDP_BILLIONS,
                "amountMillions": CANADA_GDP_BILLIONS * 1000.0,
                "spreadsheetUrl": FRT_PDF_URL,
                "historicalTablesUrl": FRT_PAGE_URL,
                "detailsUrl": FRT_PAGE_URL,
            },
            "publicAccounts": {
                "url": PUBLIC_ACCOUNTS_URL,
                "datasetUrl": PUBLIC_ACCOUNTS_DATASET,
                "otpUrl": OTP_URL,
                "metUrl": MET_URL,
                "expenseMillions": sum(
                    parse_amount(r.get("2024/2025")) or 0.0
                    for r in rows
                    if r.get("Account_Compte_eng") == "Expenses"
                ),
            },
            "highlights": {
                "interest": {
                    "name": "Public debt charges",
                    "amountMillions": next(
                        child["amountMillions"]
                        for child in spending_root["children"]
                        if child["name"] == "Public debt charges"
                    ),
                    "nodeId": "ca-public-debt-charges",
                    "note": "From this file's spending tree (FRT / Public Accounts)",
                },
                "defense": {
                    "name": "National Defence",
                    "amountMillions": CANADA_NATIONAL_DEFENCE_MILLIONS,
                    "nodeId": "ca-ode-national-defence",
                    "note": (
                        "Department of National Defence FY "
                        f"{FISCAL_YEAR_LABEL} actuals (GC Infobase / Public Accounts). "
                        "Drillable under Direct program → Other direct program expenses."
                    ),
                },
            },
        },
    )
    outlays["treasuryMts"]["netOutlays"] = spending_root["amountMillions"] * 1_000_000
    outlays["treasuryMts"]["receipts"] = revenue_root["amountMillions"] * 1_000_000

    receipts = dataset_shell(
        root=revenue_root,
        table="Public Accounts",
        title="Federal revenues by source (Public Accounts of Canada)",
        spreadsheet_url=PUBLIC_ACCOUNTS_URL,
        historical_url=PUBLIC_ACCOUNTS_DATASET,
    )
    receipts["treasuryMts"]["receipts"] = revenue_root["amountMillions"] * 1_000_000
    receipts["treasuryMts"]["netOutlays"] = spending_root["amountMillions"] * 1_000_000

    OUTLAYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTLAYS_PATH.write_text(json.dumps(outlays, indent=2) + "\n", encoding="utf-8")
    RECEIPTS_PATH.write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTLAYS_PATH}")
    print(f"Wrote {RECEIPTS_PATH}")
    print(f"FY {FISCAL_YEAR_LABEL} spending: {spending_root['amountMillions']} million")
    print(f"FY {FISCAL_YEAR_LABEL} revenue: {revenue_root['amountMillions']} million")
    print(
        f"Deficit: {round1(revenue_root['amountMillions'] - spending_root['amountMillions'])} million"
    )


if __name__ == "__main__":
    main()
