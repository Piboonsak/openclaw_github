"""Validate expectations.filled.jsonl and build a vendor-grouped review queue."""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

EXPECTATION_KEYS = [
    "doc_id",
    "split",
    "include_in_training",
    "exclusion_reason",
    "file_name",
    "relative_path",
    "labeling_status",
    "doc_type",
    "party_type",
    "invoice_number",
    "invoice_date",
    "due_date",
    "seller_name",
    "seller_tax_id",
    "buyer_name",
    "buyer_tax_id",
    "branch_code",
    "currency",
    "net_amount",
    "vat_rate",
    "vat_amount",
    "wht_rate",
    "wht_amount",
    "total_amount",
    "payment_terms",
    "po_number",
    "reference_number",
    "page_count",
    "is_multi_page",
    "reviewer",
    "review_note",
]

VALID_SPLITS = {"train", "test", "val", "excluded"}
VALID_LABELING_STATUS = {
    "pending",
    "ai_draft",
    "ai_draft_needs_review",
    "human_verified",
    "excluded",
}

NOISE_MARKERS = (
    "taxinvoice",
    "deliveryorder",
    "original",
    "customer",
    "address",
    "branch",
    "vat",
    "code",
    "เลขที่",
    "วันที่",
    "ผู้ซื้อจะได้",
    "ชําระ",
    "ใบกํากับภาษี",
    "ใบส่งสินค้า",
)

ADDRESS_MARKERS = ("หมู่", "ต.", "อ.", "จ.", "จังหวัด", "แขวง", "เขต")


@dataclass
class QueueItem:
    doc_id: str
    vendor_key: str
    vendor_label: str
    risk_score: int
    risk_level: str
    reasons: list[str]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _looks_noisy_name(value: str) -> bool:
    text = _normalize_text(value).lower()
    if not text:
        return True
    if any(marker in text for marker in NOISE_MARKERS):
        return True
    if len(text) <= 2:
        return True
    return False


def _looks_address_like(value: str) -> bool:
    text = _normalize_text(value)
    return any(marker in text for marker in ADDRESS_MARKERS)


def _looks_bad_invoice_number(value: str) -> bool:
    text = _normalize_text(value)
    if not text:
        return True
    if _looks_address_like(text):
        return True
    if len(text) > 30:
        return True
    if not re.search(r"\d", text):
        return True
    return False


def _valid_tax_id(value: str) -> bool:
    text = re.sub(r"\D", "", str(value or ""))
    return len(text) == 13


def _vendor_key(row: dict[str, Any]) -> tuple[str, str]:
    seller_tax_id = re.sub(r"\D", "", str(row.get("seller_tax_id") or ""))
    seller_name = _normalize_text(str(row.get("seller_name") or ""))
    if seller_tax_id:
        return seller_tax_id, seller_name or seller_tax_id
    compact = re.sub(r"[^A-Za-z0-9ก-๙]+", "", seller_name).upper()
    compact = compact[:40] or str(row.get("doc_id") or "unknown")
    return compact, seller_name or compact


def validate_row(row: dict[str, Any], idx: int) -> list[str]:
    errors: list[str] = []
    missing = [key for key in EXPECTATION_KEYS if key not in row]
    if missing:
        errors.append(f"row {idx}: missing keys {missing}")
    extra = sorted(set(row.keys()) - set(EXPECTATION_KEYS))
    if extra:
        errors.append(f"row {idx}: unexpected keys {extra}")

    split = str(row.get("split") or "")
    if split and split not in VALID_SPLITS:
        errors.append(f"row {idx}: invalid split '{split}'")

    labeling_status = str(row.get("labeling_status") or "")
    if labeling_status and labeling_status not in VALID_LABELING_STATUS:
        errors.append(f"row {idx}: invalid labeling_status '{labeling_status}'")

    if labeling_status == "excluded" and bool(row.get("include_in_training")):
        errors.append(f"row {idx}: excluded row cannot include_in_training=true")

    if not str(row.get("doc_id") or "").strip():
        errors.append(f"row {idx}: doc_id must be non-empty")

    return errors


def score_row(row: dict[str, Any], known_buyer_tax_ids: set[str]) -> QueueItem | None:
    if str(row.get("labeling_status") or "") == "excluded":
        return None

    reasons: list[str] = []
    score = 0

    invoice_number = str(row.get("invoice_number") or "")
    invoice_date = str(row.get("invoice_date") or "")
    seller_name = str(row.get("seller_name") or "")
    buyer_name = str(row.get("buyer_name") or "")
    seller_tax_id = str(row.get("seller_tax_id") or "")
    buyer_tax_id = str(row.get("buyer_tax_id") or "")
    net_amount = _to_decimal(row.get("net_amount"))
    vat_rate = _to_decimal(row.get("vat_rate"))
    vat_amount = _to_decimal(row.get("vat_amount"))
    wht_rate = _to_decimal(row.get("wht_rate"))
    wht_amount = _to_decimal(row.get("wht_amount"))
    total_amount = _to_decimal(row.get("total_amount"))
    review_note = str(row.get("review_note") or "")

    if _looks_bad_invoice_number(invoice_number):
        reasons.append("invoice_number missing or looks like address/noise")
        score += 4

    if invoice_date:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", invoice_date)
        if not match:
            reasons.append("invoice_date format invalid")
            score += 3
        else:
            year = int(match.group(1))
            if year < 2020 or year > 2035:
                reasons.append("invoice_date year out of expected range")
                score += 5
    else:
        reasons.append("invoice_date missing")
        score += 2

    if _looks_noisy_name(seller_name):
        reasons.append("seller_name missing or OCR noise")
        score += 4
    if _looks_noisy_name(buyer_name):
        reasons.append("buyer_name missing or OCR noise")
        score += 4

    if seller_tax_id and not _valid_tax_id(seller_tax_id):
        reasons.append("seller_tax_id invalid length")
        score += 3
    if buyer_tax_id and not _valid_tax_id(buyer_tax_id):
        reasons.append("buyer_tax_id invalid length")
        score += 3
    if known_buyer_tax_ids and buyer_tax_id and buyer_tax_id not in known_buyer_tax_ids:
        reasons.append("buyer_tax_id not in expected company tax IDs")
        score += 4
    if known_buyer_tax_ids and not buyer_tax_id:
        reasons.append("buyer_tax_id missing")
        score += 3

    if vat_rate is not None and vat_rate not in {Decimal("0"), Decimal("7")}:
        reasons.append("vat_rate outside expected values")
        score += 6

    if total_amount is not None and total_amount <= 0:
        reasons.append("total_amount is zero or negative")
        score += 6
    if total_amount is None:
        reasons.append("total_amount missing")
        score += 3

    if (
        vat_amount is not None
        and total_amount is not None
        and vat_amount >= total_amount
    ):
        reasons.append("vat_amount >= total_amount")
        score += 7

    if (
        total_amount is not None
        and vat_amount is not None
        and total_amount <= Decimal("20")
        and vat_amount >= Decimal("50")
    ):
        reasons.append("tiny total_amount with large vat_amount")
        score += 8

    if net_amount is not None and vat_amount is not None and total_amount is not None:
        diff = abs((net_amount + vat_amount) - total_amount)
        if diff > Decimal("2.00"):
            reasons.append("net_amount + vat_amount does not match total_amount")
            score += 6

    if (
        wht_rate is not None
        and wht_amount is not None
        and net_amount is not None
        and wht_rate > 0
    ):
        derived_base = (wht_amount * Decimal("100")) / wht_rate
        if abs(derived_base - net_amount) > Decimal("5.00"):
            reasons.append("wht_amount inconsistent with net_amount")
            score += 4

    if "derived net_amount from total_amount and vat_rate" in review_note:
        reasons.append("net_amount derived from total_amount and vat_rate")
        score += 2
    if "low_conf=" in review_note:
        reasons.append("pipeline marked low_conf fields")
        score += 2

    if score == 0:
        return None

    vendor_key, vendor_label = _vendor_key(row)
    if score >= 14:
        level = "high"
    elif score >= 8:
        level = "medium"
    else:
        level = "low"
    return QueueItem(
        doc_id=str(row.get("doc_id") or ""),
        vendor_key=vendor_key,
        vendor_label=vendor_label,
        risk_score=score,
        risk_level=level,
        reasons=reasons,
    )


def build_review_queue(
    rows: list[dict[str, Any]], known_buyer_tax_ids: set[str]
) -> dict[str, Any]:
    queue_items = [
        item for row in rows if (item := score_row(row, known_buyer_tax_ids))
    ]
    queue_items.sort(key=lambda item: (-item.risk_score, item.doc_id))

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"vendor_label": "", "items": []}
    )
    for item in queue_items:
        bucket = grouped[item.vendor_key]
        bucket["vendor_label"] = item.vendor_label
        bucket["items"].append(
            {
                "doc_id": item.doc_id,
                "risk_score": item.risk_score,
                "risk_level": item.risk_level,
                "reasons": item.reasons,
            }
        )

    vendors = []
    for vendor_key, payload in grouped.items():
        items = payload["items"]
        max_score = max(item["risk_score"] for item in items)
        vendors.append(
            {
                "vendor_key": vendor_key,
                "vendor_label": payload["vendor_label"],
                "doc_count": len(items),
                "max_risk_score": max_score,
                "items": items,
            }
        )
    vendors.sort(
        key=lambda item: (
            -item["max_risk_score"],
            -item["doc_count"],
            item["vendor_label"],
        )
    )

    return {
        "summary": {
            "documents_scanned": len(rows),
            "queued_documents": len(queue_items),
            "high_risk_documents": sum(
                1 for item in queue_items if item.risk_level == "high"
            ),
            "medium_risk_documents": sum(
                1 for item in queue_items if item.risk_level == "medium"
            ),
            "low_risk_documents": sum(
                1 for item in queue_items if item.risk_level == "low"
            ),
            "vendor_groups": len(vendors),
        },
        "vendors": vendors,
        "documents": [
            {
                "doc_id": item.doc_id,
                "vendor_key": item.vendor_key,
                "vendor_label": item.vendor_label,
                "risk_score": item.risk_score,
                "risk_level": item.risk_level,
                "reasons": item.reasons,
            }
            for item in queue_items
        ],
    }


def build_markdown_report(
    queue: dict[str, Any],
    generated_at: str = "",
) -> str:
    """Return a human-readable markdown worksheet from a review queue."""
    if not generated_at:
        generated_at = datetime.date.today().isoformat()

    summary = queue["summary"]
    vendors = queue["vendors"]

    risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    lines: list[str] = []

    lines.append(f"# Review Queue Worksheet — {generated_at}\n")

    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Documents scanned | {summary['documents_scanned']} |")
    lines.append(f"| Queued for review | {summary['queued_documents']} |")
    lines.append(f"| 🔴 High risk | {summary['high_risk_documents']} |")
    lines.append(f"| 🟡 Medium risk | {summary['medium_risk_documents']} |")
    lines.append(f"| 🟢 Low risk | {summary['low_risk_documents']} |")
    lines.append(f"| Vendor groups | {summary['vendor_groups']} |")
    lines.append("")
    lines.append("---\n")

    lines.append("## Vendor Worksheets\n")
    lines.append(
        "> Sorted by max risk score. "
        "Mark each row ✅ when review_note updated and labeling_status set to human_verified.\n"
    )

    for rank, vendor in enumerate(vendors, 1):
        vendor_label = vendor["vendor_label"]
        vendor_key = vendor["vendor_key"]
        doc_count = vendor["doc_count"]
        max_score = vendor["max_risk_score"]
        items = vendor["items"]

        lines.append(f"### {rank}. {vendor_label}")
        lines.append(
            f"`tax_id: {vendor_key}` — docs={doc_count}, max_score={max_score}\n"
        )
        lines.append("| doc_id | risk | score | top reasons |")
        lines.append("|--------|------|-------|-------------|")
        for item in items:
            emoji = risk_emoji.get(item["risk_level"], "⚪")
            top_reasons = "; ".join(item["reasons"][:3])
            lines.append(
                f"| {item['doc_id']} "
                f"| {emoji} {item['risk_level']} "
                f"| {item['risk_score']} "
                f"| {top_reasons} |"
            )
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate expectations.filled.jsonl and build a review queue"
    )
    parser.add_argument(
        "--input", required=True, help="Path to expectations.filled.jsonl"
    )
    parser.add_argument(
        "--queue-output", help="Optional path to write vendor-grouped review queue JSON"
    )
    parser.add_argument(
        "--report-output",
        help="Optional path to write a human-readable markdown review worksheet",
    )
    parser.add_argument(
        "--known-buyer-tax-id",
        action="append",
        default=[],
        help="Known buyer/company tax ID to validate against; may be provided multiple times",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        return 1

    rows = _read_jsonl(input_path)
    errors: list[str] = []
    seen_doc_ids: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        errors.extend(validate_row(row, idx))
        doc_id = str(row.get("doc_id") or "")
        if doc_id in seen_doc_ids:
            errors.append(f"row {idx}: duplicate doc_id '{doc_id}'")
        seen_doc_ids.add(doc_id)

    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1

    known_buyer_tax_ids = {
        re.sub(r"\D", "", item) for item in args.known_buyer_tax_id if str(item).strip()
    }
    queue = build_review_queue(rows, known_buyer_tax_ids)

    summary = queue["summary"]
    print(
        "OK: expectations file is valid | "
        f"queued={summary['queued_documents']} "
        f"high={summary['high_risk_documents']} "
        f"medium={summary['medium_risk_documents']} "
        f"low={summary['low_risk_documents']} "
        f"vendors={summary['vendor_groups']}"
    )

    for vendor in queue["vendors"][:10]:
        top = vendor["items"][0]
        print(
            f"QUEUE {vendor['vendor_label']} | docs={vendor['doc_count']} | "
            f"max_score={vendor['max_risk_score']} | top={top['doc_id']} -> {', '.join(top['reasons'][:3])}"
        )

    if args.queue_output:
        output_path = Path(args.queue_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"WROTE review queue -> {output_path}")

    if args.report_output:
        report_path = Path(args.report_output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(build_markdown_report(queue), encoding="utf-8")
        print(f"WROTE markdown report -> {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
