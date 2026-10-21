"""All fixtures in this test file are invented, not independent biological truths."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homer_audit.format_checks import detected_format
from homer_audit.reference import read_reference, compare_reference

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "examples" / "synthetic_reference_demo.tsv"
HOMER = ROOT / "examples" / "synthetic_knownResults.txt"


class FormatTests(unittest.TestCase):
    def test_homer_detection(self):
        cols = ["Motif Name", "Consensus", "P-value", "Log P-value", "q-value (Benjamini)"]
        self.assertEqual(detected_format(cols, "auto"), "homer-known")
        self.assertEqual(detected_format(cols, "homer-known"), "homer-known")

    def test_not_homer_without_consensus(self):
        self.assertEqual(detected_format(["Motif Name", "q-value (Benjamini)"], "auto"), "generic-tsv")
        with self.assertRaises(ValueError):
            detected_format(["Motif Name", "q-value (Benjamini)"], "homer-known")

    def test_generic_mode(self):
        self.assertEqual(detected_format(["motif", "qvalue"], "generic-tsv"), "generic-tsv")


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getenv("MOTIF_AUDIT_TEST_TMP", str(ROOT)))
        self.addCleanup(self.tmp.cleanup)
        self.tmpdir = Path(self.tmp.name)

    def test_pending_and_approved(self):
        refs = read_reference(REF)
        self.assertEqual(len(refs), 3)
        self.assertEqual(compare_reference("FOXA1(Forkhead)", "FOX", refs, True)["reference_concordance"],
                         "PENDING_MANUAL_REVIEW")
        self.assertEqual(compare_reference("C/EBPG(bZIP)", "CEBP/bZIP", refs, True)["reference_concordance"],
                         "SELF_REPORTED_LABEL_AGREES")
        self.assertEqual(compare_reference("ATF6(bZIP)", "Other bZIP", refs, True)["reference_concordance"],
                         "SELF_REPORTED_LABEL_DIFFERS")

    def test_missing_and_unsupplied(self):
        refs = read_reference(REF)
        self.assertEqual(compare_reference("MEF2A", "MEF2/MADS", refs, True)["reference_concordance"],
                         "NO_EXACT_MATCH")
        self.assertEqual(compare_reference("MEF2A", "MEF2/MADS", refs, False)["reference_concordance"],
                         "NOT_SUPPLIED")

    def test_duplicate_rejected(self):
        content = REF.read_text().replace("C/EBPG(bZIP)", "foxa1(forkhead)")
        path = self.tmpdir / "dup.tsv"
        path.write_text(content)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_reference(path)

    def test_invalid_status(self):
        path = self.tmpdir / "bad.tsv"
        path.write_text(REF.read_text().replace("\tpending\t", "\tconfirmed_by_tool\t"))
        with self.assertRaisesRegex(ValueError, "mapping_status"):
            read_reference(path)

    def test_missing_metadata(self):
        path = self.tmpdir / "empty.tsv"
        path.write_text(REF.read_text().replace("FAKE_001", ""))
        with self.assertRaisesRegex(ValueError, "Missing required"):
            read_reference(path)

    def test_only_header(self):
        path = ROOT / "examples" / "reference_crosswalk_template.tsv"
        self.assertEqual(read_reference(path), {})

    def test_extra_column_rejected(self):
        path = self.tmpdir / "extra.tsv"
        path.write_text(REF.read_text().replace("mapping_note\n", "mapping_note\tnew\n", 1))
        with self.assertRaisesRegex(ValueError, "exactly"):
            read_reference(path)


class CliV02Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getenv("MOTIF_AUDIT_TEST_TMP", str(ROOT)))
        self.addCleanup(self.tmp.cleanup)
        self.t = Path(self.tmp.name)

    def run_annotate(self, inp, out, *opts):
        return subprocess.run([sys.executable, "-B", "-m", "homer_audit.cli", "annotate",
                               "--input", str(inp), "--outdir", str(out), *opts],
                              cwd=ROOT, text=True, capture_output=True)

    def test_realistic_homer_format_q_strict(self):
        out = self.t / "out"
        p = self.run_annotate(HOMER, out, "--summary", "--input-format", "homer-known")
        self.assertEqual(p.returncode, 0, p.stderr)
        audit = json.loads((out / "audit.json").read_text())
        self.assertEqual(audit["input_format"], "homer-known")
        self.assertEqual(audit["rows"], 5)
        self.assertEqual(audit["significant_motif_record_count"], 4)
        with (out / "annotated.tsv").open() as f:
            records = list(csv.DictReader(f, delimiter="\t"))
        self.assertEqual(len(records), 5)
        self.assertEqual(records[1]["family_label"], "AP-1/bZIP")
        self.assertEqual(records[3]["motif_core"], "C/EBPG(bZIP)")
        self.assertEqual(records[4]["family_label"], "Unclassified")
        self.assertEqual(records[2]["reference_concordance"], "NOT_SUPPLIED")

    def test_reference_concordance(self):
        out = self.t / "with_ref"
        p = self.run_annotate(HOMER, out, "--reference-table", str(REF), "--summary")
        self.assertEqual(p.returncode, 0, p.stderr)
        audit = json.loads((out / "audit.json").read_text())
        self.assertFalse(audit["reference_source_verified_by_software"])
        self.assertEqual(audit["reference_comparison_counts"], {
            "NO_EXACT_MATCH": 2, "PENDING_MANUAL_REVIEW": 1,
            "SELF_REPORTED_LABEL_AGREES": 1, "SELF_REPORTED_LABEL_DIFFERS": 1
        })
        self.assertTrue((out / "reference_comparison.tsv").exists())
        self.assertEqual(len((out / "reference_comparison.tsv").read_text().splitlines()), 6)

    def test_bad_known_headers_fail_without_creating_output(self):
        bad = self.t / "bad.tsv"
        bad.write_text("Motif Name\tq-value (Benjamini)\nFOXA1\t0.03\n")
        out = self.t / "out"
        p = self.run_annotate(bad, out, "--input-format", "homer-known")
        self.assertEqual(p.returncode, 2)
        self.assertFalse(out.exists())

    def test_invalid_reference_blocks_writes(self):
        badref = self.t / "badref.tsv"
        badref.write_text("motif_core\treference_family_label\nfoo\tbar\n")
        out = self.t / "out"
        p = self.run_annotate(HOMER, out, "--reference-table", str(badref))
        self.assertEqual(p.returncode, 2)
        self.assertFalse(out.exists())

    def test_bad_q_rejected(self):
        bad = self.t / "bad.tsv"
        bad.write_text(HOMER.read_text().replace("\t0.001\t", "\tNaN\t"))
        p = self.run_annotate(bad, self.t / "out", "--summary")
        self.assertEqual(p.returncode, 2)
        self.assertFalse((self.t / "out").exists())

    def test_q_nan_threshold_rejected(self):
        p = self.run_annotate(HOMER, self.t / "out", "--summary", "--q-threshold", "nan")
        self.assertEqual(p.returncode, 2)
        self.assertFalse((self.t / "out").exists())

    def test_deterministic_output(self):
        out1, out2 = self.t / "one", self.t / "two"
        a = self.run_annotate(HOMER, out1, "--reference-table", str(REF), "--summary")
        b = self.run_annotate(HOMER, out2, "--reference-table", str(REF), "--summary")
        self.assertEqual((a.returncode, b.returncode), (0, 0), (a.stderr, b.stderr))
        for fname in ["annotated.tsv", "summary.tsv", "reference_comparison.tsv", "audit.json"]:
            self.assertEqual((out1 / fname).read_bytes(), (out2 / fname).read_bytes(), fname)

    def test_bom_and_crlf(self):
        path = self.t / "bom.tsv"
        path.write_bytes(b"\xef\xbb\xbfMotif Name\tConsensus\tq-value (Benjamini)\r\nFOXA1(Forkhead)/S\tAAA\t0.02\r\n")
        p = self.run_annotate(path, self.t / "out", "--summary", "--input-format", "homer-known")
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_check_reference_cli(self):
        run = subprocess.run([sys.executable, "-B", "-m", "homer_audit.cli", "check-reference",
                              "--reference-table", str(REF)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(json.loads(run.stdout)["external_records_verified"])

    def test_overwrite_input_guard(self):
        same_input = self.t / "annotated.tsv"
        same_input.write_bytes(HOMER.read_bytes())
        p = self.run_annotate(same_input, self.t, "--overwrite")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(same_input.read_bytes(), HOMER.read_bytes())


if __name__ == "__main__":
    unittest.main()

class ExternalConflictAuditTests(unittest.TestCase):
    def test_conflict_sets_manual_review(self):
        with tempfile.TemporaryDirectory(dir=os.getenv('MOTIF_AUDIT_TEST_TMP', str(ROOT))) as d:
            out = Path(d) / 'out'
            r = subprocess.run([sys.executable, '-B', '-m', 'homer_audit.cli', 'annotate',
                               '--input', str(HOMER), '--outdir', str(out),
                               '--reference-table', str(REF)], cwd=ROOT,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with (out / 'annotated.tsv').open() as f:
                by_name = {row['motif_core']: row
                           for row in csv.DictReader(f, delimiter='\t')}
            self.assertEqual(by_name['ATF6(bZIP)']['review_required'], 'TRUE')
            self.assertIn('reference_label_conflict', by_name['ATF6(bZIP)']['review_reason'])
            self.assertEqual(by_name['FOXA1(Forkhead)']['review_required'], 'TRUE')
            self.assertIn('reference_mapping_pending', by_name['FOXA1(Forkhead)']['review_reason'])
            self.assertEqual(by_name['C/EBPG(bZIP)']['reference_evidence_link'], 'NOT_A_REAL_DATABASE_LINK')
