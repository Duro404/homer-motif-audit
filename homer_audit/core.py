"""Conservative name-only annotation of HOMER known motif labels.

No PWM calculation, binding inference, or external database querying is performed.
"""
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

VERSION = "0.3.0-rc2"
RULES_PATH = Path(__file__).with_name("rules.tsv")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    stage: str
    regex: str
    family: str
    review_required: bool
    note: str


@dataclass(frozen=True)
class Annotation:
    motif_core: str
    motif_head: str
    core_parenthetical_family: str
    family_label: str
    evidence_method: str
    rule_ids: str
    review_required: bool
    review_reason: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def core_parts(name: str) -> tuple[str, str, str]:
    # HOMER often uses / to separate the core label from assay provenance,
    # but C/EBP is itself a biological TF-name spelling containing a slash.
    # Preserve that prefix before detecting the source separator.
    raw = name.strip()
    cebp = re.match(r"^C/EBP[A-Z0-9]*(?:\([^()]*\))?", raw, re.I)
    if cebp and (cebp.end() == len(raw) or raw[cebp.end():].startswith("/")):
        core = raw[:cebp.end()]
    else:
        core = raw.split("/", 1)[0].strip()
    # HOMER motif label: TF(symbol)(structural-tag)/experiment-origin...
    head = core.split("(", 1)[0].strip().upper().replace(" ", "")
    m = re.search(r"\(([^()]*)\)", core)
    tag = m.group(1).strip().upper() if m else ""
    return core, head, tag


def load_rules(path: Path = RULES_PATH) -> List[Rule]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        expected = {"rule_id", "stage", "regex", "family", "review_required", "note"}
        if not reader.fieldnames or set(reader.fieldnames) != expected:
            raise ValueError(f"Rule table must have columns {sorted(expected)}")
        rules = []
        ids = set()
        for lineno, row in enumerate(reader, 2):
            identifier = row["rule_id"].strip()
            if not identifier or identifier in ids:
                raise ValueError(f"Invalid/duplicate rule_id at line {lineno}")
            ids.add(identifier)
            if row["stage"] not in {"head", "tag"}:
                raise ValueError(f"Invalid stage at line {lineno}")
            flag = row["review_required"].lower()
            if flag not in {"true", "false"}:
                raise ValueError(f"Invalid review_required at line {lineno}")
            re.compile(row["regex"])
            rules.append(Rule(identifier, row["stage"], row["regex"],
                              row["family"], flag == "true", row["note"]))
        if not rules:
            raise ValueError("Rule table is empty")
        return rules


def load_curated(path: Optional[Path]) -> Dict[str, dict]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"motif_core", "family", "source_reference", "curator_note"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"Curated mapping needs columns {sorted(required)}")
        mapping = {}
        for lineno, row in enumerate(reader, 2):
            k = row["motif_core"].strip().casefold()
            if not k or k in mapping or not row["family"].strip() or not row["source_reference"].strip():
                raise ValueError(f"Invalid/duplicate mapping at line {lineno}")
            mapping[k] = row
        return mapping


def annotate(name: str, rules: List[Rule], curated: Dict[str, dict]) -> Annotation:
    core, head, tag = core_parts(name)
    if not core or not head:
        return Annotation(core, head, tag, "Unclassified", "none", "", True, "empty_or_invalid_name")
    if core.casefold() in curated:
        row = curated[core.casefold()]
        return Annotation(core, head, tag, row["family"].strip(),
                          "user_curated_mapping", "CURATED", True,
                          "manual_reference_review_required")
    # A family claim from a specific TF-name pattern takes precedence over a
    # broad tag. Conflicting HEAD matches are not resolved silently.
    for stage, value in (("head", head), ("tag", tag)):
        if not value:
            continue
        matches = [rule for rule in rules if rule.stage == stage and re.fullmatch(rule.regex, value, re.I)]
        if not matches:
            continue
        labels = sorted({rule.family for rule in matches})
        ids = ";".join(rule.rule_id for rule in matches)
        if len(labels) > 1:
            return Annotation(core, head, tag, "Ambiguous", "conflicting_name_rules",
                              ids, True, "multiple_family_matches")
        review = any(rule.review_required for rule in matches)
        return Annotation(core, head, tag, labels[0],
                          "name_rule" if stage == "head" else "parenthetical_tag_rule",
                          ids, review, "manual_review_requested" if review else "name_based_only")
    return Annotation(core, head, tag, "Unclassified", "none", "", True, "no_matching_rule")
