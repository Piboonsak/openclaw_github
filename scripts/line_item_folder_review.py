"""Run TASK-906 line-item vision extraction across one source folder and render HTML."""

from __future__ import annotations

import argparse
import html
import json
import math
import random
import re
import sys
import time
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.line_item_poc import (  # noqa: E402
    COMP1_ROOT,
    _call_provider_with_page_limit,
    _estimate_cost_thb,
    _ocr_text,
    _provider_for_model,
    _safe_float,
    now_iso,
    read_jsonl,
    write_json,
)
from scripts.line_item_prompts import (  # noqa: E402
    build_system_prompt,
    build_user_prompt,
    parse_line_item_response,
)

DEFAULT_FOLDER = COMP1_ROOT / "ฤทธิ์ล้ำเลิศ บิลซื้อ RRL"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
DEFAULT_RESULT_PATH = (
    ROOT / "private_data" / "poc" / "line_item_poc" / "folder_scan_results.json"
)
DEFAULT_HTML_PATH = (
    ROOT / "docs" / "PoC" / "reports" / "TASK-906-LINE-ITEM-FOLDER-REVIEW.html"
)
DEFAULT_V2_RESULT_PATH = (
    ROOT / "private_data" / "poc" / "line_item_poc" / "folder_scan_results_confidence_v2.json"
)
DEFAULT_V2_HTML_PATH = (
    ROOT / "docs" / "PoC" / "reports" / "TASK-906-LINE-ITEM-FOLDER-REVIEW-V2.html"
)
DEFAULT_V3_RESULT_PATH = (
    ROOT / "private_data" / "poc" / "line_item_poc" / "folder_scan_results_comp3_v3.json"
)
DEFAULT_V3_HTML_PATH = (
    ROOT / "docs" / "PoC" / "reports" / "TASK-906-LINE-ITEM-FOLDER-REVIEW-V3-COMP3.html"
)

LABOR_SERVICE_KEYWORDS = [
    "ค่าแรง",
    "ค่าบริการ",
    "ค่าซ่อม",
    "ค่าติดตั้ง",
    "ค่าเดินทาง",
    "ค่าส่ง",
    "ค่าขนส่ง",
    "ขนส่ง",
    "บริการ",
    "fee",
    "wage",
    "labor",
    "labour",
    "service",
    "delivery",
    "shipping",
    "transport",
    "repair",
    "installation",
    "install",
    "welding",
    "milling",
]
PROCESS_SERVICE_KEYWORDS = [
    "เคลือบ",
    "ชุบ",
    "ทำสี",
    "พ่นสี",
    "กลึง",
    "กัด",
    "เจียร",
    "ซ่อม",
    "coating",
    "coat",
    "plating",
    "painting",
    "machining",
    "polishing",
]
GENERIC_EXPENSE_PREFIXES = ["ค่า"]
PART_MATERIAL_KEYWORDS = [
    "ท่อ",
    "ท่อแบน",
    "แหวน",
    "สกรู",
    "น็อต",
    "น๊อต",
    "ลูกปืน",
    "สายพาน",
    "โซ่",
    "เฟือง",
    "มอเตอร์",
    "ปั๊ม",
    "วาล์ว",
    "เซ็นเซอร์",
    "สายไฟ",
    "สวิตช์",
    "แผ่น",
    "เหล็ก",
    "อลูมิเนียม",
    "bearing",
    "screw",
    "bolt",
    "nut",
    "washer",
    "motor",
    "sensor",
    "valve",
    "pipe",
    "plate",
    "roller",
    "sprocket",
    "cable",
    "connector",
    "clamp",
    "arm",
    "control",
    "part",
    "spare",
    "material",
]
STOCK_UNIT_KEYWORDS = [
    "ชิ้น",
    "ตัว",
    "อัน",
    "เส้น",
    "ท่อน",
    "แท่ง",
    "ชุด",
    "กล่อง",
    "ม้วน",
    "แผ่น",
    "pcs",
    "pcs.",
    "pc",
    "piece",
    "set",
    "roll",
    "box",
    "meter",
    "metre",
    "kg",
    "ea",
    "each",
    "rl",
    "ตลับ",
]
OFFICE_SUPPLY_KEYWORDS = [
    "กระดาษ",
    "สมุด",
    "ปากกา",
    "แฟ้ม",
    "หมึก",
    "เครื่องเขียน",
    "office supply",
    "paper",
    "pen",
    "notebook",
    "toner",
    "stationery",
    "เก้าอี้",
    "chair",
]


def _money(value: Any) -> str:
    number = _safe_float(value, None)
    return "" if number is None else f"{number:,.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _slug(value: str) -> str:
    keep = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "document"


def _normalize_alias(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^0-9a-zA-Zก-๙#./() -]+", "", text)
    return text.strip()


def _normalize_unit(value: Any) -> str:
    unit = str(value or "").lower().strip().replace(".", "")
    aliases = {
        "pcs": "pcs",
        "pc": "pcs",
        "piece": "pcs",
        "ชิ้น": "pcs",
        "ea": "ea",
        "each": "ea",
        "set": "set",
        "ชุด": "set",
        "rl": "roll",
        "roll": "roll",
        "ม้วน": "roll",
        "ตลับ": "ตลับ",
    }
    return aliases.get(unit, unit)


def _units_compatible(left: Any, right: Any) -> bool:
    left_unit = _normalize_unit(left)
    right_unit = _normalize_unit(right)
    return not left_unit or not right_unit or left_unit == right_unit


def _line_sum(items: list[dict[str, Any]]) -> float:
    total = 0.0
    for item in items:
        amount = _safe_float(item.get("line_amount"), None)
        if amount is not None:
            total += amount
    return round(total, 2)


def _find_corpus_root(folder: Path) -> Path:
    folder = folder.resolve()
    for candidate in [folder, *folder.parents]:
        if candidate.parent.name == "poc" and candidate.name.startswith("Comp_"):
            return candidate
    return folder


def _select_pdfs(
    folder: Path,
    *,
    recursive: bool,
    limit: int | None,
    sample: int | None,
    seed: int,
    max_file_mb: float | None,
    exclude_paths: set[str] | None = None,
) -> list[Path]:
    pdfs = sorted(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    if max_file_mb is not None:
        max_bytes = max_file_mb * 1024 * 1024
        pdfs = [path for path in pdfs if path.stat().st_size <= max_bytes]
    if exclude_paths:
        pdfs = [
            path for path in pdfs
            if str(path.resolve()).lower() not in exclude_paths
        ]
    if sample is not None and sample < len(pdfs):
        rng = random.Random(seed)
        pdfs = sorted(rng.sample(pdfs, sample))
    if limit is not None:
        pdfs = pdfs[:limit]
    return pdfs


def _line_type(product_name: Any, unit: Any) -> dict[str, Any]:
    text = f"{product_name or ''} {unit or ''}".lower()
    labor_keywords = [
        "m/c",
        "milling",
        "machine",
        "repair",
        "service",
        "installation",
        "welding",
        "ซ่อม",
        "ค่าแรง",
        "งาน",
        "ติดตั้ง",
        "เชื่อม",
    ]
    part_keywords = [
        "pcs",
        "pc",
        "piece",
        "pcs.",
        "bearing",
        "roller",
        "sensor",
        "arm",
        "clamp",
        "supply",
        "control",
        "ชุด",
        "ชิ้น",
        "อะไหล่",
    ]
    labor_hits = sum(1 for keyword in labor_keywords if keyword in text)
    part_hits = sum(1 for keyword in part_keywords if keyword in text)
    if labor_hits and part_hits:
        return {
            "type": "mixed_or_service_with_material",
            "confidence": min(0.55 + 0.1 * (labor_hits + part_hits), 0.85),
            "reason": "labor/service and part signals both present",
        }
    if labor_hits:
        return {
            "type": "labor_or_service",
            "confidence": min(0.60 + 0.12 * labor_hits, 0.90),
            "reason": "labor/service keywords",
        }
    if part_hits:
        return {
            "type": "part_or_material",
            "confidence": min(0.58 + 0.10 * part_hits, 0.88),
            "reason": "unit or part keywords",
        }
    return {
        "type": "unknown",
        "confidence": 0.35,
        "reason": "no strong category signal",
    }


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword and keyword.lower() in text]


def _unit_signal(unit: Any) -> tuple[float, list[str]]:
    unit_text = str(unit or "").strip().lower()
    if not unit_text:
        return 0.0, []
    hits = _contains_any(unit_text, STOCK_UNIT_KEYWORDS)
    if hits:
        return min(0.45 + 0.1 * len(hits), 0.75), [f"stock-like unit: {', '.join(hits[:3])}"]
    return 0.15, ["unit present but not stock-specific"]


def _classification_result(
    line_type: str,
    confidence: float,
    stock_candidate: bool,
    reasons: list[str],
    reconciled: bool,
    score_breakdown: dict[str, float] | None = None,
) -> dict[str, Any]:
    if reconciled:
        confidence = min(confidence + 0.03, 0.98)
        reasons = [*reasons, "document line total reconciled"]
    if score_breakdown is not None:
        capped_total = round(sum(score_breakdown.values()), 4)
        confidence = min(max(capped_total, 0.0), 0.98)
        if reconciled and "amount_reconcile" not in score_breakdown:
            score_breakdown["amount_reconcile"] = 0.10
            confidence = min(confidence + 0.10, 0.98)
    band = "green" if confidence >= 0.65 else "amber" if confidence >= 0.50 else "red"
    return {
        "type": line_type,
        "confidence": round(confidence, 4),
        "band": band,
        "stock_candidate": stock_candidate,
        "reason": "; ".join(reasons),
        "reasons": reasons,
        "score_breakdown": score_breakdown or {},
    }


def _stock_score_breakdown(
    *,
    keyword_score: float,
    unit_score: float,
    reconciled: bool,
    extraction_quality: float = 0.18,
    company_master_match: float = 0.0,
    human_confirm_history: float = 0.0,
) -> dict[str, float]:
    return {
        "extraction_quality": min(max(extraction_quality, 0.0), 0.20),
        "keyword_signal": min(max(keyword_score, 0.0), 0.20),
        "unit_signal": min(max(unit_score, 0.0), 0.25),
        "amount_reconcile": 0.10 if reconciled else 0.0,
        "company_master_match": min(max(company_master_match, 0.0), 0.10),
        "human_confirm_history": min(max(human_confirm_history, 0.0), 0.15),
    }


def _load_master_aliases(master_file: Path | None) -> dict[str, Any]:
    if not master_file or not master_file.exists():
        return {"aliases": [], "by_alias": {}}
    payload = json.loads(master_file.read_text(encoding="utf-8"))
    aliases = payload.get("aliases", []) if isinstance(payload, dict) else []
    by_alias: dict[str, list[dict[str, Any]]] = {}
    for alias in aliases:
        normalized = alias.get("normalized_alias") or _normalize_alias(alias.get("alias_text"))
        if not normalized:
            continue
        alias["normalized_alias"] = normalized
        by_alias.setdefault(normalized, []).append(alias)
    return {"aliases": aliases, "by_alias": by_alias, "path": str(master_file)}


def _load_excluded_paths(exclude_result: Path | None) -> set[str]:
    if not exclude_result or not exclude_result.exists():
        return set()
    payload = json.loads(exclude_result.read_text(encoding="utf-8"))
    paths = set()
    for doc in payload.get("documents", []):
        file_path = doc.get("file_path")
        if file_path:
            paths.add(str(Path(file_path).resolve()).lower())
    return paths


def _best_master_match(product_name: Any, unit: Any, master: dict[str, Any]) -> dict[str, Any] | None:
    normalized = _normalize_alias(product_name)
    if not normalized:
        return None
    exact_candidates = [
        item
        for item in master.get("by_alias", {}).get(normalized, [])
        if _units_compatible(unit, item.get("unit"))
    ]
    if exact_candidates:
        best = max(exact_candidates, key=lambda item: int(item.get("confirmed_count", 0) or 0))
        return {
            "match_type": "exact_alias",
            "similarity": 1.0,
            "alias": best,
        }

    best_match: dict[str, Any] | None = None
    best_similarity = 0.0
    for alias in master.get("aliases", []):
        if not _units_compatible(unit, alias.get("unit")):
            continue
        similarity = SequenceMatcher(None, normalized, alias.get("normalized_alias", "")).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = alias
    if best_match and best_similarity >= 0.92:
        return {
            "match_type": "fuzzy_alias",
            "similarity": round(best_similarity, 4),
            "alias": best_match,
        }
    return None


def _apply_master_match(
    classification: dict[str, Any],
    item: dict[str, Any],
    master: dict[str, Any],
) -> dict[str, Any]:
    match = _best_master_match(item.get("product_name"), item.get("unit"), master)
    if not match:
        return classification

    alias = match["alias"]
    confirmed_count = int(alias.get("confirmed_count", 0) or 0)
    rejected_count = int(alias.get("rejected_count", 0) or 0)
    no_conflict = classification.get("type") not in {"labor", "service", "service_with_material"}
    trusted = (
        match["match_type"] == "exact_alias"
        and confirmed_count >= 10
        and rejected_count == 0
        and no_conflict
    )
    updated = dict(classification)
    reasons = list(updated.get("reasons") or [])
    reasons.append(
        f"{match['match_type']} master match: {alias.get('alias_text')} "
        f"(confirmed {confirmed_count}, similarity {match['similarity']:.2f})"
    )

    if trusted:
        updated.update(
            {
                "type": "stock_item",
                "confidence": 1.0,
                "band": "green",
                "stock_candidate": True,
                "match_status": "trusted_confirmed_alias",
                "matched_alias": alias,
                "reason": "; ".join(reasons),
                "reasons": reasons,
                "score_breakdown": {
                    "extraction_quality": 0.20,
                    "keyword_signal": min(
                        float(updated.get("score_breakdown", {}).get("keyword_signal", 0.0) or 0.0),
                        0.20,
                    ),
                    "unit_signal": min(
                        max(float(updated.get("score_breakdown", {}).get("unit_signal", 0.0) or 0.0), 0.20),
                        0.25,
                    ),
                    "amount_reconcile": float(
                        updated.get("score_breakdown", {}).get("amount_reconcile", 0.0) or 0.0
                    ),
                    "company_master_match": 0.10,
                    "human_confirm_history": 0.15,
                },
            }
        )
        return updated

    if no_conflict:
        breakdown = dict(updated.get("score_breakdown") or {})
        breakdown["company_master_match"] = 0.08 if match["match_type"] == "fuzzy_alias" else 0.10
        breakdown["human_confirm_history"] = min(0.02 + confirmed_count * 0.01, 0.15)
        confidence = min(sum(float(value or 0.0) for value in breakdown.values()), 0.90)
        updated.update(
            {
                "type": "stock_item" if confidence >= 0.65 else updated.get("type"),
                "confidence": round(confidence, 4),
                "band": "green" if confidence >= 0.65 else "amber" if confidence >= 0.50 else "red",
                "stock_candidate": True,
                "match_status": "candidate_alias_match",
                "matched_alias": alias,
                "reason": "; ".join(reasons),
                "reasons": reasons,
                "score_breakdown": breakdown,
            }
        )
    return updated


def _line_type(
    product_name: Any,
    unit: Any,
    *,
    has_wht: bool = False,
    reconciled: bool = False,
) -> dict[str, Any]:
    name = str(product_name or "")
    text = f"{name} {unit or ''}".lower()
    explicit_labor_hits = _contains_any(text, LABOR_SERVICE_KEYWORDS)
    generic_expense_hits = [
        keyword for keyword in GENERIC_EXPENSE_PREFIXES if name.strip().startswith(keyword)
    ]
    part_hits = _contains_any(text, PART_MATERIAL_KEYWORDS)
    process_hits = _contains_any(text, PROCESS_SERVICE_KEYWORDS)
    office_hits = _contains_any(text, OFFICE_SUPPLY_KEYWORDS)
    unit_score, unit_reasons = _unit_signal(unit)

    if process_hits and unit_score < 0.45:
        confidence = min(0.70 + 0.07 * len(process_hits), 0.90)
        reasons = [f"process/service keyword without stock unit: {', '.join(process_hits[:3])}"]
        if part_hits:
            reasons.append(f"material appears to be the service target: {', '.join(part_hits[:3])}")
        return _classification_result("service_with_material", confidence, False, reasons, reconciled)

    if office_hits:
        keyword_score = min(0.10 + 0.04 * len(office_hits), 0.16)
        capped_unit_score = 0.18 if unit_score >= 0.45 else 0.05
        breakdown = _stock_score_breakdown(
            keyword_score=keyword_score,
            unit_score=capped_unit_score,
            reconciled=reconciled,
            extraction_quality=0.16,
        )
        reasons = [
            f"office/general product keyword: {', '.join(office_hits[:3])}",
            *unit_reasons,
            "physical item, needs company policy review before stock posting",
        ]
        return _classification_result(
            "office_supply",
            0.0,
            True,
            reasons,
            reconciled,
            score_breakdown=breakdown,
        )

    if explicit_labor_hits:
        confidence = min(0.72 + 0.08 * len(explicit_labor_hits), 0.96)
        reasons = [f"labor/service keyword: {', '.join(explicit_labor_hits[:3])}"]
        if has_wht:
            confidence = min(confidence + 0.06, 0.98)
            reasons.append("document has WHT signal")
        if part_hits or unit_score >= 0.45:
            confidence = max(confidence - 0.08, 0.70)
            reasons.extend(["also has material/unit signal, keep for review", *unit_reasons])
            return _classification_result("service_with_material", confidence, False, reasons, reconciled)
        return _classification_result("labor", confidence, False, reasons, reconciled)

    if generic_expense_hits:
        confidence = 0.66
        reasons = ["generic Thai expense prefix: ค่า"]
        if has_wht:
            confidence += 0.06
            reasons.append("document has WHT signal")
        return _classification_result("service", min(confidence, 0.86), False, reasons, reconciled)

    if part_hits:
        keyword_score = min(0.12 + 0.04 * len(part_hits), 0.20)
        capped_unit_score = 0.22 if unit_score >= 0.45 else 0.05
        breakdown = _stock_score_breakdown(
            keyword_score=keyword_score,
            unit_score=capped_unit_score,
            reconciled=reconciled,
            extraction_quality=0.18,
        )
        reasons = [f"part/material keyword: {', '.join(part_hits[:3])}", *unit_reasons]
        return _classification_result(
            "part_or_material",
            0.0,
            True,
            reasons,
            reconciled,
            score_breakdown=breakdown,
        )

    if unit_score >= 0.45:
        breakdown = _stock_score_breakdown(
            keyword_score=0.10,
            unit_score=0.25,
            reconciled=reconciled,
            extraction_quality=0.18,
        )
        reasons = [*unit_reasons, "stock-like unit boosts physical product decision"]
        return _classification_result(
            "part_or_material",
            0.0,
            True,
            reasons,
            reconciled,
            score_breakdown=breakdown,
        )

    if has_wht:
        return _classification_result(
            "service",
            0.54,
            False,
            ["document has WHT signal but row has no strong keyword"],
            reconciled,
        )

    return _classification_result("unknown", 0.35, False, ["no strong category signal"], reconciled)


def _expectation_lookup(corpus_root: Path) -> dict[str, dict[str, Any]]:
    expectations_path = corpus_root / "expectations.filled.jsonl"
    if not expectations_path.exists():
        return {}
    rows = read_jsonl(expectations_path)
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        lookup[str(row.get("file_name") or "")] = row
    return lookup


def _metadata_for_file(
    path: Path,
    expectations: dict[str, dict[str, Any]],
    corpus_root: Path,
) -> dict[str, Any]:
    row = expectations.get(path.name, {})
    try:
        relative_path = str(path.relative_to(corpus_root))
    except ValueError:
        relative_path = path.name
    return {
        "doc_id": row.get("doc_id") or path.stem,
        "file_name": path.name,
        "file_path": str(path),
        "relative_path": relative_path,
        "invoice_number": row.get("invoice_number", ""),
        "invoice_date": row.get("invoice_date", ""),
        "seller_name": row.get("seller_name", ""),
        "currency": row.get("currency", "THB") or "THB",
        "net_amount": row.get("net_amount", ""),
        "vat_amount": row.get("vat_amount", ""),
        "total_amount": row.get("total_amount", ""),
        "wht_amount": row.get("wht_amount", ""),
        "has_wht": row.get("has_wht", ""),
        "page_count": row.get("page_count", ""),
        "is_multi_page": row.get("is_multi_page", ""),
    }


def run_folder_scan(
    *,
    folder: Path,
    model: str,
    output: Path,
    max_pages: int,
    limit: int | None,
    sample: int | None,
    seed: int,
    recursive: bool,
    max_file_mb: float | None,
    master_file: Path | None,
    exclude_result: Path | None,
    force: bool,
) -> dict[str, Any]:
    provider, resolved_model = _provider_for_model(model)
    folder = folder.resolve()
    corpus_root = _find_corpus_root(folder)
    expectations = _expectation_lookup(corpus_root)
    master = _load_master_aliases(master_file)
    exclude_paths = _load_excluded_paths(exclude_result)
    pdfs = _select_pdfs(
        folder,
        recursive=recursive,
        limit=limit,
        sample=sample,
        seed=seed,
        max_file_mb=max_file_mb,
        exclude_paths=exclude_paths,
    )

    raw_dir = output.parent / f"{output.stem}_raw" / resolved_model.replace("/", "__")
    raw_dir.mkdir(parents=True, exist_ok=True)

    documents: list[dict[str, Any]] = []
    for index, path in enumerate(pdfs, 1):
        metadata = _metadata_for_file(path, expectations, corpus_root)
        raw_path = raw_dir / f"{index:03d}_{_slug(metadata['doc_id'])}.json"
        if raw_path.exists() and not force:
            raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
            parsed = raw_payload["parsed"]
            prompt_tokens = int(raw_payload.get("prompt_tokens", 0) or 0)
            completion_tokens = int(raw_payload.get("completion_tokens", 0) or 0)
            elapsed = float(raw_payload.get("elapsed_sec", 0.0) or 0.0)
            error = ""
            ocr_error = str(raw_payload.get("ocr_error") or "")
        else:
            ocr_error = ""
            try:
                ocr_text, avg_conf = _ocr_text(path)
            except Exception as exc:  # noqa: BLE001 - OCR fallback must not kill vision scan
                ocr_text = ""
                avg_conf = 0.0
                ocr_error = f"{type(exc).__name__}: {exc}"
            prompt = build_user_prompt(metadata, ocr_text)
            started = time.perf_counter()
            error = ""
            try:
                response = _call_provider_with_page_limit(
                    provider,
                    model=resolved_model,
                    system_prompt=build_system_prompt(),
                    user_prompt=prompt,
                    image_paths=[str(path)],
                    max_pages=max_pages,
                )
                parsed = parse_line_item_response(response.text)
                prompt_tokens = response.input_tokens
                completion_tokens = response.output_tokens
                raw_payload = {
                    "doc_id": metadata["doc_id"],
                    "file_name": path.name,
                    "model": resolved_model,
                    "elapsed_sec": round(time.perf_counter() - started, 4),
                    "avg_ocr_confidence": avg_conf,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "raw_text": response.text,
                    "parsed": parsed,
                    "error": "",
                    "ocr_error": ocr_error,
                }
            except Exception as exc:  # noqa: BLE001 - report captures provider failures
                parsed = {"document_total": "", "currency": "", "line_items": [], "notes": []}
                prompt_tokens = 0
                completion_tokens = 0
                error = f"{type(exc).__name__}: {exc}"
                raw_payload = {
                    "doc_id": metadata["doc_id"],
                    "file_name": path.name,
                    "model": resolved_model,
                    "elapsed_sec": round(time.perf_counter() - started, 4),
                    "avg_ocr_confidence": avg_conf if "avg_conf" in locals() else 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "raw_text": "",
                    "parsed": parsed,
                    "error": error,
                    "ocr_error": ocr_error,
                }
            write_json(raw_path, raw_payload)
            elapsed = float(raw_payload["elapsed_sec"])

        items = parsed.get("line_items", []) or []
        line_sum = _line_sum(items)
        expected_net = _safe_float(metadata.get("net_amount"), None)
        expected_gross = _safe_float(metadata.get("total_amount"), None)
        net_delta = None if expected_net is None else round(line_sum - expected_net, 2)
        gross_delta = None if expected_gross is None else round(line_sum - expected_gross, 2)
        status = "needs_review"
        if error:
            status = "error"
        elif expected_net is not None and abs(net_delta or 0.0) <= 1.0:
            status = "net_reconciled"
        elif expected_gross is not None and abs(gross_delta or 0.0) <= 1.0:
            status = "gross_reconciled"
        elif not items:
            status = "no_rows"

        reconciled = status in {"net_reconciled", "gross_reconciled"}
        has_wht = bool(metadata.get("has_wht")) or _safe_float(metadata.get("wht_amount"), None) not in (None, 0.0)
        enriched_items: list[dict[str, Any]] = []
        for item in items:
            enriched = dict(item)
            enriched["classification"] = _line_type(
                item.get("product_name"),
                item.get("unit"),
                has_wht=has_wht,
                reconciled=reconciled,
            )
            enriched["classification"] = _apply_master_match(
                enriched["classification"],
                enriched,
                master,
            )
            enriched_items.append(enriched)

        documents.append(
            {
                "index": index,
                "status": status,
                "doc_id": metadata["doc_id"],
                "file_name": path.name,
                "file_path": str(path),
                "invoice_number": metadata.get("invoice_number", ""),
                "seller_name": metadata.get("seller_name", ""),
                "page_count": metadata.get("page_count", ""),
                "expected_net": expected_net,
                "expected_vat": _safe_float(metadata.get("vat_amount"), None),
                "expected_gross": expected_gross,
                "model_document_total": parsed.get("document_total", ""),
                "line_sum": line_sum,
                "net_delta": net_delta,
                "gross_delta": gross_delta,
                "row_count": len(items),
                "elapsed_sec": elapsed,
                "cost_thb": _estimate_cost_thb(prompt_tokens, completion_tokens, resolved_model),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "raw_output_path": str(raw_path),
                "error": error,
                "ocr_error": ocr_error,
                "notes": parsed.get("notes", []),
                "line_items": enriched_items,
            }
        )

    summary = _summarize(documents)
    payload = {
        "schema_version": "task-906-folder-scan-v1",
        "generated_at": now_iso(),
        "folder": str(folder),
        "corpus_root": str(corpus_root),
        "model": resolved_model,
        "max_pages": max_pages,
        "selection": {
            "recursive": recursive,
            "limit": limit,
            "sample": sample,
            "seed": seed,
            "max_file_mb": max_file_mb,
            "selected_count": len(pdfs),
            "has_expectations": bool(expectations),
            "master_file": str(master_file) if master_file else "",
            "master_alias_count": len(master.get("aliases", [])),
            "exclude_result": str(exclude_result) if exclude_result else "",
            "excluded_count": len(exclude_paths),
        },
        "summary": summary,
        "documents": documents,
    }
    write_json(output, payload)
    return payload


def _summarize(documents: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(documents)
    counts: dict[str, int] = {}
    confidence_bands = {"green": 0, "amber": 0, "red": 0}
    line_type_counts: dict[str, int] = {}
    stock_candidate_count = 0
    for doc in documents:
        counts[doc["status"]] = counts.get(doc["status"], 0) + 1
        for item in doc.get("line_items", []):
            classification = item.get("classification", {})
            band = classification.get("band", "red")
            if band in confidence_bands:
                confidence_bands[band] += 1
            line_type = str(classification.get("type") or "unknown")
            line_type_counts[line_type] = line_type_counts.get(line_type, 0) + 1
            if classification.get("stock_candidate"):
                stock_candidate_count += 1
    total_cost = round(sum(float(doc.get("cost_thb", 0.0) or 0.0) for doc in documents), 4)
    avg_time = (
        round(sum(float(doc.get("elapsed_sec", 0.0) or 0.0) for doc in documents) / total, 2)
        if total
        else 0.0
    )
    reconciled = counts.get("net_reconciled", 0) + counts.get("gross_reconciled", 0)
    return {
        "document_count": total,
        "status_counts": dict(sorted(counts.items())),
        "reconciled_count": reconciled,
        "reconciled_rate": round(reconciled / total, 4) if total else 0.0,
        "needs_review_count": counts.get("needs_review", 0),
        "error_count": counts.get("error", 0),
        "total_rows": sum(int(doc.get("row_count", 0) or 0) for doc in documents),
        "confidence_bands": confidence_bands,
        "line_type_counts": dict(sorted(line_type_counts.items())),
        "stock_candidate_count": stock_candidate_count,
        "total_cost_thb": total_cost,
        "avg_elapsed_sec": avg_time,
    }


def _status_label(status: str) -> str:
    labels = {
        "net_reconciled": "Net matched",
        "gross_reconciled": "Gross matched",
        "needs_review": "Review",
        "no_rows": "No rows",
        "error": "Error",
    }
    return labels.get(status, status)


def _baseline_comparison(current: dict[str, Any], baseline_path: Path) -> dict[str, Any]:
    if not baseline_path.exists():
        return {"available": False, "baseline_path": str(baseline_path)}

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    old_summary = baseline.get("summary", {})
    new_summary = current.get("summary", {})
    old_docs = {doc.get("doc_id"): doc for doc in baseline.get("documents", [])}
    changed_docs = []
    for doc in current.get("documents", []):
        old_doc = old_docs.get(doc.get("doc_id"))
        if not old_doc:
            continue
        if old_doc.get("status") != doc.get("status") or old_doc.get("row_count") != doc.get("row_count"):
            changed_docs.append(
                {
                    "doc_id": doc.get("doc_id"),
                    "old_status": old_doc.get("status"),
                    "new_status": doc.get("status"),
                    "old_rows": old_doc.get("row_count"),
                    "new_rows": doc.get("row_count"),
                }
            )

    return {
        "available": True,
        "baseline_path": str(baseline_path),
        "baseline_generated_at": baseline.get("generated_at"),
        "old_reconciled_rate": old_summary.get("reconciled_rate", 0.0),
        "new_reconciled_rate": new_summary.get("reconciled_rate", 0.0),
        "reconciled_rate_delta": round(
            float(new_summary.get("reconciled_rate", 0.0) or 0.0)
            - float(old_summary.get("reconciled_rate", 0.0) or 0.0),
            4,
        ),
        "old_total_rows": old_summary.get("total_rows", 0),
        "new_total_rows": new_summary.get("total_rows", 0),
        "row_delta": int(new_summary.get("total_rows", 0) or 0)
        - int(old_summary.get("total_rows", 0) or 0),
        "old_needs_review": old_summary.get("needs_review_count", 0),
        "new_needs_review": new_summary.get("needs_review_count", 0),
        "needs_review_delta": int(new_summary.get("needs_review_count", 0) or 0)
        - int(old_summary.get("needs_review_count", 0) or 0),
        "changed_documents": changed_docs,
    }


def _score_breakdown_html(classification: dict[str, Any]) -> str:
    breakdown = classification.get("score_breakdown") or {}
    if not breakdown:
        return ""
    labels = {
        "extraction_quality": "extract",
        "keyword_signal": "keyword",
        "unit_signal": "unit",
        "amount_reconcile": "reconcile",
        "company_master_match": "master",
        "human_confirm_history": "history",
    }
    parts = [
        f"{labels.get(key, key)} {_pct(float(value or 0.0))}"
        for key, value in breakdown.items()
        if float(value or 0.0) > 0
    ]
    if not parts:
        return ""
    return f"<span class=\"score-breakdown\">{' · '.join(html.escape(part) for part in parts)}</span>"


def render_html_report(payload: dict[str, Any], html_path: Path) -> None:
    summary = payload["summary"]
    selection = payload.get("selection", {})
    generated = html.escape(payload["generated_at"])
    model = html.escape(payload["model"])
    folder = html.escape(payload["folder"])

    doc_rows = []
    doc_sections = []
    for doc in payload["documents"]:
        status = html.escape(doc["status"])
        row_anchor = f"doc-{html.escape(_slug(doc['doc_id']))}"
        doc_rows.append(
            "<tr>"
            f"<td><a href=\"#{row_anchor}\">{html.escape(doc['doc_id'])}</a></td>"
            f"<td>{html.escape(doc['file_name'])}</td>"
            f"<td><span class=\"pill {status}\">{html.escape(_status_label(doc['status']))}</span></td>"
            f"<td class=\"num\">{doc['row_count']}</td>"
            f"<td class=\"num\">{_money(doc['expected_net'])}</td>"
            f"<td class=\"num\">{_money(doc['line_sum'])}</td>"
            f"<td class=\"num\">{_money(doc['net_delta'])}</td>"
            f"<td class=\"num\">{doc['elapsed_sec']:.2f}</td>"
            f"<td class=\"num\">{doc['cost_thb']:.4f}</td>"
            "</tr>"
        )

        item_rows = []
        for idx, item in enumerate(doc["line_items"], 1):
            cls = item.get("classification", {})
            band = str(cls.get("band", "red"))
            stock_text = "Yes" if cls.get("stock_candidate") else "No"
            stock_class = "stock-yes" if cls.get("stock_candidate") else "stock-no"
            item_rows.append(
                f"<tr class=\"conf-{html.escape(band)}\">"
                f"<td class=\"num\">{idx}</td>"
                f"<td>{html.escape(str(item.get('product_name') or ''))}</td>"
                f"<td class=\"num\">{html.escape(str(item.get('qty') or ''))}</td>"
                f"<td>{html.escape(str(item.get('unit') or ''))}</td>"
                f"<td class=\"num\">{html.escape(str(item.get('unit_price') or ''))}</td>"
                f"<td class=\"num\">{html.escape(str(item.get('line_amount') or ''))}</td>"
                f"<td>{html.escape(str(cls.get('type', 'unknown')))}</td>"
                f"<td class=\"num\"><span class=\"band {html.escape(band)}\">{_pct(float(cls.get('confidence', 0.0) or 0.0))}</span></td>"
                f"<td class=\"{stock_class}\">{stock_text}</td>"
                f"<td>{html.escape(str(cls.get('reason', '')))}{_score_breakdown_html(cls)}</td>"
                "</tr>"
            )
        if not item_rows:
            item_rows.append(
                "<tr><td colspan=\"10\" class=\"empty\">No extracted rows. Human review required.</td></tr>"
            )

        notes = "; ".join(str(note) for note in doc.get("notes", []) if note)
        error = doc.get("error") or ""
        ocr_error = doc.get("ocr_error") or ""
        doc_sections.append(
            "".join(
                [
                    f"<section class=\"doc\" id=\"{row_anchor}\">",
                    "<div class=\"doc-head\">",
                    "<div>",
                    f"<h2>{html.escape(doc['doc_id'])} - {html.escape(doc['file_name'])}</h2>",
                    f"<p>{html.escape(doc.get('seller_name') or '')}</p>",
                    "</div>",
                    f"<span class=\"pill {status}\">{html.escape(_status_label(doc['status']))}</span>",
                    "</div>",
                    "<div class=\"metrics\">",
                    f"<div><span>Invoice</span><strong>{html.escape(doc.get('invoice_number') or '')}</strong></div>",
                    f"<div><span>Net</span><strong>{_money(doc['expected_net'])}</strong></div>",
                    f"<div><span>VAT</span><strong>{_money(doc['expected_vat'])}</strong></div>",
                    f"<div><span>Gross</span><strong>{_money(doc['expected_gross'])}</strong></div>",
                    f"<div><span>Line sum</span><strong>{_money(doc['line_sum'])}</strong></div>",
                    f"<div><span>Net delta</span><strong>{_money(doc['net_delta'])}</strong></div>",
                    "</div>",
                    f"<p class=\"path\">Source: {html.escape(doc['file_path'])}</p>",
                    f"<p class=\"path\">Raw JSON: {html.escape(doc['raw_output_path'])}</p>",
                    f"<p class=\"warn\">Error: {html.escape(error)}</p>" if error else "",
                    f"<p class=\"warn\">OCR fallback warning: {html.escape(ocr_error)}</p>" if ocr_error else "",
                    f"<p class=\"note\">Notes: {html.escape(notes)}</p>" if notes else "",
                    "<table class=\"line-table\">",
                    "<thead><tr><th>#</th><th>Product / service</th><th>Qty</th><th>Unit</th><th>Unit price</th><th>Amount</th><th>Type</th><th>Conf.</th><th>Stock?</th><th>Reason</th></tr></thead>",
                    f"<tbody>{''.join(item_rows)}</tbody>",
                    "</table>",
                    "<div class=\"review-box\"><strong>Human review</strong><span>Confirm row boundaries, missing descriptions, zero-price components, and type classification.</span></div>",
                    "</section>",
                ]
            )
        )

    status_items = "".join(
        f"<div><span>{html.escape(_status_label(key))}</span><strong>{value}</strong></div>"
        for key, value in summary["status_counts"].items()
    )
    band_counts = summary.get("confidence_bands", {})
    type_counts = summary.get("line_type_counts", {})
    type_items = "".join(
        f"<span class=\"type-chip\">{html.escape(key)}: {value}</span>"
        for key, value in type_counts.items()
    )
    comparison = payload.get("baseline_comparison", {})
    if comparison.get("available"):
        comparison_markup = f"""
    <section class="panel compare">
      <div class="panel-head"><h2>V2 vs baseline</h2></div>
      <div class="summary mini">
        <div><span>Baseline reconciled</span><strong>{_pct(float(comparison.get('old_reconciled_rate', 0.0) or 0.0))}</strong></div>
        <div><span>V2 reconciled</span><strong>{_pct(float(comparison.get('new_reconciled_rate', 0.0) or 0.0))}</strong></div>
        <div><span>Reconciled delta</span><strong>{_pct(float(comparison.get('reconciled_rate_delta', 0.0) or 0.0))}</strong></div>
        <div><span>Row delta</span><strong>{comparison.get('row_delta', 0)}</strong></div>
        <div><span>Review delta</span><strong>{comparison.get('needs_review_delta', 0)}</strong></div>
      </div>
      <p class="path">Baseline: {html.escape(str(comparison.get('baseline_path', '')))}</p>
    </section>
"""
    else:
        comparison_markup = ""

    markup = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TASK-906 Line Item Folder Review</title>
  <style>
    :root {{
      --bg: #f6f7f3;
      --paper: #ffffff;
      --ink: #1f2520;
      --muted: #697068;
      --line: #dfe3d9;
      --ok: #24745a;
      --warn: #9a6a00;
      --bad: #b33a2f;
      --accent: #315f7d;
      --soft: #edf2ec;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Aptos", "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.45;
    }}
    header {{
      padding: 28px 32px 18px;
      background: #17211c;
      color: #f7fbf6;
      border-bottom: 4px solid #88a986;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    header p {{ margin: 4px 0; color: #d8e2d6; }}
    main {{ max-width: 1420px; margin: 0 auto; padding: 22px 24px 40px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .summary div, .metrics div {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
    }}
    .summary span, .metrics span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .summary strong, .metrics strong {{ font-size: 20px; }}
    .panel, .doc {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 16px;
      overflow: hidden;
    }}
    .panel h2, .doc h2 {{ margin: 0; font-size: 18px; }}
    .panel-head, .doc-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      padding: 14px 16px;
      background: var(--soft);
      border-bottom: 1px solid var(--line);
    }}
    .doc-head p {{ margin: 4px 0 0; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: top; }}
    th {{ text-align: left; color: #465047; font-size: 12px; background: #fafbf8; }}
    .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .net_reconciled, .gross_reconciled {{ color: var(--ok); background: #e7f3ed; }}
    .needs_review, .no_rows {{ color: var(--warn); background: #fff4d7; }}
    .error {{ color: var(--bad); background: #fde8e5; }}
    .conf-green td {{ background: #f0faf4; }}
    .conf-amber td {{ background: #fff8e5; }}
    .conf-red td {{ background: #fff0ee; }}
    .band {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .band.green {{ color: var(--ok); background: #dff3ea; }}
    .band.amber {{ color: var(--warn); background: #ffedbd; }}
    .band.red {{ color: var(--bad); background: #fbd8d4; }}
    .stock-yes {{ color: var(--ok); font-weight: 800; }}
    .stock-no {{ color: var(--muted); }}
    .type-chip {{
      display: inline-block;
      margin: 3px 5px 3px 0;
      padding: 3px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
    }}
    .score-breakdown {{
      display: block;
      margin-top: 4px;
      color: #6d756d;
      font-size: 11px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
      padding: 12px 16px;
    }}
    .path, .note, .warn {{ margin: 0; padding: 0 16px 8px; color: var(--muted); font-size: 13px; }}
    .warn {{ color: var(--bad); }}
    .line-table {{ margin-top: 4px; }}
    .empty {{ color: var(--muted); text-align: center; padding: 18px; }}
    .review-box {{
      display: flex;
      gap: 10px;
      align-items: baseline;
      padding: 12px 16px;
      background: #f9faf6;
      color: var(--muted);
      font-size: 13px;
    }}
    .review-box strong {{ color: var(--ink); }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media print {{
      header {{ position: static; }}
      main {{ max-width: none; padding: 12px; }}
      .doc {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TASK-906 Line Item Folder Review</h1>
    <p>Generated {generated} · Model {model} · max pages {payload['max_pages']}</p>
    <p>Selection: sample {html.escape(str(selection.get('sample')))} · seed {html.escape(str(selection.get('seed')))} · recursive {html.escape(str(selection.get('recursive')))} · max file MB {html.escape(str(selection.get('max_file_mb')))} · expectations {html.escape(str(selection.get('has_expectations')))}</p>
    <p>{folder}</p>
  </header>
  <main>
    <section class="summary">
      <div><span>Documents</span><strong>{summary['document_count']}</strong></div>
      <div><span>Reconciled</span><strong>{summary['reconciled_count']} ({_pct(summary['reconciled_rate'])})</strong></div>
      <div><span>Needs review</span><strong>{summary['needs_review_count']}</strong></div>
      <div><span>Rows extracted</span><strong>{summary['total_rows']}</strong></div>
      <div><span>Green rows</span><strong>{band_counts.get('green', 0)}</strong></div>
      <div><span>Amber rows</span><strong>{band_counts.get('amber', 0)}</strong></div>
      <div><span>Red rows</span><strong>{band_counts.get('red', 0)}</strong></div>
      <div><span>Stock candidates</span><strong>{summary.get('stock_candidate_count', 0)}</strong></div>
      <div><span>Total cost THB</span><strong>{summary['total_cost_thb']:.4f}</strong></div>
      <div><span>Avg seconds/doc</span><strong>{summary['avg_elapsed_sec']:.2f}</strong></div>
      {status_items}
    </section>
    {comparison_markup}
    <section class="panel">
      <div class="panel-head"><h2>Line type distribution</h2></div>
      <div style="padding: 12px 16px;">{type_items}</div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Document queue</h2></div>
      <table>
        <thead><tr><th>Doc</th><th>File</th><th>Status</th><th class="num">Rows</th><th class="num">Expected net</th><th class="num">Line sum</th><th class="num">Delta</th><th class="num">Sec</th><th class="num">Cost</th></tr></thead>
        <tbody>{''.join(doc_rows)}</tbody>
      </table>
    </section>
    {''.join(doc_sections)}
  </main>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(markup, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a line-item folder scan and render HTML")
    parser.add_argument("--folder", default=str(DEFAULT_FOLDER))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", default=str(DEFAULT_V2_RESULT_PATH))
    parser.add_argument("--html", default=str(DEFAULT_V2_HTML_PATH))
    parser.add_argument("--baseline", default=str(DEFAULT_RESULT_PATH))
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--seed", type=int, default=906)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-file-mb", type=float, default=None)
    parser.add_argument("--master-file", default="")
    parser.add_argument("--exclude-result", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    payload = run_folder_scan(
        folder=Path(args.folder),
        model=args.model,
        output=Path(args.output),
        max_pages=args.max_pages,
        limit=args.limit,
        sample=args.sample,
        seed=args.seed,
        recursive=args.recursive,
        max_file_mb=args.max_file_mb,
        master_file=Path(args.master_file) if args.master_file else None,
        exclude_result=Path(args.exclude_result) if args.exclude_result else None,
        force=args.force,
    )
    baseline_path = Path(args.baseline)
    if baseline_path.resolve() != Path(args.output).resolve():
        payload["baseline_comparison"] = _baseline_comparison(payload, baseline_path)
        write_json(Path(args.output), payload)
    render_html_report(payload, Path(args.html))
    print(f"OK: wrote {args.output}")
    print(f"OK: wrote {args.html}")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
