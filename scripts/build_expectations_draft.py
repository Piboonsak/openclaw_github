from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.backend.ml.field_extractor import run_extraction
from src.backend.ml.ocr import run_ocr

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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _to_money(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _derive_amounts(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    net = _to_money(str(fields.get("net_amount") or ""))
    vat = _to_money(str(fields.get("vat_amount") or ""))
    total = _to_money(str(fields.get("total_amount") or ""))
    vat_rate_raw = str(fields.get("vat_rate") or "").strip()

    if (net is None or vat is None) and total is not None and vat_rate_raw:
        try:
            rate = Decimal(vat_rate_raw)
        except Exception:
            rate = None
        if rate and rate > 0:
            base = (total / (Decimal("1") + (rate / Decimal("100")))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            vat_from_total = (total - base).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if net is None:
                fields["net_amount"] = _fmt_money(base)
                notes.append("derived net_amount from total_amount and vat_rate")
            if vat is None:
                fields["vat_amount"] = _fmt_money(vat_from_total)
                notes.append("derived vat_amount from total_amount and vat_rate")

    net = _to_money(str(fields.get("net_amount") or ""))
    wht_rate = _to_money(str(fields.get("wht_rate") or ""))
    wht_amount = _to_money(str(fields.get("wht_amount") or ""))
    if net is None and wht_rate and wht_rate > 0 and wht_amount is not None:
        net_from_wht = ((wht_amount * Decimal("100")) / wht_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        fields["net_amount"] = _fmt_money(net_from_wht)
        notes.append("derived net_amount from wht_amount and wht_rate")

    return fields, notes


def _make_row_base(manifest_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": manifest_row.get("doc_id", ""),
        "split": manifest_row.get("split", ""),
        "include_in_training": bool(manifest_row.get("include_in_training", True)),
        "exclusion_reason": manifest_row.get("exclusion_reason", ""),
        "file_name": manifest_row.get("file_name", ""),
        "relative_path": manifest_row.get("relative_path", ""),
        "labeling_status": "pending",
        "doc_type": "",
        "party_type": "",
        "invoice_number": "",
        "invoice_date": "",
        "due_date": "",
        "seller_name": "",
        "seller_tax_id": "",
        "buyer_name": "",
        "buyer_tax_id": "",
        "branch_code": "",
        "currency": "THB",
        "net_amount": "",
        "vat_rate": "",
        "vat_amount": "",
        "wht_rate": "",
        "wht_amount": "",
        "total_amount": "",
        "payment_terms": "",
        "po_number": "",
        "reference_number": "",
        "page_count": "",
        "is_multi_page": "",
        "reviewer": "",
        "review_note": "",
    }


def _build_row_from_extraction(
    manifest_row: dict[str, Any], extraction: dict[str, Any], ocr: dict[str, Any]
) -> dict[str, Any]:
    row = _make_row_base(manifest_row)
    fields = dict(extraction.get("fields") or {})

    row["doc_type"] = str(fields.get("doc_type") or "")
    row["invoice_number"] = str(fields.get("invoice_number") or "")
    row["invoice_date"] = str(fields.get("invoice_date") or "")
    row["seller_name"] = str(fields.get("seller_name") or "")
    row["seller_tax_id"] = str(fields.get("seller_tax_id") or "")
    row["buyer_name"] = str(fields.get("buyer_name") or "")
    row["buyer_tax_id"] = str(fields.get("buyer_tax_id") or "")
    row["net_amount"] = str(fields.get("net_amount") or "")
    row["vat_rate"] = str(fields.get("vat_rate") or "")
    row["vat_amount"] = str(fields.get("vat_amount") or "")
    row["wht_rate"] = str(fields.get("wht_rate") or "")
    row["wht_amount"] = str(fields.get("wht_amount") or "")
    row["total_amount"] = str(fields.get("total_amount") or "")

    rel = str(manifest_row.get("relative_path") or "")
    if "บิลซื้อ" in rel:
        row["party_type"] = "purchase"

    row["page_count"] = str(ocr.get("page_count") or "")
    row["is_multi_page"] = "true" if int(ocr.get("page_count") or 1) > 1 else "false"

    row, derive_notes = _derive_amounts(row)

    low_fields = extraction.get("low_confidence_fields") or []
    needs_review = bool(extraction.get("needs_human_review"))
    row["labeling_status"] = "ai_draft_needs_review" if needs_review else "ai_draft"

    note_parts = [
        f"AI draft from pipeline ocr={float(ocr.get('avg_confidence') or 0.0):.3f}",
        f"schema={extraction.get('schema_version')}",
    ]
    if low_fields:
        note_parts.append("low_conf=" + ",".join(str(x) for x in low_fields))
    if derive_notes:
        note_parts.append("; ".join(derive_notes))
    row["review_note"] = " | ".join(note_parts)

    return row


def _keep_only_schema(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k, "") for k in EXPECTATION_KEYS}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build expectations.filled.jsonl from manifest + extraction"
    )
    parser.add_argument(
        "--manifest",
        default="private_data/poc/Comp_1/manifest.jsonl",
        help="Path to manifest jsonl",
    )
    parser.add_argument(
        "--output",
        default="private_data/poc/Comp_1/expectations.filled.jsonl",
        help="Path to output expectations jsonl",
    )
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Keep existing rows as-is when doc_id already exists",
    )
    parser.add_argument(
        "--clear-extraction-cache",
        action="store_true",
        help="Delete extraction cache artifact per manifest SHA before running",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / args.manifest
    output_path = repo_root / args.output

    manifest_rows = _read_jsonl(manifest_path)
    existing_rows = _read_jsonl(output_path)
    existing_by_doc_id = {
        str(r.get("doc_id") or ""): r for r in existing_rows if r.get("doc_id")
    }

    built_rows: list[dict[str, Any]] = []

    for idx, m in enumerate(manifest_rows, start=1):
        doc_id = str(m.get("doc_id") or "")
        file_path = Path(str(m.get("file_path") or ""))

        if args.preserve_existing and doc_id in existing_by_doc_id:
            built_rows.append(_keep_only_schema(existing_by_doc_id[doc_id]))
            print(f"[{idx}/{len(manifest_rows)}] keep existing {doc_id}")
            continue

        row = _make_row_base(m)

        if not bool(m.get("include_in_training", True)):
            row["labeling_status"] = "excluded"
            row["doc_type"] = "reference"
            row["review_note"] = "Excluded by manifest"
            built_rows.append(_keep_only_schema(row))
            print(f"[{idx}/{len(manifest_rows)}] excluded {doc_id}")
            continue

        if args.clear_extraction_cache:
            sha = str(m.get("sha256") or "").strip()
            if sha:
                cache_file = (
                    repo_root / "src/backend/ml/cache" / sha / "extraction_output.json"
                )
                if cache_file.exists():
                    cache_file.unlink()

        if not file_path.exists():
            row["labeling_status"] = "ai_draft_needs_review"
            row["review_note"] = "File not found on disk"
            built_rows.append(_keep_only_schema(row))
            print(f"[{idx}/{len(manifest_rows)}] missing file {doc_id}")
            continue

        print(f"[{idx}/{len(manifest_rows)}] process {doc_id} {m.get('file_name')}")
        ocr_output = run_ocr(str(file_path))
        extraction_output = run_extraction(ocr_output)
        row = _build_row_from_extraction(m, extraction_output, ocr_output)
        built_rows.append(_keep_only_schema(row))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in built_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Done. wrote {len(built_rows)} rows -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
