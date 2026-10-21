"""Offline, user-supplied reference crosswalks; no database validation or downloads.

'approved' is the user's *reported manual review status*. We do not independently
verify the source record, its taxonomy, the crosswalk, or its metadata.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

REQUIRED_FIELDS = (
    "motif_core", "reference_family_label", "native_tf_family", "source_database",
    "source_release", "source_record_id", "mapping_status", "evidence_link", "mapping_note"
)


@dataclass(frozen=True)
class ReferenceRecord:
    motif_core: str
    reference_family_label: str
    native_tf_family: str
    source_database: str
    source_release: str
    source_record_id: str
    mapping_status: str
    evidence_link: str
    mapping_note: str


def read_reference(path: Optional[Path]) -> Dict[str, ReferenceRecord]:
    if path is None:
        return {}
    result: Dict[str, ReferenceRecord] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = reader.fieldnames
        if (not header or len(set(header)) != len(header)
                or set(header) != set(REQUIRED_FIELDS)):
            raise ValueError("Reference table must have exactly these columns: " + ", ".join(REQUIRED_FIELDS))
        for lineno, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed reference record on line {lineno}")
            cleaned = {k: row[k].strip() for k in REQUIRED_FIELDS}
            # All source fields are necessary to permit human auditing; a non-empty
            # field or URL is NOT evidence of source verification.
            required_values = [f for f in REQUIRED_FIELDS if f != "mapping_note"]
            if any(not cleaned[f] for f in required_values):
                raise ValueError(f"Missing required reference metadata on line {lineno}")
            if cleaned["mapping_status"] not in {"pending", "approved"}:
                raise ValueError(f"mapping_status must be pending or approved (line {lineno})")
            key = cleaned["motif_core"].casefold()
            if key in result:
                raise ValueError(f"Duplicate reference motif_core (case-insensitive) at line {lineno}")
            result[key] = ReferenceRecord(**cleaned)
    return result


def compare_reference(motif_core: str, family_label: str,
                      mapping: Dict[str, ReferenceRecord], supplied: bool) -> dict:
    """Exact-key comparison of two *user-provided* family labels, not truth."""
    defaults = {
        "reference_family_label": "", "reference_native_family": "",
        "reference_source_database": "", "reference_source_release": "",
        "reference_record_id": "", "reference_mapping_status": "",
        "reference_evidence_link": "", "reference_mapping_note": "",
        "reference_concordance": "NOT_SUPPLIED" if not supplied else "NO_EXACT_MATCH"
    }
    rec = mapping.get(motif_core.strip().casefold()) if supplied else None
    if rec is None:
        return defaults
    defaults.update({
        "reference_family_label": rec.reference_family_label,
        "reference_native_family": rec.native_tf_family,
        "reference_source_database": rec.source_database,
        "reference_source_release": rec.source_release,
        "reference_record_id": rec.source_record_id,
        "reference_mapping_status": rec.mapping_status,
        "reference_evidence_link": rec.evidence_link,
        "reference_mapping_note": rec.mapping_note,
        "reference_concordance": ("PENDING_MANUAL_REVIEW" if rec.mapping_status == "pending"
            else "SELF_REPORTED_LABEL_AGREES" if rec.reference_family_label == family_label
            else "SELF_REPORTED_LABEL_DIFFERS")
    })
    return defaults
