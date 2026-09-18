"""
Shared helpers for OMB Public Budget Database (BUDGET-*-DB) enrichment.

DB-2 outlays and DB-3 receipts are in thousands of dollars; convert to millions
to match OMB Historical Tables.
"""

from __future__ import annotations

import re
import ssl
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from io import BytesIO
from typing import Callable

SSML = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CTX = ssl.create_default_context()

PDB_ZIP_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-DB/zip/BUDGET-2027-DB.zip"
PDB_DETAILS_URL = "https://www.govinfo.gov/app/details/BUDGET-2027-DB"
PDB_OUTLAYS_PATH = "BUDGET-2027-DB/xls/BUDGET-2027-DB-2.xlsx"
PDB_RECEIPTS_PATH = "BUDGET-2027-DB/xls/BUDGET-2027-DB-3.xlsx"
PDB_OUTLAYS_XLSX_URL = (
    "https://www.govinfo.gov/content/pkg/BUDGET-2027-DB/xls/BUDGET-2027-DB-2.xlsx"
)
PDB_RECEIPTS_XLSX_URL = (
    "https://www.govinfo.gov/content/pkg/BUDGET-2027-DB/xls/BUDGET-2027-DB-3.xlsx"
)

# Table 3.2 National Defense memo lines map to DoD-Military (051) bureau names.
DEFENSE_BUREAU_LINES = {
    "Military Personnel",
    "Operation and Maintenance",
    "Procurement",
    "Research, Development, Test, and Evaluation",
    "Military Construction",
    "Family Housing",
}
DEFENSE_OTHER_BUREAUS = {
    "Revolving and Management Funds",
    "Trust Funds",
    "Department of Defense--Military Programs",
}

MATCH_TOLERANCE = 0.51  # millions


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mytaxspend.com budget refresh"})
    with urllib.request.urlopen(req, context=CTX, timeout=180) as resp:
        return resp.read()


def colrow(cell_ref: str) -> tuple[int, int]:
    col = "".join(ch for ch in cell_ref if ch.isalpha())
    row = int("".join(ch for ch in cell_ref if ch.isdigit()))
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n, row


def parse_xlsx_sheet(data: bytes) -> dict[int, dict[int, str]]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = []
        for si in ss.findall("a:si", SSML):
            strings.append("".join(t.text or "" for t in si.findall(".//a:t", SSML)))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows: dict[int, dict[int, str]] = {}
        for c in sheet.findall(".//a:c", SSML):
            ref = c.get("r")
            if not ref:
                continue
            col, row = colrow(ref)
            v = c.find("a:v", SSML)
            if v is None or v.text is None:
                continue
            val = strings[int(v.text)] if c.get("t") == "s" else v.text
            rows.setdefault(row, {})[col] = val
        return rows


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def unique_id(base: str, used: set[str], fallback: str) -> str:
    """Return a tree-unique id; append -2, -3, … on collision."""
    candidate = slug(base) or slug(fallback) or fallback
    if candidate not in used:
        used.add(candidate)
        return candidate
    n = 2
    while True:
        alt = f"{candidate}-{n}"
        if alt not in used:
            used.add(alt)
            return alt
        n += 1


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


def pdb_sources(kind: str) -> list[dict[str, str]]:
    spreadsheet = PDB_OUTLAYS_XLSX_URL if kind == "outlays" else PDB_RECEIPTS_XLSX_URL
    label = (
        "OMB Public Budget Database — outlays (DB-2)"
        if kind == "outlays"
        else "OMB Public Budget Database — receipts (DB-3)"
    )
    return [
        {"label": label, "url": PDB_DETAILS_URL},
        {"label": "Public Budget Database ZIP", "url": PDB_ZIP_URL},
        {"label": "Spreadsheet", "url": spreadsheet},
    ]


def pdb_sources_compact(kind: str) -> list[dict[str, str]]:
    """Single link for deep agency/account nodes to keep the JSON small."""
    return [pdb_sources(kind)[0]]


def load_pdb_outlay_sheet() -> dict[int, dict[int, str]]:
    zip_bytes = fetch(PDB_ZIP_URL)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        return parse_xlsx_sheet(z.read(PDB_OUTLAYS_PATH))


def load_pdb_receipt_sheet() -> dict[int, dict[int, str]]:
    zip_bytes = fetch(PDB_ZIP_URL)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        return parse_xlsx_sheet(z.read(PDB_RECEIPTS_PATH))


def load_pdb_sheets() -> tuple[dict[int, dict[int, str]], dict[int, dict[int, str]]]:
    zip_bytes = fetch(PDB_ZIP_URL)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        outlays = parse_xlsx_sheet(z.read(PDB_OUTLAYS_PATH))
        receipts = parse_xlsx_sheet(z.read(PDB_RECEIPTS_PATH))
    return outlays, receipts


def year_column(header: dict[int, str], fiscal_year: int) -> int:
    target = str(fiscal_year)
    for col, val in header.items():
        if str(val).strip() == target:
            return col
    raise RuntimeError(f"Public Budget Database sheet has no column for FY {fiscal_year}")


def parse_outlay_entries(
    rows: dict[int, dict[int, str]], fiscal_year: int
) -> list[dict]:
    """Return non-zero FY outlay lines in millions of dollars."""
    ycol = year_column(rows[1], fiscal_year)
    entries: list[dict] = []
    for r, row in rows.items():
        if r == 1:
            continue
        raw = row.get(ycol)
        if raw is None or str(raw).strip() in {"", "N/A"}:
            continue
        amount = float(raw) / 1000.0
        if abs(amount) < 1e-12:
            continue
        entries.append(
            {
                "agency": str(row.get(2, "")).strip() or "(Unspecified agency)",
                "agencyCode": str(row.get(1, "")).strip() or "x",
                "bureau": str(row.get(4, "")).strip() or "(Unspecified bureau)",
                "bureauCode": str(row.get(3, "")).strip() or "x",
                "account": str(row.get(6, "")).strip() or "(Unspecified account)",
                "accountCode": str(row.get(5, "")).strip(),
                "subfunction": str(row.get(9, "")).strip().zfill(3),
                "subfunctionTitle": str(row.get(10, "")).strip(),
                "amount": amount,
            }
        )
    return entries


def parse_receipt_entries(
    rows: dict[int, dict[int, str]], fiscal_year: int
) -> list[dict]:
    """Return non-zero FY receipt lines in millions of dollars."""
    ycol = year_column(rows[1], fiscal_year)
    entries: list[dict] = []
    for r, row in rows.items():
        if r == 1:
            continue
        raw = row.get(ycol)
        if raw is None or str(raw).strip() in {"", "N/A"}:
            continue
        amount = float(raw) / 1000.0
        if abs(amount) < 1e-12:
            continue
        entries.append(
            {
                "sourceCategory": str(row.get(1, "")).strip().zfill(3),
                "sourceCategoryName": str(row.get(2, "")).strip(),
                "sourceSubcategory": str(row.get(3, "")).strip(),
                "sourceSubcategoryName": str(row.get(4, "")).strip(),
                "agency": str(row.get(6, "")).strip() or "(Unspecified agency)",
                "agencyCode": str(row.get(5, "")).strip() or "x",
                "bureau": str(row.get(8, "")).strip() or "(Unspecified bureau)",
                "bureauCode": str(row.get(7, "")).strip() or "x",
                "account": str(row.get(10, "")).strip() or "(Unspecified account)",
                "accountCode": str(row.get(9, "")).strip(),
                "amount": amount,
            }
        )
    return entries


def _fix_child_sum(children: list[dict], target: float) -> None:
    if not children:
        return
    drift = round1(target) - round1(sum(c["amountMillions"] for c in children))
    if abs(drift) < 1e-9:
        return
    biggest = max(children, key=lambda c: abs(c["amountMillions"]))
    biggest["amountMillions"] = round1(biggest["amountMillions"] + drift)


def _account_nodes(
    accounts: dict[str, dict],
    *,
    parent_id: str,
    parent_color: str,
    sources: list[dict[str, str]],
    desc_prefix: str,
    used_ids: set[str],
) -> list[dict]:
    items = [
        (name, meta)
        for name, meta in accounts.items()
        if abs(meta["amount"]) >= 1e-12
    ]
    items.sort(key=lambda item: (-abs(item[1]["amount"]), item[0]))
    nodes: list[dict] = []
    for index, (name, meta) in enumerate(items):
        code = meta.get("code") or ""
        base = (
            f"{parent_id}-c{code}"
            if code
            else f"{parent_id}-acct-{name}"
        )
        nodes.append(
            {
                "id": unique_id(base, used_ids, f"{parent_id}-acct-{index}"),
                "name": name,
                "amountMillions": round1(meta["amount"]),
                "color": mix_hex(
                    parent_color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.22
                ),
                "description": f"Budget account: {name}.",
                "sources": sources,
            }
        )
    return nodes


def build_agency_bureau_account_tree(
    entries: list[dict],
    *,
    parent_id: str,
    parent_amount: float,
    parent_color: str,
    sources: list[dict[str, str]],
    desc_prefix: str,
    kind: str = "outlays",
) -> list[dict] | None:
    """
    Collapse Agency → Bureau → Account, skipping single-child intermediate levels.
    Returns None when there is nothing useful to drill into.
    """
    # agencyName -> {code, bureaus: bureauName -> {code, accounts: name -> {code, amount}}}
    nested: dict[str, dict] = {}
    for entry in entries:
        agency = entry["agency"]
        bureau = entry["bureau"]
        account = entry["account"]
        agency_node = nested.setdefault(
            agency, {"code": entry.get("agencyCode", "x"), "bureaus": {}}
        )
        bureau_node = agency_node["bureaus"].setdefault(
            bureau, {"code": entry.get("bureauCode", "x"), "accounts": {}}
        )
        acct = bureau_node["accounts"].setdefault(
            account, {"code": entry.get("accountCode", ""), "amount": 0.0}
        )
        acct["amount"] += entry["amount"]
        if not acct["code"] and entry.get("accountCode"):
            acct["code"] = entry["accountCode"]

    if not nested:
        return None

    deep_sources = pdb_sources_compact(kind)
    used_ids: set[str] = {parent_id}

    def bureau_children(
        bureaus: dict[str, dict], node_id: str, color: str
    ) -> list[dict]:
        if len(bureaus) == 1:
            only = next(iter(bureaus.values()))
            return _account_nodes(
                only["accounts"],
                parent_id=node_id,
                parent_color=color,
                sources=deep_sources,
                desc_prefix=desc_prefix,
                used_ids=used_ids,
            )
        nodes: list[dict] = []
        ordered = sorted(
            bureaus.items(),
            key=lambda item: (
                -abs(sum(a["amount"] for a in item[1]["accounts"].values())),
                item[0],
            ),
        )
        for index, (bureau_name, bureau_meta) in enumerate(ordered):
            accounts = bureau_meta["accounts"]
            amount = round1(sum(a["amount"] for a in accounts.values()))
            if abs(amount) < 1e-12 and not any(
                abs(a["amount"]) >= 1e-12 for a in accounts.values()
            ):
                continue
            child_id = unique_id(
                f"{node_id}-b{bureau_meta['code']}",
                used_ids,
                f"{node_id}-b-{index}",
            )
            color_i = mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.14)
            acct_nodes = _account_nodes(
                accounts,
                parent_id=child_id,
                parent_color=color_i,
                sources=deep_sources,
                desc_prefix=desc_prefix,
                used_ids=used_ids,
            )
            node: dict = {
                "id": child_id,
                "name": bureau_name,
                "amountMillions": amount,
                "color": color_i,
                "description": f"{desc_prefix}: {bureau_name}.",
                "sources": deep_sources,
            }
            if len(acct_nodes) > 1 or (
                len(acct_nodes) == 1 and acct_nodes[0]["name"] != bureau_name
            ):
                _fix_child_sum(acct_nodes, amount)
                if acct_nodes:
                    node["children"] = acct_nodes
            nodes.append(node)
        return nodes

    agency_names = list(nested.keys())
    if len(agency_names) == 1:
        children = bureau_children(
            nested[agency_names[0]]["bureaus"], parent_id, parent_color
        )
    else:
        children = []
        ordered = sorted(
            nested.items(),
            key=lambda item: (
                -abs(
                    sum(
                        a["amount"]
                        for b in item[1]["bureaus"].values()
                        for a in b["accounts"].values()
                    )
                ),
                item[0],
            ),
        )
        for index, (agency_name, agency_meta) in enumerate(ordered):
            bureaus = agency_meta["bureaus"]
            amount = round1(
                sum(
                    a["amount"]
                    for b in bureaus.values()
                    for a in b["accounts"].values()
                )
            )
            child_id = unique_id(
                f"{parent_id}-a{agency_meta['code']}",
                used_ids,
                f"{parent_id}-a-{index}",
            )
            color_i = mix_hex(
                parent_color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.12
            )
            bureau_nodes = bureau_children(bureaus, child_id, color_i)
            node = {
                "id": child_id,
                "name": agency_name,
                "amountMillions": amount,
                "color": color_i,
                "description": f"{desc_prefix}: {agency_name}.",
                "sources": deep_sources,
            }
            if bureau_nodes:
                _fix_child_sum(bureau_nodes, amount)
                node["children"] = bureau_nodes
            children.append(node)

    if not children:
        return None
    # Skip enrichment when it would only restate the parent as a single account.
    if len(children) == 1 and not children[0].get("children"):
        only = children[0]
        if abs(only["amountMillions"] - round1(parent_amount)) <= MATCH_TOLERANCE:
            return None

    _fix_child_sum(children, parent_amount)
    child_sum = round1(sum(c["amountMillions"] for c in children))
    if abs(child_sum - round1(parent_amount)) > MATCH_TOLERANCE:
        return None
    return children


def _attach_if_match(
    node: dict,
    entries: list[dict],
    sources: list[dict[str, str]],
    desc_prefix: str,
    kind: str = "outlays",
) -> bool:
    if node.get("children"):
        return False
    if not entries:
        return False
    total = sum(e["amount"] for e in entries)
    if abs(total - node["amountMillions"]) > MATCH_TOLERANCE:
        return False
    children = build_agency_bureau_account_tree(
        entries,
        parent_id=node["id"],
        parent_amount=node["amountMillions"],
        parent_color=node["color"],
        sources=sources,
        desc_prefix=desc_prefix,
        kind=kind,
    )
    if not children:
        return False
    node["children"] = children
    existing = node.get("sources") or []
    merged = list(existing)
    seen = {s["url"] for s in merged}
    for src in sources:
        if src["url"] not in seen:
            merged.append(src)
            seen.add(src["url"])
    node["sources"] = merged
    if "Public Budget Database" not in node.get("description", ""):
        node["description"] = (
            node.get("description", "").rstrip(".")
            + ". Deeper agency/account detail from the OMB Public Budget Database."
        )
    return True


def enrich_outlay_tree(root: dict, entries: list[dict], fiscal_year: int) -> dict:
    """Attach Agency/Bureau/Account children under Table 3.2 leaves where sums match."""
    sources = pdb_sources("outlays")
    by_sf: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_sf[entry["subfunction"]].append(entry)

    stats = {"enriched": 0, "skipped": 0}

    def walk(node: dict, parent_function_code: str | None = None) -> None:
        children = node.get("children") or []
        if children:
            fn_code = node.get("code") if len(str(node.get("code") or "")) == 3 else parent_function_code
            # Function codes are 050, 150, …; subfunction codes are also 3 digits.
            # Prefer parent function when walking function → subfunction.
            next_fn = node["code"] if node.get("code") in {
                "050", "150", "250", "270", "300", "350", "370", "400", "450",
                "500", "550", "570", "600", "650", "700", "750", "800", "900",
                "920", "950",
            } else parent_function_code
            for child in children:
                walk(child, next_fn)
            return

        # Leaf enrichment
        matched: list[dict] | None = None
        code = str(node.get("code") or "").zfill(3) if node.get("code") else None
        name = node["name"]

        if code and code in by_sf:
            matched = by_sf[code]
        elif parent_function_code == "050" and name in DEFENSE_BUREAU_LINES:
            matched = [
                e
                for e in by_sf.get("051", [])
                if e["bureau"] == name
            ]
        elif parent_function_code == "050" and name == "Other":
            matched = [
                e
                for e in by_sf.get("051", [])
                if e["bureau"] in DEFENSE_OTHER_BUREAUS
            ]

        if matched is None:
            stats["skipped"] += 1
            return

        if _attach_if_match(
            node,
            matched,
            sources,
            f"OMB Public Budget Database FY {fiscal_year} outlays",
            kind="outlays",
        ):
            stats["enriched"] += 1
        else:
            stats["skipped"] += 1

    walk(root)
    return stats


def enrich_receipt_tree(root: dict, entries: list[dict], fiscal_year: int) -> dict:
    """Attach deeper agency/account detail under receipt leaves where sums match."""
    sources = pdb_sources("receipts")
    stats = {"enriched": 0, "skipped": 0}

    by_cat: dict[str, list[dict]] = defaultdict(list)
    by_sub: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in entries:
        by_cat[entry["sourceCategory"]].append(entry)
        by_sub[(entry["sourceCategory"], entry["sourceSubcategory"])].append(entry)

    category_by_id = {
        "individual-income-taxes": "931",
        "corporation-income-taxes": "932",
        "estate-and-gift-taxes": "935",
        "customs-duties-and-fees": "936",
    }

    employment_filters: dict[str, Callable[[str], bool]] = {
        "Trust funds (Off-Budget)": lambda a: a.startswith(
            "FOASI, Transfers from General Fund"
        ),
        "Disability insurance (Off-Budget)": lambda a: a.startswith(
            "FDI, Transfers from General Fund"
        ),
        "Hospital insurance": lambda a: a.startswith("FHI Trust Fund"),
        "Trust funds": lambda a: a == "Taxes, Rail Industry Pension Fund",
        "Railroad social security equivalent account": lambda a: (
            "Railroad Social Security Equivalent" in a
        ),
    }

    def try_attach(node: dict, matched: list[dict], label: str) -> None:
        if _attach_if_match(
            node,
            matched,
            sources,
            f"OMB Public Budget Database FY {fiscal_year} receipts ({label})",
            kind="receipts",
        ):
            stats["enriched"] += 1
        else:
            stats["skipped"] += 1

    def walk(node: dict, parent: dict | None = None) -> None:
        children = node.get("children") or []
        if children:
            for child in children:
                walk(child, node)
            return

        parent_id = parent["id"] if parent else ""
        parent_name = parent["name"] if parent else ""
        node_id = node["id"]
        name = node["name"]

        if parent_id == "unemployment-insurance" or parent_name == "Unemployment insurance":
            try_attach(node, by_sub[("933", "10")], "unemployment")
            return

        if parent_id == "employment-and-general-retirement" or parent_name == (
            "Employment and general retirement"
        ):
            pred = employment_filters.get(name)
            if pred:
                matched = [e for e in by_sub[("933", "05")] if pred(e["account"])]
                try_attach(node, matched, "employment")
                return

        if node_id in category_by_id:
            try_attach(node, by_cat[category_by_id[node_id]], node_id)
            return

        if node_id == "federal-reserve-deposits":
            matched = [
                e
                for e in by_cat["937"]
                if e["account"] == "Deposit of Earnings, Federal Reserve System"
            ]
            try_attach(node, matched, "Federal Reserve")
            return

        if node_id == "miscellaneous-all-other":
            matched = [
                e
                for e in by_cat["937"]
                if e["account"] != "Deposit of Earnings, Federal Reserve System"
            ]
            try_attach(node, matched, "miscellaneous")
            return

        if name == "Federal employees retirement - employee share":
            matched = [
                e
                for e in by_sub[("933", "15")]
                if "District of Columbia Contributions" not in e["account"]
            ]
            try_attach(node, matched, "other retirement")
            return

        if name == "Non-Federal employees retirement":
            matched = [
                e
                for e in by_sub[("933", "15")]
                if "District of Columbia Contributions" in e["account"]
            ]
            try_attach(node, matched, "other retirement")
            return

        if name == "Transportation" and abs(node["amountMillions"] - 43768.0) <= MATCH_TOLERANCE:
            matched = [
                e
                for e in by_sub[("934", "10")]
                if "Highway Trust Fund" in e["account"]
            ]
            try_attach(node, matched, "highway trust")
            return

        # Table 2.4 "Other" federal-fund excise = residual accounts not named above.
        if name == "Other" and (
            parent_id == "excise-federal-funds" or parent_name == "Federal funds"
        ):
            named_accounts = {
                "Alcohol Excise Tax",
                "Tobacco Excise Tax",
                "Telephone Excise Tax",
                "Transportation Fuels Tax",
                "Corporate Stock Repurchase Excise Tax",
                "Tax on Indoor Tanning Services",
            }
            matched = [
                e
                for e in by_sub[("934", "05")]
                if e["account"] not in named_accounts
            ]
            try_attach(node, matched, "other federal excise")
            return

        for cat_entries in (by_sub[("934", "05")], by_sub[("934", "10")], by_cat["936"]):
            matched = [
                e
                for e in cat_entries
                if name.lower() in e["account"].lower()
                or e["account"].lower().startswith(name.lower())
            ]
            if (
                matched
                and abs(sum(e["amount"] for e in matched) - node["amountMillions"])
                <= MATCH_TOLERANCE
            ):
                try_attach(node, matched, "account match")
                return

        stats["skipped"] += 1

    walk(root)
    return stats
