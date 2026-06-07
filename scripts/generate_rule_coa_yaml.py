"""Generate COA journal mapping YAML from COA PDF + mapping DOCX via the D6 service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.backend.services.secrets_loader import load_llm_keys
from src.backend.services.rule_generator import generate_rule_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate COA mapping rule YAML from PDF + DOCX"
    )
    parser.add_argument("--coa-pdf", required=True, type=Path)
    parser.add_argument("--mapping-docx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--company-id", default="comp_1_ritlerlert")
    parser.add_argument("--company-name", default="บริษัท ฤทธิ์ล้ำเลิศ จำกัด")
    parser.add_argument("--business-type", default="service")
    parser.add_argument(
        "--provider", choices=["anthropic", "openai"], default="anthropic"
    )
    parser.add_argument("--model", default="claude-sonnet-4-6-20250601")
    return parser.parse_args()


def main() -> int:
    load_llm_keys()
    args = parse_args()
    try:
        result = generate_rule_package(
            company_id=args.company_id,
            provider=args.provider,
            model=args.model,
            company_name=args.company_name,
            business_type=args.business_type,
            coa_pdf_path=args.coa_pdf,
            mapping_docx_path=args.mapping_docx,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result["yaml_content"], encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Generated: {args.output}")
    print(f"Canonical: {result['output_path']}")
    print(f"Confidence: {result['confidence_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
