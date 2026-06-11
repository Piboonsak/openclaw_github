"""Generate AI accounting evaluation reports from expectations + live API predictions.

Modes
- -jsonanswer: export normalized answer key from expectations.filled.jsonl files.
- -full-report: evaluate all companies and generate combined + per-company HTML/JSON.
- -comp-report <comp id>/<comp name>: evaluate a single company.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POC_ROOT = REPO_ROOT / "private_data" / "poc"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "benchmark" / "eva_report"
DEFAULT_API_URL = "http://127.0.0.1:8000/api/process"
CONFIDENCE_HIGH_THRESHOLD = 85.0
CONFIDENCE_MED_THRESHOLD = 70.0


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str


FIELDS: list[FieldSpec] = [
    FieldSpec("net_amount", "Net Amount (THB)", "amount"),
    FieldSpec("total_amount", "Gross Amount (THB)", "amount"),
    FieldSpec("vat_amount", "VAT 7% (THB)", "amount"),
    FieldSpec("wht_amount", "WHT Amount (THB)", "amount"),
    FieldSpec("buyer_tax_id", "Buyer tax id", "tax"),
    FieldSpec("seller_tax_id", "Seller tax id", "tax"),
    FieldSpec("invoice_number", "invoice no", "invoice"),
    FieldSpec("invoice_date", "invoice date", "date"),
]

DEFAULT_COMPANY_ID_BY_FOLDER = {
    "Comp_1": "co-3",
}


def parse_num(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_empty_or_zero(value: float | None, tolerance: float = 0.01) -> bool:
    if value is None:
        return True
    return abs(value) <= tolerance


def eq_amount(expected: Any, predicted: Any, tolerance: float = 0.01) -> bool:
    exp_num = parse_num(expected)
    pred_num = parse_num(predicted)
    if is_empty_or_zero(exp_num, tolerance) and is_empty_or_zero(pred_num, tolerance):
        return True
    if exp_num is None or pred_num is None:
        return False
    return abs(exp_num - pred_num) <= tolerance


def normalize_tax_id(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def eq_tax_id(expected: Any, predicted: Any) -> bool:
    return normalize_tax_id(expected) == normalize_tax_id(predicted)


def normalize_invoice_number(value: Any) -> str:
    text = str(value or "").strip().upper()
    return re.sub(r"\s+", "", text)


def eq_invoice_number(expected: Any, predicted: Any) -> bool:
    return normalize_invoice_number(expected) == normalize_invoice_number(predicted)


def normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    text = text.replace(".", "-").replace("/", "-")
    text = re.sub(r"\s+", "", text)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y%m%d", "%d%m%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            year = parsed.year
            if year >= 2400:
                parsed = parsed.replace(year=year - 543)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        if year >= 2400:
            year -= 543
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return text


def eq_date(expected: Any, predicted: Any) -> bool:
    return normalize_date(expected) == normalize_date(predicted)


def format_amount(value: Any) -> str:
    num = parse_num(value)
    if num is None:
        return ""
    return f"{num:.2f}"


def format_percent(value: float) -> str:
    return f"{value:.2f}%"


def html_escape(value: Any) -> str:
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def discover_expectation_files(poc_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not poc_root.exists():
        return result

    for comp_dir in sorted([d for d in poc_root.iterdir() if d.is_dir()]):
        expectation_path = comp_dir / "expectations.filled.jsonl"
        if expectation_path.exists():
            result[comp_dir.name] = expectation_path
    return result


def resolve_doc_path(comp_dir: Path, row: dict[str, Any]) -> Path | None:
    relative = str(row.get("relative_path") or "").strip()
    if relative:
        candidate = comp_dir / relative
        if candidate.exists():
            return candidate

    file_name = str(row.get("file_name") or "").strip()
    if not file_name:
        return None
    found = list(comp_dir.rglob(file_name))
    if found:
        return found[0]
    return None


def load_company_expectations(
    comp_name: str, expectation_path: Path
) -> list[dict[str, Any]]:
    comp_dir = expectation_path.parent
    text = expectation_path.read_text(encoding="utf-8-sig")
    docs: list[dict[str, Any]] = []

    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue

        file_name = str(row.get("file_name") or "").strip()
        if not file_name.lower().endswith(".pdf"):
            continue
        if str(row.get("labeling_status") or "").lower() == "excluded":
            continue

        file_path = resolve_doc_path(comp_dir, row)
        if file_path is None:
            continue

        normalized = {
            "company": comp_name,
            "file_name": file_name,
            "file_path": str(file_path),
            "split": str(row.get("split") or ""),
            "fields": {
                "net_amount": row.get("net_amount", ""),
                "total_amount": row.get("total_amount", ""),
                "vat_amount": row.get("vat_amount", ""),
                "wht_amount": row.get("wht_amount", ""),
                "buyer_tax_id": row.get("buyer_tax_id", ""),
                "seller_tax_id": row.get("seller_tax_id", ""),
                "invoice_number": row.get("invoice_number", ""),
                "invoice_date": row.get("invoice_date", ""),
            },
        }
        docs.append(normalized)

    return docs


def build_answer_key_payload(
    company_docs: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    per_company: dict[str, Any] = {}
    combined_docs: list[dict[str, Any]] = []

    for comp_name, docs in company_docs.items():
        per_company[comp_name] = {
            "count": len(docs),
            "documents": docs,
        }
        combined_docs.extend(docs)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fields": [field.key for field in FIELDS],
        "companies": per_company,
        "combined": {
            "count": len(combined_docs),
            "documents": combined_docs,
        },
    }


def encode_multipart(
    fields: dict[str, str], file_field: str, file_path: Path
) -> tuple[bytes, str]:
    boundary = f"----aiacc-eva-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(
                    "utf-8"
                ),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    file_bytes = file_path.read_bytes()
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: application/pdf\r\n\r\n",
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    body = b"".join(chunks)
    return body, boundary


def post_process_api(
    api_url: str,
    file_path: Path,
    company_id: str,
    company_tax_id: str,
    force_refresh: bool,
    timeout_sec: int,
) -> dict[str, Any]:
    form_fields = {
        "company_id": company_id,
        "company_tax_id": company_tax_id,
        "force_refresh": "true" if force_refresh else "false",
    }
    body, boundary = encode_multipart(form_fields, "file", file_path)

    request = urllib.request.Request(api_url, method="POST", data=body)
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {file_path.name}: {text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API unavailable at {api_url}: {exc.reason}") from exc


def get_predicted_value(field_key: str, api_response: dict[str, Any]) -> Any:
    fields = api_response.get("fields") or {}
    extraction = api_response.get("extraction") or {}
    reconciliation = extraction.get("reconciliation") or {}
    derived = reconciliation.get("derived") or {}

    if field_key == "total_amount":
        return fields.get("total_amount") or derived.get("gross")
    if field_key == "net_amount":
        return fields.get("net_amount") or derived.get("net")
    if field_key == "vat_amount":
        return fields.get("vat_amount") or derived.get("vat")
    return fields.get(field_key)


def compare_field(field: FieldSpec, expected: Any, predicted: Any) -> bool:
    if field.kind == "amount":
        return eq_amount(expected, predicted)
    if field.kind == "tax":
        return eq_tax_id(expected, predicted)
    if field.kind == "invoice":
        return eq_invoice_number(expected, predicted)
    if field.kind == "date":
        return eq_date(expected, predicted)
    return str(expected or "").strip() == str(predicted or "").strip()


def build_doc_result(
    doc: dict[str, Any], api_response: dict[str, Any]
) -> dict[str, Any]:
    expected_fields = doc["fields"]
    extraction = api_response.get("extraction") or {}
    reconciliation = extraction.get("reconciliation") or {}
    layout = extraction.get("vat_layout") or reconciliation.get("layout") or "unknown"
    reconciled = reconciliation.get("reconciled")
    if reconciled is None:
        reconciled = True

    confidence_raw = api_response.get("overall_confidence")
    confidence_num = parse_num(confidence_raw)
    if confidence_num is None:
        confidence_pct = None
    elif confidence_num <= 1:
        confidence_pct = confidence_num * 100
    else:
        confidence_pct = confidence_num

    comparisons: dict[str, dict[str, Any]] = {}
    for field in FIELDS:
        expected_value = expected_fields.get(field.key)
        predicted_value = get_predicted_value(field.key, api_response)
        matched = compare_field(field, expected_value, predicted_value)
        comparisons[field.key] = {
            "expected": expected_value,
            "predicted": predicted_value,
            "matched": matched,
        }

    return {
        "company": doc["company"],
        "file_name": doc["file_name"],
        "file_path": doc["file_path"],
        "split": doc.get("split", ""),
        "layout": layout,
        "reconciled": bool(reconciled),
        "confidence_pct": round(confidence_pct, 2)
        if confidence_pct is not None
        else None,
        "comparisons": comparisons,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_values = [
        float(row["confidence_pct"])
        for row in results
        if isinstance(row.get("confidence_pct"), (int, float))
    ]
    overall_confidence = (
        round(sum(confidence_values) / len(confidence_values), 2)
        if confidence_values
        else 0.0
    )
    reconciled_count = sum(1 for row in results if row.get("reconciled", False))
    reconciled_pct = (
        round((reconciled_count * 100.0) / len(results), 2) if results else 0.0
    )

    summary_fields: dict[str, dict[str, Any]] = {}
    for field in FIELDS:
        total = len(results)
        matched = sum(1 for row in results if row["comparisons"][field.key]["matched"])
        accuracy_pct = (matched * 100.0 / total) if total else 0.0
        summary_fields[field.key] = {
            "label": field.label,
            "matched": matched,
            "total": total,
            "accuracy_pct": round(accuracy_pct, 2),
        }
    return {
        "sample_size": len(results),
        "overall_confidence_pct": overall_confidence,
        "reconciled_count": reconciled_count,
        "reconciled_pct": reconciled_pct,
        "reconciled_all": bool(results) and reconciled_count == len(results),
        "fields": summary_fields,
    }


def render_summary_table(summary: dict[str, Any]) -> str:
    rows: list[str] = []
    for field in FIELDS:
        data = summary["fields"][field.key]
        rows.append(
            "<tr>"
            f"<td>{html_escape(data['label'])}</td>"
            f"<td>{data['matched']}</td>"
            f"<td>{data['total']}</td>"
            f"<td>{format_percent(float(data['accuracy_pct']))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def confidence_band(score: float, reconciled: bool = True) -> str:
    if score >= CONFIDENCE_HIGH_THRESHOLD and reconciled:
        return "conf-high"
    if score >= CONFIDENCE_MED_THRESHOLD:
        return "conf-med"
    return "conf-low"


def render_kpi_metric(
    label: str,
    score: float,
    reconciled: bool = True,
    hero: bool = False,
) -> str:
    band = confidence_band(score, reconciled=reconciled)
    hero_class = " metric-hero" if hero else ""
    value_text = format_percent(score)
    return (
        f"<article class='metric-card {band}{hero_class}'>"
        f"<div class='metric-label'>{html_escape(label)}</div>"
        f"<div class='metric-value'>{html_escape(value_text)}</div>"
        f"<div class='metric-band'>{html_escape(band.replace('conf-', '').upper())}</div>"
        "</article>"
    )


def render_kpi_tier(
    title: str,
    subtitle: str,
    tone_class: str,
    metrics_html: str,
    grid_class: str = "",
) -> str:
    grid_attr = f" tier-grid {grid_class}".rstrip()
    return (
        f"<section class='kpi-tier {tone_class}'>"
        "<div class='tier-head'>"
        f"<div class='tier-kicker'>{html_escape(title)}</div>"
        f"<div class='tier-note'>{html_escape(subtitle)}</div>"
        "</div>"
        f"<div class='{grid_attr}'>{metrics_html}</div>"
        "</section>"
    )


def render_kpi_cards(summary: dict[str, Any]) -> str:
    field_map = {field.key: summary["fields"][field.key] for field in FIELDS}

    high_priority = render_kpi_tier(
        title="Level 1 · Highest priority",
        subtitle=(
            "Executive signal for the entire evaluation run "
            f"(Reconciled {summary.get('reconciled_count', 0)}/{summary.get('sample_size', 0)})."
        ),
        tone_class="tier-high",
        grid_class="tier-grid-single",
        metrics_html=render_kpi_metric(
            label="Over all confidence",
            score=float(summary.get("overall_confidence_pct", 0.0)),
            reconciled=bool(summary.get("reconciled_all", False)),
            hero=True,
        ),
    )

    medium_metrics: list[str] = []
    for key in ("net_amount", "total_amount", "vat_amount", "wht_amount"):
        data = field_map[key]
        medium_metrics.append(
            render_kpi_metric(
                label=data["label"],
                score=float(data["accuracy_pct"]),
            )
        )

    medium_priority = render_kpi_tier(
        title="Level 2 · Financial correctness",
        subtitle="Core accounting amounts that drive tax and payable impact.",
        tone_class="tier-medium",
        metrics_html="".join(medium_metrics),
    )

    low_metrics: list[str] = []
    for key in ("buyer_tax_id", "seller_tax_id", "invoice_number", "invoice_date"):
        data = field_map[key]
        low_metrics.append(
            render_kpi_metric(
                label=data["label"],
                score=float(data["accuracy_pct"]),
            )
        )

    low_priority = render_kpi_tier(
        title="Level 3 · Reference identity",
        subtitle="Document identity fields for traceability and matching support.",
        tone_class="tier-low",
        metrics_html="".join(low_metrics),
    )

    return "\n".join([high_priority, medium_priority, low_priority])


def render_detail_table(results: list[dict[str, Any]]) -> str:
    header_cells = ["<th>File</th>"]
    for field in FIELDS:
        short = field.label.replace(" (THB)", "")
        header_cells.append(f"<th>{html_escape(short)} Pred</th>")
        header_cells.append(f"<th>{html_escape(short)} Exp</th>")
        header_cells.append(f"<th>{html_escape(short)} Match</th>")
    header_cells.extend(["<th>Conf %</th>", "<th>Layout</th>", "<th>Reconciled</th>"])

    body_rows: list[str] = []
    for row in sorted(results, key=lambda item: item["file_name"]):
        cells = [f"<td>{html_escape(row['file_name'])}</td>"]
        for field in FIELDS:
            cmp_data = row["comparisons"][field.key]
            pred = cmp_data["predicted"]
            exp = cmp_data["expected"]
            if field.kind == "amount":
                pred_text = format_amount(pred)
                exp_text = format_amount(exp)
            else:
                pred_text = str(pred or "")
                exp_text = str(exp or "")

            status = "OK" if cmp_data["matched"] else "NO"
            status_class = "ok" if cmp_data["matched"] else "no"
            cells.append(f"<td>{html_escape(pred_text)}</td>")
            cells.append(f"<td>{html_escape(exp_text)}</td>")
            cells.append(f"<td class='{status_class}'>{status}</td>")

        confidence = (
            "" if row["confidence_pct"] is None else f"{row['confidence_pct']:.2f}"
        )
        cells.append(f"<td>{html_escape(confidence)}</td>")
        cells.append(f"<td>{html_escape(row['layout'])}</td>")
        cells.append(f"<td>{'True' if row['reconciled'] else 'False'}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        "<table>"
        "<thead><tr>"
        + "".join(header_cells)
        + "</tr></thead><tbody>"
        + "\n".join(body_rows)
        + "</tbody></table>"
    )


def render_report_html(
    title: str,
    generated_at: str,
    combined_summary: dict[str, Any],
    combined_results: list[dict[str, Any]],
    per_company_payload: dict[str, dict[str, Any]],
) -> str:
    sections: list[str] = []
    sections.append("<h2>Combined Summary</h2>")
    sections.append("<div class='kpi'>" + render_kpi_cards(combined_summary) + "</div>")
    sections.append(
        "<div class='card'><details class='table-dd'><summary>Summary Table</summary>"
        "<table><thead><tr>"
        "<th>Metric</th><th>Matched</th><th>Total</th><th>Accuracy</th>"
        "</tr></thead><tbody>"
        + render_summary_table(combined_summary)
        + "</tbody></table></details></div>"
    )
    sections.append(
        "<div class='card'><details class='table-dd'><summary>Per-file Detail (Predicted vs Expected)</summary>"
        + render_detail_table(combined_results)
        + "</details></div>"
    )

    for comp_name in sorted(per_company_payload.keys()):
        payload = per_company_payload[comp_name]
        summary = payload["summary"]
        results = payload["results"]
        sections.append(f"<h2>Company: {html_escape(comp_name)}</h2>")
        sections.append("<div class='kpi'>" + render_kpi_cards(summary) + "</div>")
        sections.append(
            "<div class='card'><details class='table-dd'><summary>Summary Table</summary><table><thead><tr>"
            "<th>Metric</th><th>Matched</th><th>Total</th><th>Accuracy</th>"
            "</tr></thead><tbody>"
            + render_summary_table(summary)
            + "</tbody></table></details></div>"
        )
        sections.append(
            "<div class='card'><details class='table-dd'><summary>Per-file Detail (Predicted vs Expected)</summary>"
            + render_detail_table(results)
            + "</details></div>"
        )

    return (
        "<!doctype html>"
        "<html lang='en'><head><meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width,initial-scale=1' />"
        f"<title>{html_escape(title)}</title>"
        "<style>"
        ":root { --bg:#f3f5fa; --card:#ffffff; --ink:#172033; --muted:#5f6b85; --line:#dbe2f0; --brand:#173fcf; --brand-soft:#ebf1ff; --amber:#b54708; --amber-soft:#fff7e8; --green:#067647; --green-soft:#ecfdf3; --danger:#b42318; --danger-soft:#fef0f0; --slate:#344054; }"
        "* { box-sizing:border-box; }"
        "body { font-family: 'Segoe UI', Tahoma, sans-serif; margin:0; padding:24px; color:var(--ink); background:radial-gradient(circle at top left, rgba(23,63,207,0.12), transparent 35%), linear-gradient(180deg, #f8faff 0%, var(--bg) 100%); }"
        "h1 { margin:0 0 8px 0; font-size:1.9rem; letter-spacing:-0.02em; }"
        "h2 { margin:28px 0 10px 0; color:var(--slate); font-size:1.15rem; }"
        ".small { color:var(--muted); margin-bottom:16px; }"
        ".card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px; margin-bottom:16px; box-shadow:0 6px 18px rgba(20,32,61,0.05); }"
        "table { border-collapse: collapse; width: 100%; background:white; }"
        "th, td { border:1px solid var(--line); padding:8px; font-size:12px; }"
        "th { background:#f4f7ff; text-align:left; position: sticky; top: 0; color:var(--slate); }"
        ".ok { color:#065f46; font-weight:600; }"
        ".no { color:#991b1b; font-weight:600; }"
        ".kpi { display:grid; gap:14px; margin-bottom:16px; }"
        ".kpi-tier { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:14px; box-shadow:0 6px 18px rgba(20,32,61,0.05); position:relative; overflow:hidden; }"
        ".kpi-tier::before { content:''; position:absolute; inset:0 auto 0 0; width:6px; border-radius:18px 0 0 18px; }"
        ".tier-high { background:linear-gradient(135deg, rgba(235,241,255,0.95), rgba(255,255,255,0.98)); }"
        ".tier-high::before { background:linear-gradient(180deg, #173fcf 0%, #4c77ff 100%); }"
        ".tier-medium { background:linear-gradient(135deg, rgba(255,247,232,0.95), rgba(255,255,255,0.98)); }"
        ".tier-medium::before { background:linear-gradient(180deg, #b54708 0%, #f79009 100%); }"
        ".tier-low { background:linear-gradient(135deg, rgba(244,247,252,0.98), rgba(255,255,255,0.98)); }"
        ".tier-low::before { background:linear-gradient(180deg, #667085 0%, #98a2b3 100%); }"
        ".tier-head { display:flex; justify-content:space-between; gap:12px; align-items:end; margin-bottom:12px; flex-wrap:wrap; }"
        ".tier-kicker { font-size:0.86rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; }"
        ".tier-high .tier-kicker { color:var(--brand); }"
        ".tier-medium .tier-kicker { color:var(--amber); }"
        ".tier-low .tier-kicker { color:#475467; }"
        ".tier-note { color:var(--muted); font-size:0.82rem; }"
        ".tier-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:12px; }"
        ".tier-grid-single { grid-template-columns:minmax(280px, 1fr); }"
        ".metric-card { border-radius:14px; padding:14px 16px; border:1px solid transparent; position:relative; overflow:hidden; min-height:96px; }"
        ".metric-card::after { content:''; position:absolute; inset:auto -24px -24px auto; width:88px; height:88px; border-radius:50%; opacity:0.22; }"
        ".metric-label { font-size:0.9rem; color:var(--ink); margin-bottom:8px; }"
        ".metric-value { font-size:2rem; line-height:1; font-weight:800; letter-spacing:-0.03em; }"
        ".metric-band { margin-top:10px; font-size:0.72rem; font-weight:700; letter-spacing:0.04em; }"
        ".metric-card.conf-high { background:var(--green-soft); border-color:color-mix(in oklab, var(--green) 35%, white 65%); }"
        ".metric-card.conf-high .metric-value, .metric-card.conf-high .metric-band { color:var(--green); }"
        ".metric-card.conf-high::after { background:color-mix(in oklab, var(--green) 30%, white 70%); }"
        ".metric-card.conf-med { background:var(--amber-soft); border-color:color-mix(in oklab, var(--amber) 35%, white 65%); }"
        ".metric-card.conf-med .metric-value, .metric-card.conf-med .metric-band { color:var(--amber); }"
        ".metric-card.conf-med::after { background:color-mix(in oklab, var(--amber) 28%, white 72%); }"
        ".metric-card.conf-low { background:var(--danger-soft); border-color:color-mix(in oklab, var(--danger) 35%, white 65%); }"
        ".metric-card.conf-low .metric-value, .metric-card.conf-low .metric-band { color:var(--danger); }"
        ".metric-card.conf-low::after { background:color-mix(in oklab, var(--danger) 26%, white 74%); }"
        ".metric-card.metric-hero { box-shadow:0 14px 32px rgba(23,63,207,0.14); }"
        ".metric-card.metric-hero.conf-high { background:linear-gradient(135deg, color-mix(in oklab, var(--green-soft) 78%, white 22%), #ffffff 98%); }"
        ".metric-card.metric-hero.conf-med { background:linear-gradient(135deg, color-mix(in oklab, var(--amber-soft) 78%, white 22%), #ffffff 98%); }"
        ".metric-card.metric-hero.conf-low { background:linear-gradient(135deg, color-mix(in oklab, var(--danger-soft) 80%, white 20%), #ffffff 98%); }"
        ".table-dd { width:100%; }"
        ".table-dd summary { cursor:pointer; font-weight:700; margin-bottom:10px; color:var(--brand); }"
        ".table-dd[open] summary { margin-bottom:12px; }"
        "@media (max-width: 720px) { body { padding:16px; } .metric-value { font-size:1.7rem; } .tier-head { align-items:start; } }"
        "</style></head><body>"
        f"<h1>{html_escape(title)}</h1>"
        f"<div class='small'>Generated: {html_escape(generated_at)} | Source: expectations + live compare</div>"
        + "\n".join(sections)
        + "</body></html>"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def select_company(
    expectation_files: dict[str, Path], selector: str
) -> tuple[str, Path]:
    if selector in expectation_files:
        return selector, expectation_files[selector]

    normalized = selector.strip()
    if "/" in normalized:
        left, right = normalized.split("/", 1)
        left = left.strip()
        right = right.strip()
        if right in expectation_files:
            return right, expectation_files[right]
        candidate = f"Comp_{left}"
        if candidate in expectation_files:
            return candidate, expectation_files[candidate]

    if normalized.isdigit():
        candidate = f"Comp_{normalized}"
        if candidate in expectation_files:
            return candidate, expectation_files[candidate]

    raise ValueError(f"Unknown company selector: {selector}")


def pick_company_tax_id(docs: list[dict[str, Any]], fallback: str) -> str:
    values = [normalize_tax_id(doc["fields"].get("buyer_tax_id")) for doc in docs]
    values = [v for v in values if v]
    if values:
        return max(set(values), key=values.count)
    return fallback


def evaluate_company(
    comp_name: str,
    docs: list[dict[str, Any]],
    api_url: str,
    company_id_override: str,
    company_tax_id_override: str,
    force_refresh: bool,
    timeout_sec: int,
) -> list[dict[str, Any]]:
    company_id = company_id_override or DEFAULT_COMPANY_ID_BY_FOLDER.get(comp_name, "")
    company_tax_id = company_tax_id_override or pick_company_tax_id(docs, "")

    results: list[dict[str, Any]] = []
    for idx, doc in enumerate(docs, start=1):
        file_path = Path(doc["file_path"])
        print(f"PROGRESS|{comp_name}|{idx}/{len(docs)}|{file_path.name}")
        response = post_process_api(
            api_url=api_url,
            file_path=file_path,
            company_id=company_id,
            company_tax_id=company_tax_id,
            force_refresh=force_refresh,
            timeout_sec=timeout_sec,
        )
        results.append(build_doc_result(doc, response))
    return results


def run_jsonanswer_mode(
    output_dir: Path, company_docs: dict[str, list[dict[str, Any]]]
) -> int:
    payload = build_answer_key_payload(company_docs)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = output_dir / f"aiacc_eva_answer_key_{ts}.json"
    write_json(out_json, payload)
    print(f"OUT_JSON|{out_json}")
    print(
        f"SUMMARY|companies={len(company_docs)}|documents={payload['combined']['count']}"
    )
    return 0


def run_report_mode(
    output_dir: Path,
    company_docs: dict[str, list[dict[str, Any]]],
    api_url: str,
    company_id_override: str,
    company_tax_id_override: str,
    force_refresh: bool,
    timeout_sec: int,
    title: str,
) -> int:
    per_company_payload: dict[str, dict[str, Any]] = {}
    combined_results: list[dict[str, Any]] = []

    for comp_name in sorted(company_docs.keys()):
        docs = company_docs[comp_name]
        results = evaluate_company(
            comp_name=comp_name,
            docs=docs,
            api_url=api_url,
            company_id_override=company_id_override,
            company_tax_id_override=company_tax_id_override,
            force_refresh=force_refresh,
            timeout_sec=timeout_sec,
        )
        summary = summarize_results(results)
        per_company_payload[comp_name] = {"summary": summary, "results": results}
        combined_results.extend(results)

    combined_summary = summarize_results(combined_results)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = render_report_html(
        title=title,
        generated_at=generated_at,
        combined_summary=combined_summary,
        combined_results=combined_results,
        per_company_payload=per_company_payload,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_html = output_dir / f"aiacc_eva_report_{ts}.html"
    out_json = output_dir / f"aiacc_eva_report_{ts}.json"

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8")

    write_json(
        out_json,
        {
            "generated_at": generated_at,
            "title": title,
            "combined_summary": combined_summary,
            "per_company": per_company_payload,
        },
    )

    print(f"OUT_HTML|{out_html}")
    print(f"OUT_JSON|{out_json}")
    print(f"SUMMARY|documents={len(combined_results)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Accounting evaluation report generator"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-jsonanswer",
        "--jsonanswer",
        action="store_true",
        help="Generate normalized answer-key JSON from expectations files",
    )
    mode.add_argument(
        "-full-report",
        "--full-report",
        action="store_true",
        help="Generate full report for all companies with expectations",
    )
    mode.add_argument(
        "-comp-report",
        "--comp-report",
        type=str,
        default="",
        help="Generate report for a single company: Comp_1 or 1/Comp_1",
    )

    parser.add_argument("--poc-root", type=Path, default=DEFAULT_POC_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL)
    parser.add_argument("--company-id", type=str, default="")
    parser.add_argument("--company-tax-id", type=str, default="")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    expectation_files = discover_expectation_files(args.poc_root)
    if not expectation_files:
        print(f"ERROR|No expectations.filled.jsonl found under {args.poc_root}")
        return 1

    if args.comp_report:
        try:
            comp_name, expectation_path = select_company(
                expectation_files, args.comp_report
            )
        except ValueError as exc:
            print(f"ERROR|{exc}")
            return 1
        company_docs = {
            comp_name: load_company_expectations(comp_name, expectation_path)
        }
    else:
        company_docs = {
            comp_name: load_company_expectations(comp_name, path)
            for comp_name, path in expectation_files.items()
        }

    # Drop empty expectation sets to keep output clean.
    company_docs = {name: docs for name, docs in company_docs.items() if docs}
    if not company_docs:
        print("ERROR|No usable PDF rows found in expectations files")
        return 1

    if args.jsonanswer:
        return run_jsonanswer_mode(args.output_dir, company_docs)

    report_title = "AIACC Evaluation Report"
    if args.full_report:
        report_title = "AIACC Evaluation Report (Full)"
    elif args.comp_report:
        report_title = f"AIACC Evaluation Report ({next(iter(company_docs.keys()))})"

    try:
        return run_report_mode(
            output_dir=args.output_dir,
            company_docs=company_docs,
            api_url=args.api_url,
            company_id_override=args.company_id,
            company_tax_id_override=args.company_tax_id,
            force_refresh=args.force_refresh,
            timeout_sec=args.timeout,
            title=report_title,
        )
    except RuntimeError as exc:
        print(f"ERROR|{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
