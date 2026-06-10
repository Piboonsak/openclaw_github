"""Arithmetic reconciliation for accounting amount fields.

Anchors on the VAT value seen on the document, classifies the document layout
(VAT-exclusive "บวก VAT" vs VAT-inclusive "ถอด VAT"), and enforces the invariant
``Net + VAT = Gross``. The result feeds confidence calibration: a document may only
earn high confidence when its money fields reconcile arithmetically.

Key relationships (Thai pre-accounting):
- Exclusive (บวก VAT):  vat = net * rate% ;            gross = net + vat
- Inclusive (ถอด VAT):  vat = gross * rate/(100+rate) ; net = gross - vat
- WHT:                   wht = net * wht_rate%   (computed on the pre-VAT base)
- Amount paid:           amount_paid = gross - wht   (= net + vat - wht)

This module is pure: string fields in, plain dict out. No I/O, no external deps.
"""

from __future__ import annotations

from typing import Any

DEFAULT_VAT_RATE = 7.0

# Tolerance: absolute floor (rounding) blended with a small relative band.
_ABS_TOLERANCE = 1.0
_REL_TOLERANCE = 0.005  # 0.5%


def _to_float(value: Any) -> float | None:
    """Parse a possibly comma-formatted amount string into a float."""
    text = str(value if value is not None else "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _tolerance(base: float) -> float:
    return max(_ABS_TOLERANCE, abs(base) * _REL_TOLERANCE)


def _close(a: float | None, b: float | None, base: float | None = None) -> bool:
    if a is None or b is None:
        return False
    ref = base if base is not None else max(abs(a), abs(b))
    return abs(a - b) <= _tolerance(ref)


def _expected_exclusive_vat(amount: float, rate: float) -> float:
    return round(amount * rate / 100.0, 2)


def _expected_inclusive_vat(amount: float, rate: float) -> float:
    return round(amount * rate / (100.0 + rate), 2)


def _formula_close(actual: float, expected: float) -> bool:
    # Formula disambiguation needs tighter tolerance than generic amount checks;
    # otherwise both inclusive and exclusive can pass for the same value.
    tolerance = max(0.5, abs(expected) * 0.02)
    return abs(actual - expected) <= tolerance


def _vat_fits_exclusive(amount: float | None, vat: float | None, rate: float) -> bool:
    if amount is None or vat is None:
        return False
    expected = _expected_exclusive_vat(amount, rate)
    return _formula_close(vat, expected)


def _vat_fits_inclusive(amount: float | None, vat: float | None, rate: float) -> bool:
    if amount is None or vat is None:
        return False
    expected = _expected_inclusive_vat(amount, rate)
    return _formula_close(vat, expected)


def classify_vat_layout(
    net: float | None,
    vat: float | None,
    total: float | None,
    rate: float = DEFAULT_VAT_RATE,
) -> tuple[str, dict[str, float | None]]:
    """Classify the document VAT layout and return canonical net/vat/gross.

    The document VAT value (``vat``) is treated as the anchor and is never
    overwritten by a recomputed value. Missing components are derived so that
    ``net + vat == gross`` holds.

    Returns ``(layout, {"net", "vat", "gross"})`` where ``layout`` is one of
    ``"exclusive"``, ``"inclusive"`` or ``"unknown"``.
    """
    if rate <= 0:
        rate = DEFAULT_VAT_RATE

    # VAT + subtotal: choose arithmetic match first, then slot fallback.
    if vat is not None and net is not None:
        net_matches_exclusive = _vat_fits_exclusive(net, vat, rate)
        net_matches_inclusive = _vat_fits_inclusive(net, vat, rate)
        if net_matches_exclusive and not net_matches_inclusive:
            return "exclusive", {"net": net, "vat": vat, "gross": round(net + vat, 2)}
        if net_matches_inclusive and not net_matches_exclusive:
            return "inclusive", {
                "net": round(net - vat, 2),
                "vat": vat,
                "gross": net,
            }
        return "exclusive", {"net": net, "vat": vat, "gross": round(net + vat, 2)}

    # VAT + total: choose arithmetic match first, then slot fallback.
    if vat is not None and total is not None:
        total_matches_exclusive = _vat_fits_exclusive(total, vat, rate)
        total_matches_inclusive = _vat_fits_inclusive(total, vat, rate)
        if total_matches_exclusive and not total_matches_inclusive:
            # total is actually net (common mis-slot); rebuild gross from formula.
            return "exclusive", {
                "net": total,
                "vat": vat,
                "gross": round(total + vat, 2),
            }
        if total_matches_inclusive and not total_matches_exclusive:
            return "inclusive", {
                "net": round(total - vat, 2),
                "vat": vat,
                "gross": total,
            }
        return "inclusive", {
            "net": round(total - vat, 2),
            "vat": vat,
            "gross": total,
        }

    # No VAT line, but net + total -> VAT is the difference.
    if net is not None and total is not None:
        if total >= net:
            diff = round(total - net, 2)
            return "exclusive", {"net": net, "vat": max(diff, 0.0), "gross": total}
        # Swap mis-slotted values when gross/net are reversed in extraction.
        diff = round(net - total, 2)
        return "exclusive", {"net": total, "vat": max(diff, 0.0), "gross": net}

    # Only grand total -> assume inclusive (Thai grand totals usually include VAT).
    if total is not None:
        derived_vat = round(total * rate / (100.0 + rate), 2)
        return "inclusive", {
            "net": round(total - derived_vat, 2),
            "vat": derived_vat,
            "gross": total,
        }

    # Only subtotal -> assume exclusive.
    if net is not None:
        derived_vat = round(net * rate / 100.0, 2)
        return "exclusive", {
            "net": net,
            "vat": derived_vat,
            "gross": round(net + derived_vat, 2),
        }

    # Only VAT or nothing.
    return "unknown", {"net": net, "vat": vat, "gross": total}


def reconcile_amounts(
    fields: dict[str, Any], rate: float | None = None
) -> dict[str, Any]:
    """Validate the internal arithmetic of accounting amount fields.

    Returns a dict with per-relationship check status, a doc-level ``reconciled``
    flag, the canonical derived ``net/vat/gross``, mismatch descriptions, a
    ``total_is_paid`` flag (printed total is actually the post-WHT paid amount),
    and suggested ``corrected`` field values.
    """
    if rate is None:
        rate = _to_float(fields.get("vat_rate")) or DEFAULT_VAT_RATE
    if rate <= 0:
        rate = DEFAULT_VAT_RATE

    net = _to_float(fields.get("net_amount"))
    vat = _to_float(fields.get("vat_amount"))
    total = _to_float(fields.get("total_amount")) or _to_float(
        fields.get("gross_amount")
    )
    wht = _to_float(fields.get("wht_amount"))
    wht_rate = _to_float(fields.get("wht_rate"))
    paid = _to_float(fields.get("amount_paid"))

    layout, derived = classify_vat_layout(net, vat, total, rate)
    d_net = derived.get("net")
    d_gross = derived.get("gross")

    checks: dict[str, str] = {}
    mismatches: list[str] = []

    # --- Total relationship: net + vat == gross ---
    if net is not None and vat is not None and total is not None:
        if _close(net + vat, total, total):
            checks["total"] = "ok"
        else:
            checks["total"] = "fail"
            mismatches.append(
                f"net({net}) + vat({vat}) = {round(net + vat, 2)} != total({total})"
            )
    else:
        checks["total"] = "na"

    # --- VAT relationship: anchor on document VAT, accept either layout ---
    if vat is not None and (net is not None or total is not None):
        ok = False
        expected: float | None = None
        if net is not None:
            expected = round(net * rate / 100.0, 2)
            if _close(vat, expected, max(net, vat)):
                ok = True
        if not ok and total is not None:
            expected_incl = round(total * rate / (100.0 + rate), 2)
            if _close(vat, expected_incl, max(total, vat)):
                ok = True
            if expected is None:
                expected = expected_incl
        checks["vat"] = "ok" if ok else "fail"
        if not ok and expected is not None:
            mismatches.append(f"vat({vat}) != expected({expected})")
    else:
        checks["vat"] = "na"

    # --- WHT relationship: strict wht == base * wht_rate% (try net and gross base) ---
    if wht is not None and wht > 0:
        if wht_rate and wht_rate > 0:
            base_net = net if net is not None else d_net
            base_gross = total if total is not None else d_gross
            ok = False
            for base in (base_net, base_gross):
                if base and _close(wht, base * wht_rate / 100.0, max(base, wht)):
                    ok = True
                    break
            checks["wht"] = "ok" if ok else "fail"
            if not ok and base_net:
                mismatches.append(
                    f"wht({wht}) != net*rate({round(base_net * wht_rate / 100.0, 2)})"
                )
        else:
            # Cannot verify without a rate; treat as not-applicable rather than fail.
            checks["wht"] = "na"
    else:
        checks["wht"] = "na"

    # --- Amount paid relationship: paid == gross - wht ---
    if paid is not None and paid > 0 and total is not None:
        w = wht or 0.0
        if _close(paid, total - w, total):
            checks["paid"] = "ok"
        else:
            checks["paid"] = "fail"
            mismatches.append(f"paid({paid}) != total-wht({round(total - w, 2)})")
    else:
        checks["paid"] = "na"

    # --- Detect "total is actually the post-WHT paid amount" ---
    total_is_paid = False
    if (
        net is not None
        and vat is not None
        and wht is not None
        and wht > 0
        and total is not None
    ):
        if _close(total, net + vat - wht, total) and not _close(
            net + vat, total, total
        ):
            total_is_paid = True

    # --- Suggested corrections (Q2: auto-correct gross when total is paid) ---
    corrected: dict[str, str] = {}
    if total_is_paid and net is not None and vat is not None:
        corrected_gross = round(net + vat, 2)
        corrected["total_amount"] = f"{corrected_gross:.2f}"
        corrected["amount_paid"] = f"{round(net + vat - (wht or 0.0), 2):.2f}"

    # The doc-level `reconciled` gate governs the green band. It considers the
    # core money relationships (vat, total, wht) only. The `paid` check is
    # informational: amount_paid is the weakest/most-optional field and a misread
    # there must not block an otherwise-correct extraction.
    core_checks = {k: v for k, v in checks.items() if k != "paid"}
    reconciled = all(status != "fail" for status in core_checks.values()) and any(
        status == "ok" for status in core_checks.values()
    )

    return {
        "rate": rate,
        "layout": layout,
        "reconciled": reconciled,
        "checks": checks,
        "mismatches": mismatches,
        "derived": derived,
        "total_is_paid": total_is_paid,
        "corrected": corrected,
    }


# Fields whose confidence is governed by amount reconciliation.
_AMOUNT_FIELDS = ("net_amount", "vat_amount", "total_amount", "wht_amount")


def apply_amount_confidence(
    fields: dict[str, Any],
    confidence: dict[str, Any],
    reconciliation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Penalize amount-field confidence when reconciliation fails.

    Mutates and returns ``confidence``. A failing relationship caps the involved
    fields below the trust threshold so a wrong-but-confident value cannot earn a
    green band.
    """
    if reconciliation is None:
        reconciliation = reconcile_amounts(fields)

    checks = reconciliation.get("checks", {})

    def _cap(field_name: str, ceiling: float) -> None:
        current = confidence.get(field_name)
        if isinstance(current, (int, float)):
            confidence[field_name] = min(float(current), ceiling)

    if checks.get("total") == "fail":
        for name in ("net_amount", "vat_amount", "total_amount"):
            _cap(name, 0.45)
    if checks.get("vat") == "fail":
        _cap("vat_amount", 0.40)
        _cap("total_amount", 0.55)
    if checks.get("wht") == "fail":
        _cap("wht_amount", 0.40)
    if reconciliation.get("total_is_paid"):
        _cap("total_amount", 0.55)

    return confidence
