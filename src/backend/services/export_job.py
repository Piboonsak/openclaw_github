"""Export Job — fan-out 6 CSV files and package as ZIP for Express Accounting.

Orchestrates:
  1. Route documents to books (BookRouter)
  2. Render each book group via TemplateEngine
  3. Package all 6 CSV files + export_summary.json into a single ZIP

Always produces exactly 6 files, even if a book group is empty
(empty file = header row only, no data rows).

Task: TASK-1011
Spec: docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md#task-1011
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from typing import Optional

from .book_router import BookAssignment, BookRouter, UnroutedDocumentError

# ---------------------------------------------------------------------------
# Express Accounting expected filenames (must match exactly — client-defined)
# ---------------------------------------------------------------------------

BOOK_FILENAMES: dict[str, str] = {
    "12":  "12 ซื้อสด บรรทัดเดียว.csv",
    "14":  "14 ซื้อเชื่อ บรรทัดเดียว.csv",
    "15":  "15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv",
    "15W": "15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv",
    "22":  "22 ขายสด บรรทัดเดียว.csv",
    "24":  "24 ขายเชื่อ บรรทัดเดียว.csv",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileSummary:
    filename: str
    rows: int
    documents: int


@dataclass
class ExportSummary:
    export_date: str
    company: str
    period: str                          # "2569-05" (Thai year-month)
    files: list[FileSummary] = field(default_factory=list)
    unrouted_documents: list[str] = field(default_factory=list)   # doc IDs
    total_documents: int = 0


# ---------------------------------------------------------------------------
# ExportJob
# ---------------------------------------------------------------------------

class ExportJob:
    """Generate all 6 Express CSV files for a given company + period.

    Usage::
        job = ExportJob(router=BookRouter(), engine=template_engine)
        zip_bytes = job.run(
            company_id="comp_001",
            documents=[...],
            period="2569-05",
            company_name="GL เมโทร อีเล็กทริค",
        )
    """

    def __init__(
        self,
        router: Optional[BookRouter] = None,
        engine=None,       # TemplateEngine instance (TASK-1001) — injected
    ) -> None:
        self._router = router or BookRouter()
        self._engine = engine   # None until TASK-1001 is implemented

    def run(
        self,
        company_id: str,
        documents: list[dict],
        period: str,
        company_name: str = "",
        export_date: str = "",
    ) -> bytes:
        """Build the 6-file ZIP and return raw bytes for download.

        Raises nothing for unrouted documents — they are logged in the
        ExportSummary and skipped silently.
        """
        # Step 1: Route all documents to books
        groups: dict[str, list[dict]] = {book_id: [] for book_id in BOOK_FILENAMES}
        unrouted: list[str] = []

        for doc in documents:
            try:
                assignment: BookAssignment = self._router.route(doc)
                groups[assignment.book_id].append(doc)
            except UnroutedDocumentError:
                unrouted.append(str(doc.get("id", "unknown")))

        # Step 2: Render each group → CSV bytes
        csv_files: dict[str, bytes] = {}
        file_summaries: list[FileSummary] = []

        for book_id, filename in BOOK_FILENAMES.items():
            book_docs = groups.get(book_id, [])
            csv_bytes = self._render_group(book_id, book_docs)
            csv_files[filename] = csv_bytes
            # Row count: number of \n in output minus 1 (header) — rough estimate
            rows = max(0, csv_bytes.count(b"\n") - 1) if csv_bytes else 0
            file_summaries.append(FileSummary(
                filename=filename,
                rows=rows,
                documents=len(book_docs),
            ))

        # Step 3: Build export_summary.json
        summary = ExportSummary(
            export_date=export_date,
            company=company_name,
            period=period,
            files=file_summaries,
            unrouted_documents=unrouted,
            total_documents=len(documents) - len(unrouted),
        )
        summary_json = json.dumps(
            {
                "export_date": summary.export_date,
                "company": summary.company,
                "period": summary.period,
                "files": [
                    {"filename": f.filename, "rows": f.rows, "documents": f.documents}
                    for f in summary.files
                ],
                "unrouted_documents": summary.unrouted_documents,
                "total_documents": summary.total_documents,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        # Step 4: Pack into ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, csv_bytes in csv_files.items():
                zf.writestr(filename, csv_bytes)
            zf.writestr("export_summary.json", summary_json)
        return buf.getvalue()

    def _render_group(self, book_id: str, docs: list[dict]) -> bytes:
        """Render a book group to CSV bytes.

        Returns header-only CSV when docs is empty (Express expects all 6 files).
        Full rendering delegated to TemplateEngine (TASK-1001) — stub for now.
        """
        # TODO: integrate with TemplateEngine once TASK-1001 is complete
        # For now: return empty placeholder with TIS-620 encoding note
        if not docs:
            # Header-only file — actual headers come from template definition
            return b""   # TODO: fetch header row from template
        raise NotImplementedError(
            f"ExportJob._render_group not yet connected to TemplateEngine (book_id={book_id}). "
            "Complete TASK-1001 first, then wire up here."
        )
