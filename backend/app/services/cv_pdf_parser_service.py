from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional, Sequence

from .extract_input_field_service import (
    DOCUMENT_EXTRACTORS,
    RawTable,
    TextLine,
    UnsupportedDocumentError,
    clean_cell,
    normalize,
)


WORKER_FIELD_ALIASES = {
    "name": ["nama lengkap", "nama pekerja", "nama kandidat", "full name", "nama", "name"],
    "age": ["usia", "umur", "age"],
    "birth_date": ["tempat tanggal lahir", "tanggal lahir", "date of birth", "ttl", "dob"],
    "gender": ["jenis kelamin", "gender", "sex"],
    "years_of_experience": ["total pengalaman kerja", "lama pengalaman", "masa kerja",
                            "years of experience", "total experience", "pengalaman kerja total"],
    "current_position": ["posisi saat ini", "jabatan saat ini", "posisi", "jabatan",
                         "current position", "position", "role"],
    "hours_worked_today": ["jam kerja hari ini", "jam kerja hari berjalan", "hours worked today",
                           "jam kerja"],
    "consecutive_shifts": ["shift berturut turut", "shift beruntun", "shift berurutan",
                           "consecutive shifts", "jumlah shift berturut"],
    "shift_pattern": ["pola shift", "jadwal shift", "shift pattern", "shift schedule"],
}

SECTION_ALIASES = {
    "work_history": ["riwayat pekerjaan", "pengalaman kerja", "riwayat kerja", "riwayat jabatan",
                     "professional experience", "relevant experience", "work experience",
                     "employment history", "work history", "experience", "pengalaman"],
    "education": ["riwayat pendidikan", "academic background", "pendidikan", "education"],
    "skills": ["areas of expertise", "core competencies", "technical skills", "keterampilan",
               "kompetensi", "key skills", "keahlian", "skills"],
    "certifications": ["licenses and certification", "sertifikasi", "certification", "pelatihan",
                       "sertifikat", "training"],
    "health_notes": ["riwayat kesehatan", "catatan kesehatan", "kondisi kesehatan", "health notes"],
    "interview_notes": ["ringkasan wawancara", "catatan wawancara", "hasil wawancara",
                        "interview notes", "wawancara"],
    "summary": ["professional summary", "career objective", "career summary", "ringkasan profil",
                "profil singkat", "tentang saya", "about me", "objective", "ringkasan",
                "summary", "profile"],
}

REQUIRED_FIELDS = [
    "name",
    "age",
    "gender",
    "years_of_experience",
    "hours_worked_today",
    "consecutive_shifts",
]

FIELD_LABELS = {
    "name": "Nama",
    "age": "Usia",
    "gender": "Jenis kelamin",
    "years_of_experience": "Total pengalaman kerja (tahun)",
    "hours_worked_today": "Jam kerja hari ini",
    "consecutive_shifts": "Shift berturut-turut",
    "current_position": "Posisi saat ini",
    "shift_pattern": "Pola shift",
}

SECTION_LABELS = {
    "summary": "RINGKASAN PROFIL",
    "work_history": "RIWAYAT PEKERJAAN",
    "education": "PENDIDIKAN",
    "skills": "KEAHLIAN",
    "certifications": "SERTIFIKASI DAN PELATIHAN",
    "health_notes": "CATATAN KESEHATAN",
    "interview_notes": "CATATAN WAWANCARA",
}

GENDER_MALE = {"male", "laki laki", "laki", "pria", "l", "m", "man"}
GENDER_FEMALE = {"female", "perempuan", "wanita", "p", "f", "woman"}

CANDIDATE_HEADING = re.compile(
    r"^\W*(kandidat|pekerja|karyawan|candidate|worker|pelamar|operator)\s*[#\-]?\s*(\d+)\b",
    re.IGNORECASE)

YEAR_RANGE = re.compile(
    r"((?:19|20)\d{2})\s*(?:-|\u2013|\u2014|s\.?d\.?|sampai|hingga|to|until)\s*"
    r"(?:[A-Za-z]{3,9}\.?\s+)?"
    r"((?:19|20)\d{2}|sekarang|saat ini|kini|present|now|current)",
    re.IGNORECASE)

DURATION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(tahun|thn|years?|yrs?)", re.IGNORECASE)

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

YEAR = re.compile(r"(19|20)\d{2}")

MAX_NAME_WORDS = 6
MAX_NAME_LENGTH = 60

MIN_EVIDENCE_SCORE = 2

NON_CV_STEMS = {"readme", "read me", "notes", "catatan", "index", "license", "lisensi",
                "changelog", "manifest", "daftar isi", "petunjuk", "instructions"}

BULLET_PREFIX = re.compile(r"^\s*(?:[-\u2013\u2014*\u2022\u00b7\u25cf\u25aa]|\d{1,2}[.)])\s*")

INLINE_LIST_SPLIT = re.compile(r"\s*(?:[;|\u2022\u00b7]|,(?!\d))\s*")

SKILL_MIN_LENGTH = 2
SKILL_MAX_LENGTH = 80
SKILL_MAX_ITEMS = 24

LIST_SECTIONS = ("skills", "certifications")

@dataclass
class ExtractedCandidate:
    index: int
    worker_id: str
    source_name: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)
    section_items: dict[str, list[str]] = field(default_factory=dict)
    derived: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def missing_fields(self) -> list[str]:
        return [name for name in REQUIRED_FIELDS if self.derived.get(name) in (None, "")]

    def is_complete(self) -> bool:
        return not self.missing_fields()


@dataclass
class ExtractedWorkerDocument:
    source_names: list[str] = field(default_factory=list)
    candidates: list[ExtractedCandidate] = field(default_factory=list)
    rejected_blocks: list[dict[str, str]] = field(default_factory=list)
    raw_text: str = ""

    def missing_fields(self) -> dict[str, list[str]]:
        return {candidate.worker_id: candidate.missing_fields()
                for candidate in self.candidates if candidate.missing_fields()}

    def is_complete(self) -> bool:
        return bool(self.candidates) and not self.missing_fields()


def _label_patterns(mapping: dict[str, list[str]]) -> list[tuple[str, int, re.Pattern[str]]]:
    patterns = []
    for key, aliases in mapping.items():
        for alias in sorted(aliases, key=len, reverse=True):
            body = r"\W+".join(re.escape(token) for token in alias.split())
            patterns.append((
                key,
                len(alias),
                re.compile(r"^\W*%s\s*[:\uff1a\u2013\u2014\-]?\s*(.*)$" % body, re.IGNORECASE),
            ))
    patterns.sort(key=lambda item: -item[1])
    return patterns


def _heading_patterns(mapping: dict[str, list[str]]) -> list[tuple[str, int, re.Pattern[str]]]:
    patterns = []
    for key, aliases in mapping.items():
        for alias in sorted(aliases, key=len, reverse=True):
            body = r"\W+".join(re.escape(token) for token in alias.split())
            patterns.append((
                key,
                len(alias),
                re.compile(r"^\W*%ss?\s*[:\uff1a]?\s*$" % body, re.IGNORECASE),
            ))
    patterns.sort(key=lambda item: -item[1])
    return patterns


FIELD_PATTERNS = _label_patterns(WORKER_FIELD_ALIASES)
SECTION_PATTERNS = _heading_patterns(SECTION_ALIASES)
SECTION_INLINE_PATTERNS = _label_patterns(SECTION_ALIASES)


def match_section_inline(line: str) -> Optional[tuple[str, str]]:
    text = strip_decoration(line)
    if not text:
        return None
    for key, _, pattern in SECTION_INLINE_PATTERNS:
        found = pattern.match(text)
        if found:
            return key, clean_cell(found.group(1))
    return None


def clean_list_entry(value: str) -> str:
    text = strip_decoration(BULLET_PREFIX.sub("", str(value)))
    text = re.sub(r"\s+", " ", text).strip(" .;:,-")
    return text


def split_list_entries(values: Sequence[str]) -> list[str]:
    entries: list[str] = []

    for value in values:
        stripped = str(value).strip()
        if not stripped:
            continue

        if BULLET_PREFIX.match(stripped):
            entries.append(clean_list_entry(stripped))
            continue

        for piece in INLINE_LIST_SPLIT.split(stripped):
            cleaned = clean_list_entry(piece)
            if cleaned:
                entries.append(cleaned)

    ordered: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        if not (SKILL_MIN_LENGTH <= len(entry) <= SKILL_MAX_LENGTH):
            continue
        marker = normalize(entry)
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(entry)

    return ordered[:SKILL_MAX_ITEMS]


def derive_list_section(section_items: dict[str, list[str]], key: str) -> list[str]:
    return split_list_entries(section_items.get(key, []))


def derive_skills_from_history(section_items: dict[str, list[str]]) -> list[str]:
    history = section_items.get("work_history", [])
    candidates: list[str] = []

    for entry in history:
        cleaned = clean_list_entry(entry)
        if not cleaned:
            continue
        for clause in re.split(r"(?<=[a-z])\.\s+|\.\s*$", cleaned):
            phrase = clause.strip(" .,;")
            if SKILL_MIN_LENGTH <= len(phrase) <= SKILL_MAX_LENGTH:
                candidates.append(phrase)

    return split_list_entries(candidates)[:5]

def strip_decoration(value: str) -> str:
    return clean_cell(str(value).replace("**", "").replace("__", "").lstrip("#").strip())


def match_worker_field(line: str) -> Optional[tuple[str, str]]:
    text = strip_decoration(line)
    if not text:
        return None
    for key, _, pattern in FIELD_PATTERNS:
        found = pattern.match(text)
        if found:
            return key, clean_cell(found.group(1))
    return None


def match_section_heading(line: str) -> Optional[str]:
    text = strip_decoration(line)
    if not text or len(text) > 48:
        return None
    for key, _, pattern in SECTION_PATTERNS:
        if pattern.match(text):
            return key
    return None


def looks_like_person_name(value: str) -> bool:
    text = strip_decoration(value)
    if not text or len(text) > MAX_NAME_LENGTH:
        return False
    if len(text.split()) > MAX_NAME_WORDS:
        return False
    if NUMBER.search(text) or "@" in text:
        return False
    return bool(re.fullmatch(r"[A-Za-z\u00c0-\u024f'.,\- ]+", text))


def table_lines(tables: Sequence[RawTable]) -> list[TextLine]:
    lines: list[TextLine] = []
    for table in sorted(tables, key=lambda item: item.order):
        headers = [clean_cell(cell) for cell in table.headers]
        labelled = sum(1 for cell in headers
                       if cell and (match_worker_field(cell) or match_section_heading(cell)))
        if labelled >= 2 and table.width >= 2:
            for row in table.rows:
                for header, cell in zip(headers, row):
                    value = clean_cell(cell)
                    if header and value:
                        lines.append(TextLine(f"{header}: {value}", True))
            continue
        for row in [headers] + [[clean_cell(cell) for cell in item] for item in table.rows]:
            cells = [cell for cell in row if cell]
            if not cells:
                continue
            if len(cells) >= 2:
                lines.append(TextLine(f"{cells[0]}: {' '.join(cells[1:])}", True))
            else:
                lines.append(TextLine(cells[0], True))
    return lines


def split_candidates(lines: Sequence[TextLine]) -> list[list[TextLine]]:
    blocks: list[list[TextLine]] = []
    current: list[TextLine] = []
    seen_name = False
    for line in lines:
        text = strip_decoration(line.text)
        if not text:
            continue
        matched = match_worker_field(text)
        is_name = matched is not None and matched[0] == "name" and bool(matched[1])
        is_heading = CANDIDATE_HEADING.match(text) is not None and len(text) < 48
        if current and (is_heading or (is_name and seen_name)):
            blocks.append(current)
            current, seen_name = [], False
        current.append(line)
        if is_name:
            seen_name = True
    if current:
        blocks.append(current)
    return blocks


def parse_year_ranges(text: str) -> int:
    total = 0
    for start, end in YEAR_RANGE.findall(text):
        begin = int(start)
        finish = date.today().year if not end.isdigit() else int(end)
        if finish >= begin:
            total += finish - begin
    return total


def parse_duration(text: str) -> Optional[float]:
    found = DURATION.search(text)
    if found is None:
        return None
    return float(found.group(1).replace(",", "."))


def parse_number(text: str) -> Optional[float]:
    found = NUMBER.search(text or "")
    if found is None:
        return None
    return float(found.group(0).replace(",", "."))


def derive_age(fields: dict[str, str]) -> Optional[int]:
    direct = parse_number(fields.get("age", ""))
    if direct is not None and 16 <= direct <= 75:
        return int(direct)
    birth = fields.get("birth_date", "")
    found = YEAR.search(birth)
    if found is not None:
        age = date.today().year - int(found.group(0))
        if 16 <= age <= 75:
            return age
    return None


def derive_gender(fields: dict[str, str]) -> str:
    token = normalize(fields.get("gender", ""))
    if not token:
        return "unspecified"
    if any(word in GENDER_MALE for word in token.split()) or token in GENDER_MALE:
        return "male"
    if any(word in GENDER_FEMALE for word in token.split()) or token in GENDER_FEMALE:
        return "female"
    return "unspecified"


def derive_experience(fields: dict[str, str], sections: dict[str, str]) -> Optional[int]:
    declared = fields.get("years_of_experience", "")
    duration = parse_duration(declared) or parse_number(declared)
    if duration is not None and 0 <= duration <= 55:
        return int(round(duration))
    corpus = " ".join(sections.get(name, "")
                      for name in ("work_history", "summary", "interview_notes"))
    duration = parse_duration(corpus)
    if duration is not None and 0 <= duration <= 55:
        return int(round(duration))
    spans = parse_year_ranges(corpus)
    return spans if 0 < spans <= 55 else None


def derive_shift_value(value: str, ceiling: float) -> Optional[float]:
    number = parse_number(value)
    if number is None or number < 0 or number > ceiling:
        return None
    return number


def parse_candidate(lines: Sequence[TextLine], index: int) -> ExtractedCandidate:
    fields: dict[str, str] = {}
    buckets: dict[str, list[str]] = {}
    active_section: Optional[str] = None
    pending_field: Optional[str] = None
    body: list[str] = []

    for line in lines:
        text = strip_decoration(line.text)
        if not text:
            continue

        body.append(text)

        if CANDIDATE_HEADING.match(text) and len(text) < 48:
            continue

        section = match_section_heading(text)
        if section is not None:
            active_section, pending_field = section, None
            buckets.setdefault(section, [])
            continue

        matched = match_worker_field(text)
        if matched is not None:
            key, value = matched
            if value:
                fields.setdefault(key, value)
                pending_field = None
            else:
                pending_field = key
            continue

        inline = match_section_inline(text)
        if inline is not None:
            key, value = inline
            buckets.setdefault(key, [])
            if value:
                buckets[key].append(value)
            active_section, pending_field = key, None
            continue

        if pending_field is not None:
            fields.setdefault(pending_field, text)
            pending_field = None
            continue

        buckets.setdefault(active_section or "summary", []).append(line.text.strip())

    if "name" not in fields:
        for text in body[:4]:
            if looks_like_person_name(text):
                fields["name"] = text
                break

    section_items = {key: list(values) for key, values in buckets.items() if values}
    sections = {
        key: " ".join(strip_decoration(item) for item in values).strip()
        for key, values in section_items.items()
    }

    skills = derive_list_section(section_items, "skills")
    if not skills:
        skills = derive_skills_from_history(section_items)

    derived = {
        "name": fields.get("name", ""),
        "age": derive_age(fields),
        "gender": derive_gender(fields),
        "years_of_experience": derive_experience(fields, sections),
        "hours_worked_today": derive_shift_value(fields.get("hours_worked_today", ""), 24.0),
        "consecutive_shifts": derive_shift_value(fields.get("consecutive_shifts", ""), 31.0),
        "current_position": fields.get("current_position", ""),
        "shift_pattern": fields.get("shift_pattern", ""),
        "skills": skills,
        "certifications": derive_list_section(section_items, "certifications"),
    }

    return ExtractedCandidate(
        index=index,
        worker_id=f"wrk-{index:02d}",
        fields=fields,
        sections=sections,
        section_items=section_items,
        derived=derived,
        raw_text="\n".join(body),
    )

def parse_candidate(lines: Sequence[TextLine], index: int) -> ExtractedCandidate:
    fields: dict[str, str] = {}
    buckets: dict[str, list[str]] = {}
    active_section: Optional[str] = None
    pending_field: Optional[str] = None
    body: list[str] = []

    for line in lines:
        text = strip_decoration(line.text)
        if not text:
            continue

        body.append(text)

        if CANDIDATE_HEADING.match(text) and len(text) < 48:
            continue

        section = match_section_heading(text)
        if section is not None:
            active_section, pending_field = section, None
            buckets.setdefault(section, [])
            continue

        matched = match_worker_field(text)
        if matched is not None:
            key, value = matched
            if value:
                fields.setdefault(key, value)
                pending_field = None
            else:
                pending_field = key
            continue

        inline = match_section_inline(text)
        if inline is not None:
            key, value = inline
            buckets.setdefault(key, [])
            if value:
                buckets[key].append(value)
            active_section, pending_field = key, None
            continue

        if pending_field is not None:
            fields.setdefault(pending_field, text)
            pending_field = None
            continue

        buckets.setdefault(active_section or "summary", []).append(line.text.strip())

    if "name" not in fields:
        for text in body[:4]:
            if looks_like_person_name(text):
                fields["name"] = text
                break

    section_items = {key: list(values) for key, values in buckets.items() if values}
    sections = {
        key: " ".join(strip_decoration(item) for item in values).strip()
        for key, values in section_items.items()
    }

    skills = derive_list_section(section_items, "skills")
    if not skills:
        skills = derive_skills_from_history(section_items)

    derived = {
        "name": fields.get("name", ""),
        "age": derive_age(fields),
        "gender": derive_gender(fields),
        "years_of_experience": derive_experience(fields, sections),
        "hours_worked_today": derive_shift_value(fields.get("hours_worked_today", ""), 24.0),
        "consecutive_shifts": derive_shift_value(fields.get("consecutive_shifts", ""), 31.0),
        "current_position": fields.get("current_position", ""),
        "shift_pattern": fields.get("shift_pattern", ""),
        "skills": skills,
        "certifications": derive_list_section(section_items, "certifications"),
    }

    return ExtractedCandidate(
        index=index,
        worker_id=f"wrk-{index:02d}",
        fields=fields,
        sections=sections,
        section_items=section_items,
        derived=derived,
        raw_text="\n".join(body),
    )

def evidence_score(candidate: ExtractedCandidate) -> int:
    signals = [key for key in candidate.fields if key != "name" and candidate.fields[key]]
    list_signals = 1 if candidate.derived.get("skills") else 0
    return len(signals) + len(candidate.sections) + list_signals


def looks_like_curriculum_vitae(candidate: ExtractedCandidate,
                                min_evidence: int = MIN_EVIDENCE_SCORE) -> bool:
    if not candidate.derived.get("name"):
        return False
    if normalize(Path(candidate.source_name).stem) in NON_CV_STEMS:
        return False
    return evidence_score(candidate) >= min_evidence


def extract_worker_document(path: str | Path, offset: int = 0, min_evidence: int = MIN_EVIDENCE_SCORE) -> ExtractedWorkerDocument:
    resolved = Path(path)
    extractor = DOCUMENT_EXTRACTORS.get(resolved.suffix.lower())
    if extractor is None:
        raise UnsupportedDocumentError(
            f"Format dokumen tidak didukung: '{resolved.suffix}'. "
            f"Didukung: {sorted(DOCUMENT_EXTRACTORS.keys())}"
        )

    text_lines, raw_tables = extractor(resolved)
    lines = list(text_lines) + table_lines(raw_tables)
    blocks = split_candidates(lines)

    candidates = []
    rejected = []

    for position, block in enumerate(blocks, start=1):
        candidate = parse_candidate(block, len(candidates) + offset + 1)
        candidate.source_name = resolved.name

        if looks_like_curriculum_vitae(candidate, min_evidence=min_evidence):
            candidates.append(candidate)
        else:
            rejected.append({
                "source": resolved.name,
                "nama_terbaca": candidate.derived.get("name") or "(tidak terbaca)",
                "alasan": f"bukti tidak cukup untuk dianggap CV (skor {evidence_score(candidate)}"
                          f" dari minimal {min_evidence})",
            })

    return ExtractedWorkerDocument(
        source_names=[resolved.name],
        candidates=candidates,
        rejected_blocks=rejected,
        raw_text="\n".join(line.text for line in lines),
    )


def merge_worker_documents(documents: Sequence[ExtractedWorkerDocument]) -> ExtractedWorkerDocument:
    merged = ExtractedWorkerDocument()

    for document in documents:
        merged.source_names.extend(document.source_names)
        merged.rejected_blocks.extend(document.rejected_blocks)

        for candidate in document.candidates:
            candidate.index = len(merged.candidates) + 1
            candidate.worker_id = f"wrk-{candidate.index:02d}"
            merged.candidates.append(candidate)

    merged.raw_text = "\n\n".join(document.raw_text for document in documents)
    return merged


def candidate_payload(candidate: ExtractedCandidate) -> str:
    blocks = [f"KANDIDAT {candidate.index} — gunakan worker_id: {candidate.worker_id}"]

    for key, label in FIELD_LABELS.items():
        value = candidate.derived.get(key)
        blocks.append(f"{label}: {value if value not in (None, '') else 'tidak tercantum'}")

    for key in LIST_SECTIONS:
        entries = candidate.derived.get(key) or []
        label = SECTION_LABELS[key]
        if entries:
            numbered = "\n".join(f"  {position}. {entry}"
                                 for position, entry in enumerate(entries, start=1))
            blocks.append(f"{label} (daftar terpisah):\n{numbered}")
        else:
            blocks.append(f"{label} (daftar terpisah): tidak tercantum")

    for key, label in SECTION_LABELS.items():
        if key in LIST_SECTIONS:
            continue
        value = candidate.sections.get(key)
        if value:
            blocks.append(f"{label}: {value}")

    missing = candidate.missing_fields()
    if missing:
        blocks.append(f"FIELD TIDAK TERBACA: {', '.join(missing)}")

    return "\n".join(blocks)

def build_worker_agent_input(document: ExtractedWorkerDocument) -> str:
    header = f"Jumlah kandidat terbaca: {len(document.candidates)}"
    payloads = [candidate_payload(candidate) for candidate in document.candidates]
    return "\n\n".join([header] + payloads)



def build_worker_agent_input_chunks(
    document: ExtractedWorkerDocument, chunk_size: int = 4
) -> list[str]:
    """
    Sama seperti build_worker_agent_input, tapi membagi kandidat menjadi
    beberapa batch agar setiap panggilan LLM tidak melebihi max_tokens
    saat jumlah kandidat dalam satu ZIP banyak.
    """
    candidates = document.candidates
    if not candidates:
        return []

    chunks: list[str] = []
    for i in range(0, len(candidates), chunk_size):
        batch = candidates[i : i + chunk_size]
        header = f"Jumlah kandidat terbaca: {len(batch)}"
        payloads = [candidate_payload(candidate) for candidate in batch]
        chunks.append("\n\n".join([header] + payloads))
    return chunks