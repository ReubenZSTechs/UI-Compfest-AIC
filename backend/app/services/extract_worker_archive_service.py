from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

from app.services.extract_input_field_service import (
    DOCUMENT_EXTRACTORS,
    UnsupportedDocumentError,
)
from app.services.extract_worker_field_service import (
    ExtractedWorkerDocument,
    extract_worker_document,
    merge_worker_documents,
)

SUPPORTED_SUFFIXES = tuple(sorted(DOCUMENT_EXTRACTORS.keys()))

JUNK_PREFIXES = ("__MACOSX/", "__macosx/")
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}

MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_MEMBERS = 200
MAX_COMPRESSION_RATIO = 120.0


class ArchiveError(ValueError):
    pass


@dataclass
class ArchiveMember:
    member_name: str
    file_name: str
    suffix: str
    size_bytes: int


@dataclass
class ArchiveReport:
    archive_name: str
    accepted: list[ArchiveMember] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)

    def accepted_count(self) -> int:
        return len(self.accepted)

    def suffix_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for member in self.accepted:
            counts[member.suffix] = counts.get(member.suffix, 0) + 1
        return counts


def is_junk(name: str) -> bool:
    if name.startswith(JUNK_PREFIXES):
        return True
    tail = name.rsplit("/", 1)[-1]
    return tail in JUNK_NAMES or tail.startswith("._") or tail.startswith(".")


def is_unsafe(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return True
    if ".." in Path(name.replace("\\", "/")).parts:
        return True
    return ":" in name.split("/")[-1][:2]


def inspect_archive(path: Path) -> tuple[list[zipfile.ZipInfo], ArchiveReport]:
    report = ArchiveReport(archive_name=path.name)

    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ArchiveError(f"Berkas ZIP rusak atau bukan arsip ZIP: {error}") from error

    with archive:
        infos = archive.infolist()

        if len(infos) > MAX_MEMBERS:
            raise ArchiveError(
                f"Arsip memuat {len(infos)} entri, melebihi batas {MAX_MEMBERS} entri."
            )

        selected: list[zipfile.ZipInfo] = []
        total = 0

        for info in infos:
            name = info.filename

            if info.is_dir():
                continue

            if is_junk(name):
                report.skipped.append({"member": name, "alasan": "berkas sistem atau tersembunyi"})
                continue

            if is_unsafe(name):
                report.skipped.append({"member": name, "alasan": "jalur berkas tidak aman"})
                continue

            suffix = Path(name).suffix.lower()

            if suffix not in DOCUMENT_EXTRACTORS:
                report.skipped.append({
                    "member": name,
                    "alasan": f"ekstensi '{suffix or 'tanpa ekstensi'}' tidak didukung",
                })
                continue

            if info.file_size > MAX_MEMBER_BYTES:
                report.skipped.append({
                    "member": name,
                    "alasan": f"ukuran {info.file_size} byte melebihi batas per berkas",
                })
                continue

            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    report.skipped.append({
                        "member": name,
                        "alasan": f"rasio kompresi {ratio:.0f}x mencurigakan",
                    })
                    continue

            total += info.file_size

            if total > MAX_TOTAL_BYTES:
                raise ArchiveError(
                    f"Total ukuran isi arsip melampaui batas {MAX_TOTAL_BYTES} byte."
                )

            selected.append(info)
            report.accepted.append(
                ArchiveMember(
                    member_name=name,
                    file_name=Path(name).name,
                    suffix=suffix,
                    size_bytes=info.file_size,
                )
            )

    selected.sort(key=lambda info: info.filename.lower())
    report.accepted.sort(key=lambda member: member.member_name.lower())

    if not selected:
        raise ArchiveError(
            "Tidak ada berkas CV yang bisa diproses di dalam arsip. "
            f"Ekstensi yang didukung: {', '.join(SUPPORTED_SUFFIXES)}."
        )

    return selected, report


def unpack_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, target_dir: Path) -> Path:
    target = target_dir / Path(info.filename).name

    counter = 1
    while target.exists():
        stem = Path(info.filename).stem
        target = target_dir / f"{stem}__{counter}{Path(info.filename).suffix}"
        counter += 1

    with archive.open(info) as source, open(target, "wb") as handle:
        shutil.copyfileobj(source, handle, length=1024 * 256)

    return target


def extract_worker_archive(path: str | Path, strict: bool = False,
                           progress: Optional[Callable[[int, int], None]] = None
                           ) -> tuple[ExtractedWorkerDocument, ArchiveReport]:
    resolved = Path(path)

    if resolved.suffix.lower() != ".zip":
        raise ArchiveError(f"Berkas '{resolved.name}' bukan arsip ZIP.")

    selected, report = inspect_archive(resolved)
    documents: list[ExtractedWorkerDocument] = []
    total = len(selected)

    with tempfile.TemporaryDirectory(prefix="cv_archive_") as staging:
        staging_dir = Path(staging)

        with zipfile.ZipFile(resolved) as archive:
            for position, info in enumerate(selected, start=1):
                member = unpack_member(archive, info, staging_dir)

                try:
                    documents.append(extract_worker_document(member))

                except Exception as error:
                    failure = {
                        "member": info.filename,
                        "error": f"{type(error).__name__}: {error}",
                    }

                    if strict:
                        raise ArchiveError(
                            f"Gagal memproses '{info.filename}': {failure['error']}"
                        ) from error

                    report.failed.append(failure)

                if progress is not None:
                    progress(position, total)

    if not documents:
        raise ArchiveError("Seluruh berkas di dalam arsip gagal diekstraksi.")

    merged = merge_worker_documents(documents)

    if not merged.candidates:
        raise ArchiveError(
            "Tidak ada profil pekerja yang terbaca dari arsip. "
            f"{len(merged.rejected_blocks)} berkas dinilai bukan CV."
        )

    return merged, report


def extract_worker_uploads(paths: Sequence[str | Path], strict: bool = False,
                           progress: Optional[Callable[[int, int], None]] = None
                           ) -> tuple[ExtractedWorkerDocument, list[ArchiveReport]]:
    documents: list[ExtractedWorkerDocument] = []
    reports: list[ArchiveReport] = []

    ordered = sorted(Path(item) for item in paths)
    total = len(ordered)

    for position, item in enumerate(ordered, start=1):
        if item.suffix.lower() == ".zip":
            document, report = extract_worker_archive(item, strict=strict)
            documents.append(document)
            reports.append(report)

        else:
            documents.append(extract_worker_document(item))

        if progress is not None:
            progress(position, total)

    if not documents:
        raise ArchiveError("Tidak ada dokumen pekerja yang berhasil diekstraksi.")

    merged = merge_worker_documents(documents)

    if not merged.candidates:
        raise ArchiveError("Tidak ada profil pekerja yang terbaca dari berkas yang diunggah.")

    return merged, reports