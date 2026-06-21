"""TASK-906 line-item PoC corpus, scoring, and report harness."""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from scripts.line_item_prompts import (  # noqa: E402
    DEFAULT_MODEL_SET,
    build_system_prompt,
    build_user_prompt,
    parse_line_item_response,
)
from src.backend.ml.image_loader import load_images_for_vision  # noqa: E402
from src.backend.ml.ocr import run_ocr  # noqa: E402
from src.backend.ml.providers import AnthropicProvider, OpenRouterProvider  # noqa: E402
from src.backend.services.secrets_loader import load_llm_keys  # noqa: E402

COMP1_ROOT = ROOT / "private_data" / "poc" / "Comp_1"
ARTIFACT_ROOT = ROOT / "private_data" / "poc" / "line_item_poc"
DEFAULT_MANIFEST_PATH = ARTIFACT_ROOT / "corpus_manifest.json"
DEFAULT_GROUND_TRUTH_PATH = ARTIFACT_ROOT / "line_item_ground_truth.json"
DEFAULT_RESULTS_DIR = ARTIFACT_ROOT / "results"
DEFAULT_REPORT_PATH = ROOT / "docs" / "PoC" / "reports" / "TASK-906-FEASIBILITY-REPORT.md"

FIELD_NAMES = ["product_name", "qty", "unit", "unit_price", "line_amount"]
UNIT_MAP = {
    "pcs": "piece",
    "pc": "piece",
    "piece": "piece",
    "pieces": "piece",
    "ea": "piece",
    "unit": "piece",
    "ชิ้น": "piece",
    "อัน": "piece",
    "set": "set",
    "ชุด": "set",
    "kg": "kg",
    "kgs": "kg",
    "กก": "kg",
    "เมตร": "meter",
    "m": "meter",
    "เมตร.": "meter",
    "ลัง": "carton",
    "กล่อง": "box",
    "box": "box",
}
METRIC_THRESHOLDS = {
    "per_field_accuracy": 0.80,
    "document_success_rate": 0.60,
    "line_total_reconciliation_rate": 0.70,
    "cost_per_document_thb": 1.50,
    "processing_time_per_document_sec": 15.0,
    "manual_correction_time_min": 3.0,
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    content = path.read_text(encoding="utf-8-sig")
    for line in content.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_unit(value: Any) -> str:
    key = _normalize_text(value).replace(".", "")
    return UNIT_MAP.get(key, key)


def normalize_line_item_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": _normalize_text(row.get("product_name", "")),
        "qty": _safe_float(row.get("qty"), None),
        "unit": normalize_unit(row.get("unit", "")),
        "unit_price": _safe_float(row.get("unit_price"), None),
        "line_amount": _safe_float(row.get("line_amount"), None),
    }


def text_similarity(left: Any, right: Any) -> float:
    a = _normalize_text(left)
    b = _normalize_text(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def numeric_match(left: float | None, right: float | None, tolerance: float) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def row_match_score(expected: dict[str, Any], predicted: dict[str, Any]) -> float:
    score = text_similarity(expected.get("product_name"), predicted.get("product_name")) * 2.0
    score += 1.0 if numeric_match(expected.get("qty"), predicted.get("qty"), 0.001) else 0.0
    score += 1.0 if _field_match("unit", expected.get("unit"), predicted.get("unit")) else 0.0
    score += 1.0 if numeric_match(expected.get("unit_price"), predicted.get("unit_price"), 0.01) else 0.0
    score += 1.0 if numeric_match(expected.get("line_amount"), predicted.get("line_amount"), 0.01) else 0.0
    return score


def _field_match(field_name: str, expected: Any, predicted: Any) -> bool:
    if field_name == "product_name":
        return text_similarity(expected, predicted) >= 0.92
    if field_name == "qty":
        return numeric_match(expected, predicted, 0.001)
    if field_name == "unit":
        return normalize_unit(expected) == normalize_unit(predicted)
    if field_name in {"unit_price", "line_amount"}:
        return numeric_match(expected, predicted, 0.01)
    return _normalize_text(expected) == _normalize_text(predicted)


def match_rows(
    expected_rows: list[dict[str, Any]], predicted_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    unmatched = set(range(len(predicted_rows)))
    matches: list[dict[str, Any]] = []
    ordering = sorted(
        range(len(expected_rows)),
        key=lambda idx: len(expected_rows[idx].get("product_name") or ""),
        reverse=True,
    )
    for expected_idx in ordering:
        best_idx = -1
        best_score = -1.0
        for predicted_idx in sorted(unmatched):
            score = row_match_score(expected_rows[expected_idx], predicted_rows[predicted_idx])
            if score > best_score:
                best_score = score
                best_idx = predicted_idx
        if best_idx >= 0:
            unmatched.remove(best_idx)
            matches.append(
                {
                    "expected_index": expected_idx,
                    "predicted_index": best_idx,
                    "score": round(best_score, 4),
                }
            )
    return sorted(matches, key=lambda item: item["expected_index"])


def score_document(
    truth_rows: list[dict[str, Any]],
    predicted_rows: list[dict[str, Any]],
    expected_total: float | None,
) -> dict[str, Any]:
    normalized_truth = [normalize_line_item_row(row) for row in truth_rows]
    normalized_pred = [normalize_line_item_row(row) for row in predicted_rows]
    matches = match_rows(normalized_truth, normalized_pred)
    row_count_match = len(normalized_truth) == len(normalized_pred)

    field_hits = {field: 0 for field in FIELD_NAMES}
    field_totals = {field: len(normalized_truth) for field in FIELD_NAMES}
    matched_row_results: list[dict[str, Any]] = []
    error_count = 0

    for match in matches:
        expected = normalized_truth[match["expected_index"]]
        predicted = normalized_pred[match["predicted_index"]]
        row_fields: dict[str, bool] = {}
        for field in FIELD_NAMES:
            ok = _field_match(field, expected.get(field), predicted.get(field))
            row_fields[field] = ok
            field_hits[field] += int(ok)
            error_count += int(not ok)
        matched_row_results.append(
            {
                "expected_index": match["expected_index"],
                "predicted_index": match["predicted_index"],
                "score": match["score"],
                "field_matches": row_fields,
            }
        )

    missing_rows = max(0, len(normalized_truth) - len(matches))
    extra_rows = max(0, len(normalized_pred) - len(matches))
    error_count += (missing_rows + extra_rows) * len(FIELD_NAMES)

    per_field_accuracy = {
        field: round(field_hits[field] / field_totals[field], 4) if field_totals[field] else 0.0
        for field in FIELD_NAMES
    }
    predicted_total = round(
        sum(row.get("line_amount") or 0.0 for row in normalized_pred),
        2,
    )
    reconciliation_pass = False
    if expected_total is not None and normalized_pred:
        reconciliation_pass = abs(predicted_total - expected_total) <= 1.0

    all_fields_ok = all(
        all(row["field_matches"].values()) for row in matched_row_results
    )
    document_success = (
        row_count_match
        and missing_rows == 0
        and extra_rows == 0
        and all_fields_ok
        and len(matches) == len(normalized_truth)
    )

    return {
        "row_count_truth": len(normalized_truth),
        "row_count_predicted": len(normalized_pred),
        "row_count_match": row_count_match,
        "missing_rows": missing_rows,
        "extra_rows": extra_rows,
        "per_field_accuracy": per_field_accuracy,
        "document_success": document_success,
        "reconciliation_pass": reconciliation_pass,
        "expected_total": expected_total,
        "predicted_total": predicted_total,
        "error_count": error_count,
        "matched_rows": matched_row_results,
        "normalized_prediction": normalized_pred,
        "normalized_truth": normalized_truth,
    }


def score_go_no_go(model_summary: dict[str, Any]) -> dict[str, Any]:
    metric_results = {
        "per_field_accuracy": all(
            (model_summary.get("per_field_accuracy", {}) or {}).get(field, 0.0)
            >= METRIC_THRESHOLDS["per_field_accuracy"]
            for field in FIELD_NAMES
        ),
        "document_success_rate": model_summary.get("document_success_rate", 0.0)
        >= METRIC_THRESHOLDS["document_success_rate"],
        "line_total_reconciliation_rate": model_summary.get(
            "line_total_reconciliation_rate", 0.0
        )
        >= METRIC_THRESHOLDS["line_total_reconciliation_rate"],
        "cost_per_document_thb": model_summary.get("cost_per_document_thb", math.inf)
        <= METRIC_THRESHOLDS["cost_per_document_thb"],
        "processing_time_per_document_sec": model_summary.get(
            "processing_time_per_document_sec", math.inf
        )
        <= METRIC_THRESHOLDS["processing_time_per_document_sec"],
        "manual_correction_time_min": model_summary.get(
            "manual_correction_time_min", math.inf
        )
        <= METRIC_THRESHOLDS["manual_correction_time_min"],
    }
    pass_count = sum(int(value) for value in metric_results.values())
    if pass_count >= 4:
        decision = "Go"
    elif pass_count == 3:
        decision = "Conditional"
    else:
        decision = "No-Go"
    return {"metric_passes": metric_results, "pass_count": pass_count, "decision": decision}


def aggregate_model_reports(
    model: str,
    documents: list[dict[str, Any]],
    timed_review_docs: set[str],
) -> dict[str, Any]:
    if not documents:
        return {
            "model": model,
            "documents_tested": 0,
            "per_field_accuracy": {field: 0.0 for field in FIELD_NAMES},
            "document_success_rate": 0.0,
            "line_total_reconciliation_rate": 0.0,
            "cost_per_document_thb": 0.0,
            "processing_time_per_document_sec": 0.0,
            "manual_correction_time_min": math.inf,
            "timed_review_sample_size": 0,
        }

    per_field_totals = {field: 0.0 for field in FIELD_NAMES}
    document_success_rate = 0.0
    reconciliation_rate = 0.0
    total_cost = 0.0
    total_time = 0.0
    manual_times: list[float] = []

    for doc in documents:
        scoring = doc["scoring"]
        for field in FIELD_NAMES:
            per_field_totals[field] += scoring["per_field_accuracy"][field]
        document_success_rate += float(scoring["document_success"])
        reconciliation_rate += float(scoring["reconciliation_pass"])
        total_cost += float(doc.get("cost_thb", 0.0) or 0.0)
        total_time += float(doc.get("elapsed_sec", 0.0) or 0.0)
        if doc["doc_id"] in timed_review_docs:
            review_seconds = _safe_float(doc.get("manual_review_seconds"), None)
            if review_seconds is not None:
                manual_times.append(review_seconds / 60.0)

    doc_count = len(documents)
    summary = {
        "model": model,
        "documents_tested": doc_count,
        "per_field_accuracy": {
            field: round(per_field_totals[field] / doc_count, 4) for field in FIELD_NAMES
        },
        "document_success_rate": round(document_success_rate / doc_count, 4),
        "line_total_reconciliation_rate": round(reconciliation_rate / doc_count, 4),
        "cost_per_document_thb": round(total_cost / doc_count, 4),
        "processing_time_per_document_sec": round(total_time / doc_count, 4),
        "manual_correction_time_min": round(sum(manual_times) / len(manual_times), 4)
        if manual_times
        else math.inf,
        "timed_review_sample_size": len(manual_times),
        "cost_projection_thb": {
            "10000_docs_month": round((total_cost / doc_count) * 10000, 2),
            "20000_docs_month": round((total_cost / doc_count) * 20000, 2),
        },
    }
    summary.update(score_go_no_go(summary))
    return summary


def summarize_diversity(selected_docs: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for doc in selected_docs:
        for tag in doc.get("diversity_tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    return {
        "category_count": len(counts),
        "counts": dict(sorted(counts.items())),
    }


def _extract_pdf_text_layer(file_path: Path) -> str:
    try:
        pypdf_module = __import__("pypdf")
    except ImportError:
        return ""
    try:
        reader = pypdf_module.PdfReader(str(file_path))
    except Exception:
        return ""
    chunks: list[str] = []
    for page in reader.pages[:2]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _ocr_text(file_path: Path) -> tuple[str, float]:
    ocr = run_ocr(str(file_path))
    text = "\n".join(str(block.get("text", "")) for block in ocr.get("blocks", []))
    return text, float(ocr.get("avg_confidence", 0.0) or 0.0)


def _detect_gridline(file_path: Path) -> bool:
    try:
        import cv2  # type: ignore
        import numpy  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return False
    try:
        first_page, _mime = load_images_for_vision(str(file_path), max_pages=1)[0]
        image = Image.open(io.BytesIO(first_page)).convert("L")
        pixels = numpy.array(image)
        threshold = cv2.threshold(
            pixels, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]
        horizontal = cv2.morphologyEx(
            threshold,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT, (max(20, pixels.shape[1] // 15), 1)
            ),
        )
        vertical = cv2.morphologyEx(
            threshold,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT, (1, max(20, pixels.shape[0] // 15))
            ),
        )
        density = (
            float(cv2.countNonZero(horizontal)) + float(cv2.countNonZero(vertical))
        ) / float(pixels.size or 1)
        return density >= 0.015
    except Exception:
        return False


def infer_diversity_tags(doc: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    file_path = Path(doc["file_path"])
    tags: list[str] = []
    sources: dict[str, str] = {}
    text_layer = _extract_pdf_text_layer(file_path)
    ocr_text, avg_conf = _ocr_text(file_path)
    joined_text = f"{text_layer}\n{ocr_text}".lower()

    if text_layer and len(text_layer) >= 200:
        tags.append("digital_pdf")
        sources["digital_pdf"] = "heuristic:text_layer"
    if not text_layer and avg_conf >= 0.88:
        tags.append("clear_scan")
        sources["clear_scan"] = "heuristic:ocr_confidence"
    if not text_layer and avg_conf < 0.65:
        tags.append("low_quality_scan")
        sources["low_quality_scan"] = "heuristic:ocr_confidence"
    if str(doc.get("is_multi_page", "")).lower() == "true" or str(doc.get("page_count", "")) == "2":
        tags.append("multi_page")
        sources["multi_page"] = "expectations:is_multi_page"
    if doc.get("wht_amount") or doc.get("wht_rate") or "หัก ณ ที่จ่าย" in joined_text:
        tags.append("discount_or_wht")
        sources["discount_or_wht"] = "expectations_or_ocr"
    if "ส่วนลด" in joined_text or "discount" in joined_text:
        if "discount_or_wht" not in tags:
            tags.append("discount_or_wht")
            sources["discount_or_wht"] = "ocr:discount_keyword"
    net_amount = _safe_float(doc.get("net_amount"), None)
    vat_amount = _safe_float(doc.get("vat_amount"), None)
    total_amount = _safe_float(doc.get("total_amount"), None)
    if net_amount is not None and vat_amount is not None and total_amount is not None:
        if abs((net_amount + vat_amount) - total_amount) <= 1.0:
            tags.append("vat_excluded")
            sources["vat_excluded"] = "expectations:amount_reconciliation"
    if "รวมภาษี" in joined_text or "vat included" in joined_text:
        tags.append("vat_included")
        sources["vat_included"] = "ocr:keyword"
    gridline = _detect_gridline(file_path)
    if gridline:
        tags.append("gridline_table")
        sources["gridline_table"] = "heuristic:cv_lines"
    elif len(ocr_text.splitlines()) >= 12:
        tags.append("text_only_layout")
        sources["text_only_layout"] = "heuristic:ocr_lines"

    return sorted(set(tags)), sources


def load_comp1_documents() -> list[dict[str, Any]]:
    manifest_rows = {
        row["doc_id"]: row for row in read_jsonl(COMP1_ROOT / "manifest.jsonl")
    }
    expectation_rows = {
        row["doc_id"]: row for row in read_jsonl(COMP1_ROOT / "expectations.filled.jsonl")
    }
    documents: list[dict[str, Any]] = []
    for doc_id, expected in expectation_rows.items():
        manifest = manifest_rows.get(doc_id)
        if not manifest:
            continue
        merged = dict(manifest)
        merged.update(expected)
        merged["file_path"] = str(COMP1_ROOT / expected["relative_path"])
        documents.append(merged)
    return documents


def select_corpus_documents(
    documents: list[dict[str, Any]], core_target: int = 20, reserve_target: int = 5
) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    for doc in documents:
        if not doc.get("include_in_training"):
            continue
        if doc.get("labeling_status") == "excluded":
            continue
        if doc.get("doc_type") != "Invoice":
            continue
        tags, tag_sources = infer_diversity_tags(doc)
        candidate = dict(doc)
        candidate["diversity_tags"] = tags
        candidate["tag_sources"] = tag_sources
        candidate["selection_status"] = "candidate"
        candidate["timed_review_eligible"] = False
        candidate["line_item_table_status"] = "assumed_candidate"
        eligible.append(candidate)

    remaining = list(eligible)
    selected_core: list[dict[str, Any]] = []
    covered: set[str] = set()

    while remaining and len(selected_core) < min(core_target, len(eligible)):
        remaining.sort(
            key=lambda doc: (
                -len(set(doc["diversity_tags"]) - covered),
                -len(doc["diversity_tags"]),
                -int(str(doc.get("is_multi_page", "")).lower() == "true"),
                -len(_normalize_text(doc.get("seller_name", ""))),
                doc["doc_id"],
            ),
        )
        picked = remaining.pop(0)
        picked["selection_status"] = "core"
        selected_core.append(picked)
        covered.update(picked["diversity_tags"])

    selected_doc_ids = {doc["doc_id"] for doc in selected_core}
    reserves = [doc for doc in eligible if doc["doc_id"] not in selected_doc_ids]
    reserves.sort(
        key=lambda doc: (
            -len(set(doc["diversity_tags"]) - covered),
            -len(doc["diversity_tags"]),
            doc["doc_id"],
        )
    )
    selected_reserve = reserves[:reserve_target]
    for doc in selected_reserve:
        doc["selection_status"] = "reserve"

    timed_review = choose_timed_review_docs(selected_core, target=5)
    timed_review_ids = {doc["doc_id"] for doc in timed_review}
    for doc in selected_core:
        doc["timed_review_eligible"] = doc["doc_id"] in timed_review_ids

    selected_all = selected_core + selected_reserve
    for doc in selected_all:
        doc["header_truth"] = {
            "invoice_number": doc.get("invoice_number", ""),
            "invoice_date": doc.get("invoice_date", ""),
            "seller_name": doc.get("seller_name", ""),
            "currency": doc.get("currency", "THB"),
            "total_amount": doc.get("total_amount", ""),
            "vat_amount": doc.get("vat_amount", ""),
            "wht_amount": doc.get("wht_amount", ""),
        }

    return {
        "schema_version": "task-906-corpus-v1",
        "generated_at": now_iso(),
        "source_root": str(COMP1_ROOT),
        "selection_policy": {
            "core_target": core_target,
            "reserve_target": reserve_target,
            "minimum_categories": 6,
            "notes": "Uses Comp_1 because it is the only current corpus with both manifest.jsonl and expectations.filled.jsonl.",
        },
        "summary": {
            "candidate_count": len(eligible),
            "core_count": len(selected_core),
            "reserve_count": len(selected_reserve),
            "timed_review_count": len(timed_review),
            "diversity_coverage": summarize_diversity(selected_core),
        },
        "documents": selected_all,
    }


def choose_timed_review_docs(
    core_docs: list[dict[str, Any]], target: int = 5
) -> list[dict[str, Any]]:
    timed: list[dict[str, Any]] = []
    covered: set[str] = set()
    remaining = list(core_docs)
    while remaining and len(timed) < min(target, len(core_docs)):
        remaining.sort(
            key=lambda doc: (
                -len(set(doc.get("diversity_tags", [])) - covered),
                -len(doc.get("diversity_tags", [])),
                doc["doc_id"],
            )
        )
        picked = remaining.pop(0)
        timed.append(picked)
        covered.update(picked.get("diversity_tags", []))
    return timed


def build_ground_truth_template(manifest_payload: dict[str, Any]) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    for doc in manifest_payload["documents"]:
        documents.append(
            {
                "doc_id": doc["doc_id"],
                "selection_status": doc["selection_status"],
                "timed_review_eligible": doc.get("timed_review_eligible", False),
                "label_status": "pending_bootstrap",
                "reviewer": "",
                "review_notes": "",
                "locked_at": "",
                "expected_line_total_amount": doc.get("net_amount", ""),
                "expected_gross_total_amount": doc.get("total_amount", ""),
                "expected_total_amount": doc.get("total_amount", ""),
                "currency": doc.get("currency", "THB") or "THB",
                "line_items": [],
                "bootstrap": {
                    "model": "",
                    "completed_at": "",
                    "raw_output_path": "",
                },
                "timed_review_measurements": {
                    model: {
                        "seconds": None,
                        "reviewer": "",
                        "reviewed_at": "",
                        "notes": "",
                    }
                    for model in DEFAULT_MODEL_SET
                },
            }
        )
    return {
        "schema_version": "task-906-ground-truth-v1",
        "generated_at": now_iso(),
        "documents": documents,
    }


def write_pending_report(report_path: Path, manifest_payload: dict[str, Any]) -> None:
    coverage = manifest_payload["summary"]["diversity_coverage"]["counts"]
    lines = [
        "# TASK-906 Feasibility Report",
        "",
        "> Status: Pending evaluation run",
        "",
        "## Corpus snapshot",
        "",
        f"- Generated at: `{manifest_payload['generated_at']}`",
        f"- Core docs: `{manifest_payload['summary']['core_count']}`",
        f"- Reserve docs: `{manifest_payload['summary']['reserve_count']}`",
        f"- Timed review docs: `{manifest_payload['summary']['timed_review_count']}`",
        f"- Diversity categories covered in current core set: `{manifest_payload['summary']['diversity_coverage']['category_count']}`",
        "",
        "## Diversity coverage",
        "",
    ]
    for key, value in coverage.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Pending steps",
            "",
            "1. Run `bootstrap-labels` to create draft line-item labels.",
            "2. Human-verify and lock every core document in `line_item_ground_truth.json`.",
            "3. Fill timed review measurements for the 5 marked sample docs.",
            "4. Run `evaluate` and re-render this report to get the final `Go / Conditional / No-Go` decision.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def expected_line_total_for_doc(doc: dict[str, Any]) -> float | None:
    """Line-item rows normally reconcile to net amount; taxes live in summary rows."""
    return _safe_float(
        doc.get("expected_line_total_amount")
        or doc.get("net_amount")
        or doc.get("expected_total_amount")
        or doc.get("total_amount"),
        None,
    )


def prepare_corpus(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    manifest_payload = select_corpus_documents(load_comp1_documents())
    ground_truth_payload = build_ground_truth_template(manifest_payload)
    write_json(manifest_path, manifest_payload)
    write_json(ground_truth_path, ground_truth_payload)
    write_pending_report(report_path, manifest_payload)
    return manifest_payload


def _provider_for_model(model: str) -> tuple[Any, str]:
    load_llm_keys()
    settings.reload()
    openrouter_key = (
        getattr(settings, "BWCACC_OPENROUTER_API_KEY", "")
        or os.environ.get("BWCACC_OPENROUTER_API_KEY", "")
        or settings.OPENROUTER_API_KEY
        or os.environ.get("OPENROUTER_API_KEY", "")
    )
    if openrouter_key:
        return (
            OpenRouterProvider(
                api_key=openrouter_key,
                base_url=settings.OPENROUTER_BASE_URL,
            ),
            model,
        )
    if model.startswith("anthropic/") and settings.ANTHROPIC_API_KEY:
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY), model.split("/", 1)[1]
    raise RuntimeError(f"No configured provider available for model: {model}")


def _call_provider_with_page_limit(
    provider: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    image_paths: list[str],
    max_pages: int,
) -> Any:
    previous = os.environ.get("STAGE_C_MAX_PAGES")
    os.environ["STAGE_C_MAX_PAGES"] = str(max_pages)
    try:
        return provider.call(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_paths=image_paths,
        )
    finally:
        if previous is None:
            os.environ.pop("STAGE_C_MAX_PAGES", None)
        else:
            os.environ["STAGE_C_MAX_PAGES"] = previous


def _estimate_cost_thb(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    lowered = model.lower()
    if "gemini-2.5-flash-lite" in lowered:
        input_price = 0.075 / 1_000_000
        output_price = 0.30 / 1_000_000
    elif "gpt-4.1-nano" in lowered:
        input_price = 0.10 / 1_000_000
        output_price = 0.40 / 1_000_000
    elif "qwen3-vl-8b" in lowered:
        input_price = 0.08 / 1_000_000
        output_price = 0.50 / 1_000_000
    elif "qwen3-vl-32b" in lowered:
        input_price = 0.104 / 1_000_000
        output_price = 0.416 / 1_000_000
    elif "mistral-small-3.2" in lowered:
        input_price = 0.075 / 1_000_000
        output_price = 0.20 / 1_000_000
    elif "llama-4-scout" in lowered:
        input_price = 0.10 / 1_000_000
        output_price = 0.30 / 1_000_000
    elif "gemini-2.5-flash" in lowered:
        input_price = 0.30 / 1_000_000
        output_price = 2.50 / 1_000_000
    elif "claude-sonnet-4" in lowered:
        input_price = 3.00 / 1_000_000
        output_price = 15.00 / 1_000_000
    else:
        input_price = 1.0 / 1_000_000
        output_price = 5.0 / 1_000_000
    usd = (prompt_tokens * input_price) + (completion_tokens * output_price)
    return round(usd * 33.0, 4)


def bootstrap_labels(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    model: str = "google/gemini-2.5-flash",
    limit: int | None = None,
    force: bool = False,
    doc_ids: set[str] | None = None,
    max_pages: int = 4,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    doc_lookup = {doc["doc_id"]: doc for doc in manifest["documents"]}
    provider, resolved_model = _provider_for_model(model)

    updated = 0
    for item in ground_truth["documents"]:
        if doc_ids and item["doc_id"] not in doc_ids:
            continue
        if item["selection_status"] not in {"core", "reserve"}:
            continue
        if not force and item["label_status"] not in {"pending_bootstrap", "bootstrap_failed"}:
            continue
        doc = doc_lookup[item["doc_id"]]
        ocr_text, _avg_conf = _ocr_text(Path(doc["file_path"]))
        prompt = build_user_prompt(doc, ocr_text)
        started = time.perf_counter()
        try:
            response = _call_provider_with_page_limit(
                provider,
                model=resolved_model,
                system_prompt=build_system_prompt(),
                user_prompt=prompt,
                image_paths=[doc["file_path"]],
                max_pages=max_pages,
            )
            parsed = parse_line_item_response(response.text)
            raw_dir = (
                ground_truth_path.parent
                / "bootstrap_raw"
                / resolved_model.replace("/", "__")
            )
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{item['doc_id']}.json"
            write_json(
                raw_path,
                {
                    "doc_id": item["doc_id"],
                    "model": resolved_model,
                    "raw_text": response.text,
                    "parsed": parsed,
                    "prompt_tokens": response.input_tokens,
                    "completion_tokens": response.output_tokens,
                },
            )
            item["line_items"] = parsed.get("line_items", [])
            item["label_status"] = "bootstrap_draft"
            item["bootstrap"] = {
                "model": resolved_model,
                "completed_at": now_iso(),
                "raw_output_path": str(raw_path),
            }
            item["review_notes"] = "; ".join(parsed.get("notes", []))
        except Exception as exc:
            item["label_status"] = "bootstrap_failed"
            item["review_notes"] = f"Bootstrap failed: {exc}"
        item["bootstrap"]["elapsed_sec"] = round(time.perf_counter() - started, 4)
        updated += 1
        if limit is not None and updated >= limit:
            break

    write_json(ground_truth_path, ground_truth)
    return ground_truth


def _load_locked_truth_documents(
    manifest_path: Path, ground_truth_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    manifest_lookup = {doc["doc_id"]: doc for doc in manifest["documents"]}
    locked_docs: list[dict[str, Any]] = []
    for item in ground_truth["documents"]:
        if item["selection_status"] != "core":
            continue
        if item["label_status"] not in {"human_verified", "locked"}:
            continue
        merged = dict(item)
        merged.update(manifest_lookup[item["doc_id"]])
        locked_docs.append(merged)
    return manifest, locked_docs


def evaluate_models(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    models: list[str] | None = None,
    max_pages: int = 4,
) -> dict[str, Any]:
    selected_models = models or list(DEFAULT_MODEL_SET)
    manifest, locked_docs = _load_locked_truth_documents(manifest_path, ground_truth_path)
    if not locked_docs:
        raise RuntimeError("No locked core documents found. Human verification is required before evaluation.")

    results_dir.mkdir(parents=True, exist_ok=True)
    timed_review_docs = {
        doc["doc_id"] for doc in locked_docs if doc.get("timed_review_eligible", False)
    }
    per_model_documents: dict[str, list[dict[str, Any]]] = {}
    per_model_summary: dict[str, Any] = {}

    for model in selected_models:
        provider, resolved_model = _provider_for_model(model)
        model_docs: list[dict[str, Any]] = []
        raw_dir = results_dir / resolved_model.replace("/", "__")
        raw_dir.mkdir(parents=True, exist_ok=True)

        for doc in locked_docs:
            ocr_text, _avg_conf = _ocr_text(Path(doc["file_path"]))
            prompt = build_user_prompt(doc, ocr_text)
            started = time.perf_counter()
            response = _call_provider_with_page_limit(
                provider,
                model=resolved_model,
                system_prompt=build_system_prompt(),
                user_prompt=prompt,
                image_paths=[doc["file_path"]],
                max_pages=max_pages,
            )
            elapsed = round(time.perf_counter() - started, 4)
            parsed = parse_line_item_response(response.text)
            raw_path = raw_dir / f"{doc['doc_id']}.json"
            write_json(
                raw_path,
                {
                    "doc_id": doc["doc_id"],
                    "model": resolved_model,
                    "raw_text": response.text,
                    "parsed": parsed,
                    "prompt_tokens": response.input_tokens,
                    "completion_tokens": response.output_tokens,
                },
            )
            scoring = score_document(
                truth_rows=doc.get("line_items", []),
                predicted_rows=parsed.get("line_items", []),
                expected_total=expected_line_total_for_doc(doc),
            )
            review_measurement = (
                doc.get("timed_review_measurements", {}).get(model)
                or doc.get("timed_review_measurements", {}).get(resolved_model)
                or {}
            )
            model_docs.append(
                {
                    "doc_id": doc["doc_id"],
                    "model": resolved_model,
                    "elapsed_sec": elapsed,
                    "cost_thb": _estimate_cost_thb(
                        response.input_tokens, response.output_tokens, resolved_model
                    ),
                    "manual_review_seconds": review_measurement.get("seconds"),
                    "predicted_document_total": parsed.get("document_total", ""),
                    "predicted_line_items": parsed.get("line_items", []),
                    "scoring": scoring,
                    "raw_output_path": str(raw_path),
                }
            )

        summary = aggregate_model_reports(model, model_docs, timed_review_docs)
        per_model_documents[model] = model_docs
        per_model_summary[model] = summary

    ranked = sorted(
        per_model_summary.values(),
        key=lambda row: (
            row["pass_count"],
            row["document_success_rate"],
            row["line_total_reconciliation_rate"],
            -row["cost_per_document_thb"],
        ),
        reverse=True,
    )
    best = ranked[0]
    results_payload = {
        "schema_version": "task-906-results-v1",
        "generated_at": now_iso(),
        "manifest_summary": manifest["summary"],
        "timed_review_doc_ids": sorted(timed_review_docs),
        "models": selected_models,
        "per_model_summary": per_model_summary,
        "per_model_documents": per_model_documents,
        "recommendation": {
            "best_model": best["model"],
            "decision": best["decision"],
            "rationale": (
                f"{best['model']} leads with {best['pass_count']}/6 metrics passed, "
                f"document success {best['document_success_rate']:.2%}, "
                f"and cost {best['cost_per_document_thb']:.4f} THB/doc."
            ),
        },
    }
    write_json(results_dir / "task_906_results.json", results_payload)
    return results_payload


def render_report(results_payload: dict[str, Any]) -> str:
    coverage = results_payload["manifest_summary"]["diversity_coverage"]["counts"]
    recommendation = results_payload["recommendation"]
    lines = [
        "# TASK-906 Feasibility Report",
        "",
        f"> Generated at: `{results_payload['generated_at']}`",
        "",
        "## Corpus summary",
        "",
        f"- Core docs: `{results_payload['manifest_summary']['core_count']}`",
        f"- Reserve docs: `{results_payload['manifest_summary']['reserve_count']}`",
        f"- Timed review docs: `{results_payload['manifest_summary']['timed_review_count']}`",
        "",
        "## Diversity coverage",
        "",
    ]
    for key, value in coverage.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Model comparison",
            "",
            "| Model | Decision | Pass | Doc success | Reconciliation | Cost/doc (THB) | Time/doc (s) | Manual correction (min) | 10K docs/mo | 20K docs/mo |",
            "|------|----------|------:|------------:|---------------:|---------------:|-------------:|------------------------:|------------:|------------:|",
        ]
    )
    for summary in results_payload["per_model_summary"].values():
        manual = summary["manual_correction_time_min"]
        manual_text = "n/a" if math.isinf(manual) else f"{manual:.2f}"
        lines.append(
            f"| `{summary['model']}` | {summary['decision']} | {summary['pass_count']}/6 | "
            f"{summary['document_success_rate']:.2%} | {summary['line_total_reconciliation_rate']:.2%} | "
            f"{summary['cost_per_document_thb']:.4f} | {summary['processing_time_per_document_sec']:.2f} | "
            f"{manual_text} | {summary['cost_projection_thb']['10000_docs_month']:.2f} | "
            f"{summary['cost_projection_thb']['20000_docs_month']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Best model: `{recommendation['best_model']}`",
            f"- Final decision: **{recommendation['decision']}**",
            f"- Rationale: {recommendation['rationale']}",
            "",
            "## Supported vs failing patterns",
            "",
            "This section is derived from per-document scoring. Review the JSON results for exact failing docs and line-item mismatches.",
        ]
    )
    if recommendation["decision"] == "Conditional":
        lines.extend(
            [
                "",
                "## Conditional scope guidance",
                "",
                "Allow only the document formats whose documents passed document-level success and line-total reconciliation during the PoC run.",
            ]
        )
    return "\n".join(lines) + "\n"


def write_report(
    results_path: Path = DEFAULT_RESULTS_DIR / "task_906_results.json",
    report_path: Path = DEFAULT_REPORT_PATH,
) -> str:
    results_payload = json.loads(results_path.read_text(encoding="utf-8"))
    markdown = render_report(results_payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")
    return markdown


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TASK-906 line-item PoC harness")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare-corpus", help="Generate corpus manifest and ground-truth scaffold")
    prepare.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    prepare.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH_PATH))
    prepare.add_argument("--report", default=str(DEFAULT_REPORT_PATH))

    bootstrap = sub.add_parser("bootstrap-labels", help="Bootstrap line-item labels with one model")
    bootstrap.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    bootstrap.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH_PATH))
    bootstrap.add_argument("--model", default="google/gemini-2.5-flash")
    bootstrap.add_argument("--limit", type=int, default=None)
    bootstrap.add_argument("--force", action="store_true", help="Re-run documents that already have bootstrap drafts")
    bootstrap.add_argument("--doc-ids", default="", help="Comma-separated doc_ids to bootstrap")
    bootstrap.add_argument("--max-pages", type=int, default=4, help="Max rendered pages sent to vision model")

    evaluate = sub.add_parser("evaluate", help="Evaluate all models against locked ground truth")
    evaluate.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    evaluate.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH_PATH))
    evaluate.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    evaluate.add_argument("--models", nargs="*", default=list(DEFAULT_MODEL_SET))
    evaluate.add_argument("--max-pages", type=int, default=4, help="Max rendered pages sent to vision model")

    report = sub.add_parser("render-report", help="Render final markdown report from JSON results")
    report.add_argument("--results", default=str(DEFAULT_RESULTS_DIR / "task_906_results.json"))
    report.add_argument("--report", default=str(DEFAULT_REPORT_PATH))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare-corpus":
        prepare_corpus(
            manifest_path=Path(args.manifest),
            ground_truth_path=Path(args.ground_truth),
            report_path=Path(args.report),
        )
        print(f"OK: wrote {args.manifest}")
        print(f"OK: wrote {args.ground_truth}")
        print(f"OK: wrote {args.report}")
        return 0

    if args.command == "bootstrap-labels":
        bootstrap_labels(
            manifest_path=Path(args.manifest),
            ground_truth_path=Path(args.ground_truth),
            model=args.model,
            limit=args.limit,
            force=args.force,
            doc_ids={doc_id.strip() for doc_id in args.doc_ids.split(",") if doc_id.strip()} or None,
            max_pages=args.max_pages,
        )
        print(f"OK: updated {args.ground_truth}")
        return 0

    if args.command == "evaluate":
        results = evaluate_models(
            manifest_path=Path(args.manifest),
            ground_truth_path=Path(args.ground_truth),
            results_dir=Path(args.results_dir),
            models=args.models,
            max_pages=args.max_pages,
        )
        out_path = Path(args.results_dir) / "task_906_results.json"
        print(f"OK: wrote {out_path}")
        print(json.dumps(results["recommendation"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "render-report":
        write_report(results_path=Path(args.results), report_path=Path(args.report))
        print(f"OK: wrote {args.report}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
