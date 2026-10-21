"""CLI for provisional motif-name labeling and offline source-crosswalk audit."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .core import VERSION, RULES_PATH, annotate, load_curated, load_rules, sha256_file
from .format_checks import detected_format
from .reference import compare_reference, read_reference
from .semantic import V03_FIELDS, REFERENCE, load_crosswalk, semantic_fields
from .claims import CLAIM_FIELDS, claim_fields

ANNOT_FIELDS = ["motif_core", "motif_head", "core_parenthetical_family", "family_label",
                "evidence_method", "rule_ids", "review_required", "review_reason"]
REFERENCE_FIELDS = ["reference_family_label", "reference_native_family", "reference_source_database",
                    "reference_source_release", "reference_record_id", "reference_mapping_status",
                    "reference_evidence_link", "reference_mapping_note", "reference_concordance"]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.casefold())


def choose_column(cols, requested, aliases, required=True):
    if requested:
        if requested not in cols:
            raise ValueError(f"Column not found: {requested!r}; available={cols!r}")
        return requested
    for choice in aliases:
        candidates = [col for col in cols if norm(col) == norm(choice)]
        if len(candidates) > 1:
            raise ValueError(f"Ambiguous matching columns: {candidates}")
        if candidates:
            return candidates[0]
    if required:
        raise ValueError(f"Required column missing (accepted aliases: {aliases}); available={cols!r}")
    return None


def read_tsv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        cols = reader.fieldnames
        if not cols or any(not c or not c.strip() for c in cols) or len(cols) != len(set(cols)):
            raise ValueError("Invalid, missing, blank or duplicate TSV header")
        rows = list(reader)
    for lineno, row in enumerate(rows, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Malformed TSV record at source line {lineno}")
    return cols, rows


def parse_q(value, lineno):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid q-value on data row {lineno}: {value!r}")
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"q-value out of range [0,1] on data row {lineno}: {value!r}")
    return number


def write_tsv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def cmd_annotate(args):
    if not math.isfinite(args.q_threshold) or not 0 < args.q_threshold <= 1:
        raise ValueError("--q-threshold must be finite, >0 and <=1")
    if not args.input.is_file():
        raise ValueError("Input is not a regular file")

    cols, rows = read_tsv(args.input)
    observed_format = detected_format(cols, args.input_format)
    motif_col = choose_column(cols, args.motif_column, ("Motif Name", "motif", "motif_name", "Name"))
    reserved = set(ANNOT_FIELDS + REFERENCE_FIELDS + V03_FIELDS + CLAIM_FIELDS)
    if reserved.intersection(cols):
        raise ValueError("Input has reserved output columns: " + ", ".join(sorted(reserved.intersection(cols))))

    groups = [s.strip() for s in args.group_by.split(",") if s.strip()]
    if len(set(groups)) != len(groups):
        raise ValueError("Duplicate --group-by field")
    if args.summary and any(g not in cols for g in groups):
        raise ValueError(f"Missing grouping columns: {[g for g in groups if g not in cols]}")
    q_col = choose_column(cols, args.q_column,
                          ("qvalue", "q-value", "q-value (Benjamini)", "q.value", "q"),
                          required=args.summary)
    rules = load_rules(args.rules)
    crosswalk = load_crosswalk()
    curated = load_curated(args.curated)
    ref = read_reference(args.reference_table)
    with_reference = args.reference_table is not None

    annotated = []
    hit_counts = Counter()
    ref_counts = Counter()
    summary_groups = defaultdict(list)
    evidence_groups = defaultdict(list)
    restricted_groups = defaultdict(list)
    disposition_counts = Counter()
    reference_comparison = []
    levels = Counter()
    semantic_review_count = 0
    for lineno, row in enumerate(rows, 2):
        a = annotate(row[motif_col], rules, curated)
        ref_a = compare_reference(a.motif_core, a.family_label, ref, with_reference)
        ref_status = ref_a["reference_concordance"]
        conflict = ref_status in {"SELF_REPORTED_LABEL_DIFFERS", "PENDING_MANUAL_REVIEW"}
        needs_review = a.review_required or conflict
        reason = a.review_reason
        if conflict:
            reason += ";" + ("reference_label_conflict" if ref_status == "SELF_REPORTED_LABEL_DIFFERS"
                              else "reference_mapping_pending")
        new = dict(row)
        new.update({"motif_core": a.motif_core, "motif_head": a.motif_head,
                    "core_parenthetical_family": a.core_parenthetical_family,
                    "family_label": a.family_label, "evidence_method": a.evidence_method,
                    "rule_ids": a.rule_ids, "review_required": str(needs_review).upper(),
                    "review_reason": reason})
        new.update(ref_a)
        semantics = semantic_fields(row[motif_col], a, crosswalk)
        # User-supplied reference tables do not authenticate themselves: a mismatch
        # or pending review must NEVER be bypassed by bundled name metadata.
        if conflict:
            semantics["v03_review_required"] = "TRUE"
            semantics["v03_review_status"] = "PENDING_REFERENCE_TABLE_CONFLICT"
            semantics["v03_review_reason"] += ";UNVERIFIED_USER_REFERENCE_CONFLICT_OR_PENDING"
        new.update(semantics)
        claims = claim_fields(semantics, ref_status)
        new.update(claims)
        disposition_counts[claims["v03_claim_disposition"]] += 1
        levels[semantics["v03_label_level"]] += 1
        semantic_review_count += semantics["v03_review_required"] == "TRUE"
        annotated.append(new)
        hit_counts[a.family_label] += 1
        ref_counts[ref_a["reference_concordance"]] += 1
        if with_reference:
            reference_comparison.append({"input_line": lineno, "motif_name": row[motif_col],
                                         "motif_core": a.motif_core, "rule_family_label": a.family_label,
                                         **ref_a})
        if args.summary:
            q = parse_q(row[q_col], lineno)
            if q < args.q_threshold:
                key = tuple(row[col] for col in groups) + (a.family_label,)
                summary_groups[key].append((q, row[motif_col]))
                ekey = tuple(row[col] for col in groups) + (
                    claims["v03_annotation_origin"],
                    claims["v03_metadata_evidence_scope"],
                    claims["v03_claim_disposition"],
                    semantics["v03_label_level"],
                    semantics["v03_reference_rule_id"],
                    claims["v03_review_action"],
                )
                evidence_groups[ekey].append((q, row[motif_col]))
                if claims["v03_reference_name_supported"] == "TRUE":
                    rkey = tuple(row[col] for col in groups) + (
                        semantics["v03_reference_rule_id"],
                        semantics["v03_tf_name_candidate"],
                        semantics["v03_reference_tf_class"],
                        semantics["v03_reference_tf_family"],
                    )
                    restricted_groups[rkey].append((q, row[motif_col]))

    summary_rows = []
    for key, vals in sorted(summary_groups.items()):
        vals.sort(key=lambda pair: (pair[0], pair[1]))
        entry = dict(zip(groups + ["family_label"], key))
        entry["significant_motif_record_count"] = len(vals)
        entry["top_motifs_sorted_by_q"] = ";".join(name for _, name in vals[:8])
        summary_rows.append(entry)

    evidence_cols = groups + ["v03_annotation_origin", "v03_metadata_evidence_scope",
        "v03_claim_disposition", "v03_label_level", "v03_reference_rule_id",
        "v03_review_action", "significant_motif_record_count", "top_motifs_sorted_by_q"]
    restricted_cols = groups + ["v03_reference_rule_id", "v03_tf_name_candidate",
        "v03_reference_tf_class", "v03_reference_tf_family",
        "significant_motif_record_count", "top_motifs_sorted_by_q",
        "interpretation_scope"]
    evidence_rows = []
    restricted_rows = []
    for key, values in sorted(evidence_groups.items()):
        values.sort(key=lambda pair: (pair[0], pair[1]))
        d = dict(zip(evidence_cols[:-2], key))
        d["significant_motif_record_count"] = len(values)
        d["top_motifs_sorted_by_q"] = ";".join(n for _, n in values[:8])
        evidence_rows.append(d)
    for key, values in sorted(restricted_groups.items()):
        values.sort(key=lambda pair: (pair[0], pair[1]))
        d = dict(zip(restricted_cols[:-3], key))
        d["significant_motif_record_count"] = len(values)
        d["top_motifs_sorted_by_q"] = ";".join(n for _, n in values[:8])
        d["interpretation_scope"] = "TF_NAME_METADATA_ONLY_NO_PWM_OR_BINDING_PROOF"
        restricted_rows.append(d)

    output_paths = [args.outdir / "annotated.tsv", args.outdir / "audit.json"]
    if args.summary:
        output_paths.insert(1, args.outdir / "summary.tsv")
        output_paths.insert(2, args.outdir / "summary_evidence.tsv")
        output_paths.insert(3, args.outdir / "summary_restricted_name_metadata.tsv")
    if with_reference:
        output_paths.insert(-1, args.outdir / "reference_comparison.tsv")
    protected = [args.input, args.rules, REFERENCE]
    if args.curated:
        protected.append(args.curated)
    if args.reference_table:
        protected.append(args.reference_table)
    if set(map(lambda p: p.resolve(), protected)).intersection(p.resolve() for p in output_paths):
        raise ValueError("Output path would overwrite an input, rules, or reference file")
    if not args.overwrite and any(p.exists() or p.is_symlink() for p in output_paths):
        raise ValueError("Output already exists; use a new directory or --overwrite")

    audit = {
        "version": VERSION,
        "rc2_claim_logic_sha256": sha256_file(Path(__file__).with_name("claims.py")),
        "v03_reference_name_crosswalk_sha256": sha256_file(REFERENCE),
        "v03_semantic_level_counts": dict(sorted(levels.items())),
        "v03_review_required_count": semantic_review_count,
        "v03_approved_tf_name_metadata_hits": sum(x["v03_name_mapping_status"] == "TF_NAME_METADATA_CLASSIFICATION_SUPPORTED" for x in annotated),
        "v03_pwm_identity_tested": False, "v03_tf_binding_proven": False,
        "v03_legacy_family_summary_not_biological_validation": True,
        "rc2_claim_disposition_counts": dict(sorted(disposition_counts.items())),
        "rc2_reference_name_supported_count": sum(x["v03_reference_name_supported"] == "TRUE" for x in annotated),
        "rc2_scientifically_validated_motif_family_claims": 0,
        "rc2_legacy_summary_semantics": "PROVISIONAL_ONLY_NOT_APPROVED_TF_FAMILY",
        "rc2_evidence_summary_semantics": "NAME_ORIGIN_AND_REVIEW_ACTION_NOT_BIOLOGICAL_VALIDATION",
        "rc2_restricted_summary_semantics": "TF_NAME_METADATA_CROSSWALK_ONLY_NO_PWM_IDENTITY",
        "purpose": "provisional_name_based_annotation_and_user_supplied_reference_concordance_not_pwm_validation",
        "input_format": observed_format, "input_columns": cols,
        "input_sha256": sha256_file(args.input), "rules_sha256": sha256_file(args.rules),
        "curated_sha256": sha256_file(args.curated) if args.curated else None,
        "reference_sha256": sha256_file(args.reference_table) if args.reference_table else None,
        "reference_source_verified_by_software": False,
        "reference_matching": "exact_case_insensitive_motif_core_only",
        "reference_comparison_counts": dict(sorted(ref_counts.items())),
        "reference_table_distinct_keys": len(ref),
        "motif_column": motif_col, "q_column": q_col if args.summary else None,
        "rows": len(rows), "families": dict(sorted(hit_counts.items())),
        "review_required_count": sum(r["review_required"] == "TRUE" for r in annotated),
        "summary_performed": args.summary,
        "summary_uses_strict_less_than": args.q_threshold if args.summary else None,
        "summary_group_by": groups if args.summary else [],
        "significant_motif_record_count": (sum(len(v) for v in summary_groups.values())
                                          if args.summary else None),
        "interpretation_warning": "Concordance with user-supplied labels does NOT validate biological family membership."
    }

    # Stage output before replacing individual destination files. A crash in the
    # replacement phase can still leave a partial set; no multi-file transaction.
    args.outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".audit-stage-", dir=args.outdir) as temp_dir:
        stage = Path(temp_dir)
        write_tsv(stage / "annotated.tsv", cols + ANNOT_FIELDS + REFERENCE_FIELDS + V03_FIELDS + CLAIM_FIELDS, annotated)
        if args.summary:
            write_tsv(stage / "summary.tsv", groups + ["family_label",
                      "significant_motif_record_count", "top_motifs_sorted_by_q"], summary_rows)
            write_tsv(stage / "summary_evidence.tsv", evidence_cols, evidence_rows)
            write_tsv(stage / "summary_restricted_name_metadata.tsv", restricted_cols, restricted_rows)
        if with_reference:
            write_tsv(stage / "reference_comparison.tsv",
                      ["input_line", "motif_name", "motif_core", "rule_family_label"] + REFERENCE_FIELDS,
                      reference_comparison)
        (stage / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2)
                                            + "\n", encoding="utf-8")
        for dest in output_paths:
            os.replace(stage / dest.name, dest)
    print(json.dumps({"status": "OK", "rows": len(rows), "format": observed_format,
                      "manual_review_needed": audit["review_required_count"],
                      "v03_review_needed": audit["v03_review_required_count"],
                      "reference_concordance": audit["reference_comparison_counts"],
                      "output_dir": str(args.outdir)}, ensure_ascii=False))


def cmd_check_reference(args):
    refs = read_reference(args.reference_table)
    counts = Counter(r.mapping_status for r in refs.values())
    print(json.dumps({"status": "VALID_FORMAT_ONLY", "record_count": len(refs),
                      "declared_review_status": dict(sorted(counts.items())),
                      "reference_sha256": sha256_file(args.reference_table),
                      "external_records_verified": False}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="HOMER provisional motif-family label auditing (offline)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("annotate", help="Annotate knownResults.txt or generic TSV; optional reference concordance")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--input-format", choices=["auto", "homer-known", "generic-tsv"], default="auto")
    p.add_argument("--motif-column", help="Override detected motif column")
    p.add_argument("--rules", type=Path, default=RULES_PATH)
    p.add_argument("--curated", type=Path, help="Optional legacy user-curated override (unverified)")
    p.add_argument("--reference-table", type=Path,
                   help="Offline manually prepared crosswalk; no database querying or verification")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--q-column", help="Override detected q-value column")
    p.add_argument("--q-threshold", type=float, default=0.05)
    p.add_argument("--group-by", default="", help="Comma-separated exact columns, default only family")
    p.add_argument("--overwrite", action="store_true")
    check = sub.add_parser("check-reference", help="Validate reference TSV schema only")
    check.add_argument("--reference-table", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "annotate":
            cmd_annotate(args)
        elif args.command == "check-reference":
            cmd_check_reference(args)
    except (ValueError, OSError, csv.Error, re.error) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
