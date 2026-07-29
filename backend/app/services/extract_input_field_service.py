import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber
from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph


FIELD_ALIASES = {
    "factory_name": ["nama pabrik"],
    "process_type": ["jenis proses"],
    "layout_description": ["deskripsi pabrik"],
    "worker_count": ["jumlah pekerja", "jumlah tenaga kerja"],
}

STOP_LABEL_PATTERNS = [
    r"^catatan\s+metodologi",
    r"^sumber\s+data",
    r"^disusun\s+ulang",
    r"^tabel\s*\d",
    r"^table\s*\d",
]

CAPTION_PATTERN = re.compile(r"\b(?:TABEL|TABLE)\s*(\d+)", re.IGNORECASE)

BULLET_CHARS = ("●", "•", "◦", "▪")

HEADER_CANONICAL = {
    "tahapproses": "Tahap Proses",
    "peralatan": "Peralatan",
    "deskripsitugasoperator": "Deskripsi Tugas Operator",
    "otomatisasi": "Otomatisasi",
    "qualitycontrol(qc)": "Quality Control (QC)",
    "qualitycontrolqc": "Quality Control (QC)",
    "throughput(estimasi)": "Throughput (estimasi)",
    "throughputestimasi": "Throughput (estimasi)",
    "jumlahpekerja": "Jumlah Pekerja",
    "pekerjaditugaskan": "Pekerja Ditugaskan",
    "keteranganpenugasan": "Keterangan Penugasan",
    "jumlahunit": "Jumlah Unit",
    "kapasitasperunit": "Kapasitas per Unit",
    "totalkapasitastahap": "Total Kapasitas Tahap",
}

TABLE_LABELS = {
    1: "TABEL 1 (tahap proses, peralatan, deskripsi tugas operator, otomatisasi, QC)",
    2: "TABEL 2 (tahap proses, jumlah pekerja, pekerja ditugaskan)",
    3: "TABEL 3 (tahap proses, peralatan, jumlah unit)",
}

TABLE_FALLBACK_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}


class UnsupportedDocumentError(ValueError):
    pass


@dataclass
class RawTable:
    caption_number: int | None
    headers: list[str]
    rows: list[list[str]]
    order: int


@dataclass
class ExtractedTable:
    index: int
    headers: list[str]
    rows: list[list[str]]

    def to_markdown(self) -> str:
        frame = pd.DataFrame(self.rows, columns=self.headers)
        return frame.to_markdown(index=False)


@dataclass
class ExtractedDocument:
    source_name: str
    text_fields: dict[str, str] = field(default_factory=dict)
    tables: list[ExtractedTable] = field(default_factory=list)
    raw_text: str = ""

    def missing_text_fields(self) -> list[str]:
        missing = []
        for key in FIELD_ALIASES:
            if not self.text_fields.get(key):
                missing.append(key)
        return missing

    def table_by_index(self, index: int) -> ExtractedTable | None:
        for table in self.tables:
            if table.index == index:
                return table
        return None

    def missing_tables(self) -> list[int]:
        present = set()
        for table in self.tables:
            present.add(table.index)

        missing = []
        for expected in (1, 2, 3):
            if expected not in present:
                missing.append(expected)
        return missing


def _normalize_key(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[\s\u00a0]+", "", lowered)


def _clean_cell(cell) -> str:
    if cell is None:
        return ""
    if not isinstance(cell, str):
        cell = str(cell)

    collapsed = re.sub(r"[\s\u00a0]+", " ", cell)
    return collapsed.strip()


def _canonical_header(raw: str, position: int) -> str:
    cleaned = _clean_cell(raw)
    if not cleaned:
        return f"kolom_{position}"

    canonical = HEADER_CANONICAL.get(_normalize_key(cleaned))
    if canonical:
        return canonical

    return cleaned


def _is_bullet_row(row: list[str]) -> bool:
    filled = []
    for cell in row:
        if cell:
            filled.append(cell)

    if len(filled) != 1:
        return False

    return filled[0].startswith(BULLET_CHARS)


def _is_repeated_header(row: list[str], headers: list[str]) -> bool:
    if len(row) != len(headers):
        return False

    matches = 0
    for cell, header in zip(row, headers):
        if not cell:
            continue
        if _normalize_key(cell) == _normalize_key(header):
            matches += 1

    return matches >= max(2, len(headers) // 2)


def _build_raw_table(caption_number: int | None, order: int, raw_rows: list[list]) -> RawTable | None:
    cleaned_rows = []
    for row in raw_rows:
        cleaned_row = []
        for cell in row:
            cleaned_row.append(_clean_cell(cell))
        cleaned_rows.append(cleaned_row)

    non_empty_rows = []
    for row in cleaned_rows:
        has_content = False
        for cell in row:
            if cell:
                has_content = True
                break
        if has_content:
            non_empty_rows.append(row)

    if len(non_empty_rows) < 2:
        return None

    header_row = non_empty_rows[0]
    body_rows = non_empty_rows[1:]

    headers = []
    for position, name in enumerate(header_row):
        headers.append(_canonical_header(name, position))

    width = len(headers)
    normalized_rows = []
    for row in body_rows:
        if _is_bullet_row(row):
            continue
        if _is_repeated_header(row, headers):
            continue

        if len(row) < width:
            row = row + [""] * (width - len(row))
        normalized_rows.append(row[:width])

    return RawTable(
        caption_number=caption_number,
        headers=headers,
        rows=normalized_rows,
        order=order,
    )


def _find_caption_number(text: str) -> int | None:
    matches = CAPTION_PATTERN.findall(text or "")
    if not matches:
        return None
    return int(matches[-1])


def _extract_pdf(path: Path) -> tuple[str, list[RawTable]]:
    text_chunks = []
    raw_tables = []
    order = 0

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            found = page.find_tables()
            if not found:
                found = page.find_tables(table_settings=TABLE_FALLBACK_SETTINGS)

            found = sorted(found, key=lambda item: item.bbox[1])

            previous_bottom = 0.0
            for table in found:
                top = table.bbox[1]
                if top > previous_bottom:
                    region = page.crop((0, previous_bottom, page.width, top))
                    caption_text = region.extract_text()
                else:
                    caption_text = ""

                order += 1
                parsed = _build_raw_table(
                    caption_number=_find_caption_number(caption_text),
                    order=order,
                    raw_rows=table.extract(),
                )
                if parsed is not None:
                    raw_tables.append(parsed)

                previous_bottom = table.bbox[3]

            text_area = page
            for table in found:
                text_area = text_area.outside_bbox(table.bbox)

            page_text = text_area.extract_text()
            if page_text:
                text_chunks.append(page_text)

    return "\n".join(text_chunks), raw_tables


def _iter_docx_blocks(document: DocxDocument):
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            yield DocxParagraph(child, document)
        elif tag == "tbl":
            yield DocxTable(child, document)


def _extract_docx(path: Path) -> tuple[str, list[RawTable]]:
    document = DocxDocument(path)

    text_chunks = []
    raw_tables = []
    order = 0
    pending_caption = None

    for block in _iter_docx_blocks(document):
        if isinstance(block, DocxParagraph):
            stripped = block.text.strip()
            if not stripped:
                continue

            caption = _find_caption_number(stripped)
            if caption is not None:
                pending_caption = caption

            text_chunks.append(stripped)
            continue

        raw_rows = []
        for row in block.rows:
            raw_row = []
            for cell in row.cells:
                raw_row.append(cell.text)
            raw_rows.append(raw_row)

        order += 1
        parsed = _build_raw_table(
            caption_number=pending_caption,
            order=order,
            raw_rows=raw_rows,
        )
        if parsed is not None:
            raw_tables.append(parsed)

        pending_caption = None

    return "\n".join(text_chunks), raw_tables


def _extract_markdown(path: Path) -> tuple[str, list[RawTable]]:
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    text_lines = []
    raw_tables = []
    buffer = []
    order = 0
    pending_caption = None

    def flush_buffer():
        nonlocal order, buffer, pending_caption

        if len(buffer) < 2:
            text_lines.extend(buffer)
            buffer = []
            return

        parsed_rows = []
        for line in buffer:
            if re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", line):
                continue
            trimmed = line.strip().strip("|")
            parsed_rows.append(trimmed.split("|"))

        order += 1
        parsed = _build_raw_table(
            caption_number=pending_caption,
            order=order,
            raw_rows=parsed_rows,
        )
        if parsed is not None:
            raw_tables.append(parsed)

        pending_caption = None
        buffer = []

    for line in lines:
        if "|" in line:
            buffer.append(line)
            continue

        if buffer:
            flush_buffer()

        caption = _find_caption_number(line)
        if caption is not None:
            pending_caption = caption

        text_lines.append(line)

    if buffer:
        flush_buffer()

    return "\n".join(text_lines), raw_tables


DOCUMENT_EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".md": _extract_markdown,
    ".markdown": _extract_markdown,
    ".txt": _extract_markdown,
}


def _match_field_label(line: str) -> tuple[str, str] | None:
    stripped = line.strip().lstrip("#").strip()
    stripped = stripped.replace("**", "").replace("__", "")

    if not stripped:
        return None

    for key, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            pattern = rf"^{alias}\s*[:：\-–—]?\s*(.*)$"
            match = re.match(pattern, stripped, re.IGNORECASE)
            if match:
                return key, match.group(1).strip()

    return None


def _is_stop_line(line: str) -> bool:
    stripped = line.strip().lower()
    for pattern in STOP_LABEL_PATTERNS:
        if re.match(pattern, stripped):
            return True
    return False


def _parse_text_fields(raw_text: str) -> dict[str, str]:
    results = {}
    active_key = None
    buffer = []

    def flush_active():
        nonlocal active_key, buffer

        if active_key is not None:
            joined = " ".join(buffer).strip()
            if joined and not results.get(active_key):
                results[active_key] = joined

        active_key = None
        buffer = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        matched = _match_field_label(stripped)
        if matched is not None:
            flush_active()
            active_key = matched[0]
            if matched[1]:
                buffer.append(matched[1])
            continue

        if _is_stop_line(stripped):
            flush_active()
            continue

        if active_key is not None:
            buffer.append(stripped)

    flush_active()
    return results


def _harvest_metadata_table(table: RawTable) -> dict[str, str]:
    harvested = {}

    candidate_rows = [table.headers] + table.rows
    for row in candidate_rows:
        if len(row) < 2:
            continue

        matched = _match_field_label(row[0])
        if matched is None:
            continue

        value_parts = []
        for cell in row[1:]:
            if cell:
                value_parts.append(cell)

        joined = " ".join(value_parts).strip()
        if joined:
            harvested[matched[0]] = joined

    return harvested


def _resolve_tables(raw_tables: list[RawTable]) -> tuple[list[ExtractedTable], dict[str, str]]:
    harvested_fields = {}
    numbered = {}
    last_number = None

    for table in sorted(raw_tables, key=lambda item: item.order):
        if table.caption_number is None:
            metadata = _harvest_metadata_table(table)
            if metadata:
                harvested_fields.update(metadata)
                continue

            if last_number is not None and last_number in numbered:
                numbered[last_number].rows.extend(table.rows)
            continue

        number = table.caption_number
        last_number = number

        if number in numbered:
            numbered[number].rows.extend(table.rows)
            continue

        numbered[number] = ExtractedTable(
            index=number,
            headers=table.headers,
            rows=table.rows,
        )

    ordered = []
    for number in sorted(numbered.keys()):
        ordered.append(numbered[number])

    return ordered, harvested_fields


def _normalize_process_type(value: str) -> str:
    lowered = value.lower()
    if "paralel" in lowered or "parallel" in lowered:
        return "parallel"
    if "serial" in lowered or "sekuensial" in lowered or "sequential" in lowered:
        return "serial"
    return value.strip()


def _normalize_worker_count(value: str) -> str:
    digits = re.search(r"\d+", value.replace(".", ""))
    if digits:
        return digits.group(0)
    return value.strip()


def extract_document(path: str | Path) -> ExtractedDocument:
    resolved = Path(path)
    suffix = resolved.suffix.lower()

    extractor = DOCUMENT_EXTRACTORS.get(suffix)
    if extractor is None:
        raise UnsupportedDocumentError(
            f"Format dokumen tidak didukung: '{suffix}'. "
            f"Didukung: {sorted(DOCUMENT_EXTRACTORS.keys())}"
        )

    raw_text, raw_tables = extractor(resolved)
    tables, harvested_fields = _resolve_tables(raw_tables)

    text_fields = _parse_text_fields(raw_text)

    for key, value in harvested_fields.items():
        if not text_fields.get(key):
            text_fields[key] = value

    if text_fields.get("process_type"):
        text_fields["process_type"] = _normalize_process_type(text_fields["process_type"])

    if text_fields.get("worker_count"):
        text_fields["worker_count"] = _normalize_worker_count(text_fields["worker_count"])

    return ExtractedDocument(
        source_name=resolved.name,
        text_fields=text_fields,
        tables=tables,
        raw_text=raw_text,
    )


def build_agent_input(document: ExtractedDocument) -> str:
    fields = document.text_fields
    blocks = [
        f"Nama pabrik: {fields.get('factory_name', '')}",
        f"Jenis proses: {fields.get('process_type', '')}",
        f"Deskripsi pabrik: {fields.get('layout_description', '')}",
        f"Jumlah pekerja: {fields.get('worker_count', '')}",
    ]

    for table in document.tables:
        label = TABLE_LABELS.get(table.index, f"TABEL {table.index}")
        blocks.append(f"\n{label}\n{table.to_markdown()}")

    return "\n".join(blocks)