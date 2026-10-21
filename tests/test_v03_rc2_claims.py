"""RC2 claim gate tests. Synthetic evidence cases, not real binding validation."""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homer_audit.claims import CLAIM_FIELDS, claim_fields
from homer_audit.core import annotate, load_rules
from homer_audit.semantic import load_crosswalk, semantic_fields

ROOT = Path(__file__).resolve().parents[1]


class ClaimGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()
        cls.mapping = load_crosswalk()

    def calc(self, name, ref_status="NOT_SUPPLIED"):
        legacy = annotate(name, self.rules, {})
        sem = semantic_fields(name, legacy, self.mapping)
        if ref_status in {"SELF_REPORTED_LABEL_DIFFERS", "PENDING_MANUAL_REVIEW"}:
            sem["v03_review_required"] = "TRUE"
            sem["v03_review_status"] = "PENDING_REFERENCE_TABLE_CONFLICT"
        return claim_fields(sem, ref_status)

    def test_all_ten_mapping_rules_restricted_name_only(self):
        cases = ["CEBPA(bZIP)", "FOXA1(Forkhead)", "SOX9(HMG)",
                 "MEF2A(MADS)", "SRF(MADS)", "GATA4(Zf)", "RUNX1(Runt)",
                 "SMAD3", "TEAD4", "FLI1(ETS)"]
        for name in cases:
            with self.subTest(name=name):
                x = self.calc(name)
                self.assertEqual(x["v03_reference_name_supported"], "TRUE")
                self.assertEqual(x["v03_family_claim_validated"], "FALSE")
                self.assertIn("TF_NAME", x["v03_metadata_evidence_scope"])

    def test_cebp_and_srf_specific_without_database_claim_overreach(self):
        for name in ["CEBPA(bZIP)", "SRF(MADS)"]:
            x = self.calc(name)
            self.assertTrue(x["v03_native_family_for_name_only"])
            self.assertFalse(x["v03_claim_disposition"].startswith("VALIDATED"))
            self.assertEqual(x["v03_review_action"], "NO_ADDITIONAL_REVIEW_TRIGGER_NOT_AN_APPROVAL")

    def test_cebp_wrong_name_no_automatic_approval(self):
        for n in ["CEBPG(bZIP)", "CEBPZ(bZIP)", "SOX2(HMG)", "SRF2(MADS)"]:
            with self.subTest(n=n):
                self.assertEqual(self.calc(n)["v03_reference_name_supported"], "FALSE")

    def test_generic_complex_composite_member_hold(self):
        for n in ["ETS(ETS)", "AP-1(bZIP)", "NFY(CCAAT)",
                  "FOXA1:AR(Forkhead,NR)", "EWS:FLI1-fusion(ETS)", "BATF(bZIP)"]:
            with self.subTest(n=n):
                x = self.calc(n)
                self.assertEqual(x["v03_review_action"], "REVIEW_REQUIRED")
                self.assertEqual(x["v03_reference_name_supported"], "FALSE")
                self.assertEqual(x["v03_native_family_for_name_only"], "")

    def test_ctcf_no_extra_review_is_not_approval(self):
        x = self.calc("CTCF(Zf)")
        self.assertEqual(x["v03_review_action"], "NO_ADDITIONAL_REVIEW_TRIGGER_NOT_AN_APPROVAL")
        self.assertEqual(x["v03_family_claim_validated"], "FALSE")
        self.assertEqual(x["v03_reference_name_supported"], "FALSE")

    def test_reference_conflict_withholds_native_family_even_when_name_matches(self):
        for status in ("SELF_REPORTED_LABEL_DIFFERS", "PENDING_MANUAL_REVIEW"):
            x = self.calc("FOXA1(Forkhead)", status)
            self.assertEqual(x["v03_reference_name_supported"], "FALSE")
            self.assertEqual(x["v03_native_family_for_name_only"], "")
            self.assertEqual(x["v03_claim_disposition"], "HOLD_CONFLICT_REQUIRES_REVIEW")

    def test_provisional_no_review_flag_does_not_imply_validated(self):
        x = self.calc("CTCF(Zf)")
        self.assertFalse(x["v03_family_claim_validated"] == "TRUE")
        self.assertNotEqual(x["v03_claim_disposition"], "SCIENTIFICALLY_VALIDATED")


class CliSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("MOTIF_AUDIT_TEST_TMP", str(ROOT)))
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def run_cli(self, raw, args=()):
        inp = self.path / "records.tsv"
        inp.write_text(raw, encoding="utf8")
        out = self.path / "output"
        p = subprocess.run([sys.executable, "-B", "-m", "homer_audit.cli", "annotate",
                            "--input", str(inp), "--outdir", str(out), "--summary", *args],
                           cwd=ROOT, text=True, capture_output=True)
        return p, out

    def read(self, file):
        with file.open(encoding="utf8", newline="") as f:
            return list(csv.DictReader(f, delimiter="\t"))

    def test_evidence_separated_and_q_sums(self):
        p, out = self.run_cli(
            "motif\tqvalue\nCEBPA(bZIP)\t0.001\nSRF(MADS)\t0.002\n"
            "ETS(ETS)\t0.003\nCTCF(Zf)\t0.020\nATF6(bZIP)\t0.8\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        annotated = self.read(out / "annotated.tsv")
        self.assertEqual(len(annotated), 5)
        self.assertEqual(annotated[0]["v03_reference_name_supported"], "TRUE")
        self.assertEqual(annotated[2]["v03_reference_name_supported"], "FALSE")
        self.assertTrue(all(r["v03_family_claim_validated"] == "FALSE" for r in annotated))
        old = self.read(out / "summary.tsv")
        evidence = self.read(out / "summary_evidence.tsv")
        restricted = self.read(out / "summary_restricted_name_metadata.tsv")
        self.assertEqual(sum(int(r["significant_motif_record_count"]) for r in old), 4)
        self.assertEqual(sum(int(r["significant_motif_record_count"]) for r in evidence), 4)
        self.assertEqual(sum(int(r["significant_motif_record_count"]) for r in restricted), 2)
        self.assertEqual(set(r["v03_tf_name_candidate"] for r in restricted), {"CEBPA", "SRF"})
        self.assertEqual({r["interpretation_scope"] for r in restricted},
                         {"TF_NAME_METADATA_ONLY_NO_PWM_OR_BINDING_PROOF"})
        audit = json.loads((out / "audit.json").read_text())
        self.assertEqual(audit["version"], "0.3.0-rc2")
        self.assertEqual(audit["rc2_reference_name_supported_count"], 2)
        self.assertEqual(audit["rc2_scientifically_validated_motif_family_claims"], 0)

    def test_reference_disagreement_excluded_from_restricted_summary(self):
        ref = self.path / "ref.tsv"
        # This is a synthetic user reference: the mismatch must block the native-name summary.
        ref.write_text("motif_core\treference_family_label\tnative_tf_family\tsource_database\t"
                       "source_release\tsource_record_id\tmapping_status\tevidence_link\tmapping_note\n"
                       "FOXA1(Forkhead)\tIncorrectFamily\tFOX\tTEST\t1\tTEST1\tapproved\t"
                       "https://example.org/record\tSynthetic conflict\n", encoding="utf8")
        p, out = self.run_cli("motif\tqvalue\nFOXA1(Forkhead)\t0.01\n", ("--reference-table", str(ref)))
        self.assertEqual(p.returncode, 0, p.stderr)
        a = self.read(out / "annotated.tsv")[0]
        self.assertEqual(a["v03_reference_name_supported"], "FALSE")
        self.assertEqual(a["v03_claim_disposition"], "HOLD_CONFLICT_REQUIRES_REVIEW")
        self.assertEqual(self.read(out / "summary_restricted_name_metadata.tsv"), [])
        self.assertEqual(self.read(out / "summary_evidence.tsv")[0]["v03_review_action"], "REVIEW_REQUIRED")

    def test_source_group_by_keeps_evidence_counts(self):
        p, out = self.run_cli("group\tmotif\tqvalue\nA\tFOXA1(Forkhead)\t0.01\nB\tETS(ETS)\t0.01\n",
                              ("--group-by", "group"))
        self.assertEqual(p.returncode, 0, p.stderr)
        s = self.read(out / "summary_evidence.tsv")
        self.assertEqual({r["group"] for r in s}, {"A", "B"})

    def test_refuses_overwrite_of_all_rc2_outputs(self):
        p, out = self.run_cli("motif\tqvalue\nETS(ETS)\t0.01\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        p2 = subprocess.run([sys.executable, "-B", "-m", "homer_audit.cli", "annotate",
                              "--input", str(self.path / "records.tsv"), "--outdir", str(out), "--summary"],
                            cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p2.returncode, 2)
        self.assertIn("Output already exists", p2.stderr)
