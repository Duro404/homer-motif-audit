import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homer_audit.core import annotate, core_parts, load_rules, load_curated

ROOT = Path(__file__).resolve().parents[1]


class NameRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()

    def a(self, name):
        return annotate(name, self.rules, {})

    def test_ap1_source_text_does_not_override_name(self):
        name = 'AP-1(bZIP)/PU.1-ChIP-Seq'
        self.assertEqual(self.a(name).family_label, 'AP-1/bZIP')
        self.assertEqual(self.a(name).evidence_method, 'name_rule')

    def test_fosl_batf_name_rule_regression(self):
        for name in ('FOSL2(bZIP)', 'BATF(bZIP)', 'JDP2(bZIP)'):
            self.assertEqual(self.a(name).family_label, 'AP-1/bZIP')

    def test_batf2_name_rule_regression(self):
        self.assertEqual(self.a('BATF2(bZIP)').family_label, 'AP-1/bZIP')

    def test_uncertain_atf_review_required(self):
        val = self.a('ATF6(bZIP)')
        self.assertEqual(val.family_label, 'Other bZIP')
        self.assertTrue(val.review_required)

    def test_common_motif_names(self):
        cases = {
            'MEF2A(MADS)': 'MEF2/MADS', 'SRF(MADS)': 'SRF/MADS',
            'CEBPA(bZIP)': 'CEBP/bZIP', 'C/EBPG(bZIP)/Source': 'CEBP/bZIP', 'TBX5(T-box)': 'T-box',
            'MYOG(bHLH)': 'bHLH/E-box', 'MYOD1(bHLH)': 'bHLH/E-box',
            'TEAD1(TEA)': 'TEAD', 'ETS:RUNX(ETS,Runt)': 'Composite ETS/RUNX',
            'PU.1(ETS)/FOS-source': 'ETS', 'FOXA1(Forkhead)': 'FOX',
            'SOX2(HMG)': 'SOX', 'ATF3(bZIP)': 'Other bZIP',
            'NFAT:AP1(bZIP)': 'Composite NFAT/AP-1',
            'CompletelyUnknown': 'Unclassified',
            'SomeName(RRM)': 'RNA-binding/non-TF',
        }
        for name, fam in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.a(name).family_label, fam)

    def test_unclassified_and_core_splitting(self):
        self.assertEqual(core_parts('FOXG1(HMG)/PU.1_Source'), ('FOXG1(HMG)', 'FOXG1', 'HMG'))
        self.assertTrue(self.a('UnknownNoTag').review_required)
        self.assertTrue(self.a('').review_required)

    def test_mapping_precedence_with_ref(self):
        with tempfile.TemporaryDirectory(dir=os.getenv('MOTIF_AUDIT_TEST_TMP', str(ROOT))) as d:
            path = Path(d) / 'curated.tsv'
            path.write_text('motif_core\tfamily\tsource_reference\tcurator_note\n'
                            'UNKNOWNFACTOR(bZIP)\tOther bZIP\tDOI:example\tuser supplied\n')
            a = annotate('UnknownFactor(bZIP)/some_source', self.rules, load_curated(path))
            self.assertEqual(a.evidence_method, 'user_curated_mapping')
            self.assertTrue(a.review_required)

    def test_mapping_rejects_duplicate(self):
        with tempfile.TemporaryDirectory(dir=os.getenv('MOTIF_AUDIT_TEST_TMP', str(ROOT))) as d:
            path = Path(d) / 'curated.tsv'
            path.write_text('motif_core\tfamily\tsource_reference\tcurator_note\n'
                            'AP-1\tA\tref1\t\n'
                            'ap-1\tB\tref2\t\n')
            with self.assertRaises(ValueError):
                load_curated(path)


class CLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getenv('MOTIF_AUDIT_TEST_TMP', str(ROOT)))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = [sys.executable, '-B', '-m', 'homer_audit.cli', 'annotate']

    def run_cli(self, path, out, *extra):
        return subprocess.run(self.script + ['--input', str(path), '--outdir', str(out), *extra],
                              cwd=ROOT, text=True, capture_output=True)

    def test_header_only(self):
        inp = self.root / 'empty.tsv'
        inp.write_text('motif\tset\ttissue\tqvalue\n')
        out = self.root / 'out'
        run = self.run_cli(inp, out, '--summary', '--group-by', 'set,tissue')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len((out/'annotated.tsv').read_text().splitlines()), 1)
        self.assertEqual(len((out/'summary.tsv').read_text().splitlines()), 1)

    def test_summary_count_and_order(self):
        inp = ROOT/'examples'/'synthetic_motifs.tsv'
        out = self.root/'out'
        run = self.run_cli(inp, out, '--summary', '--group-by', 'set,tissue')
        self.assertEqual(run.returncode, 0, run.stderr)
        with (out/'summary.tsv').open() as f:
            results = list(csv.DictReader(f, delimiter='\t'))
        with inp.open() as f:
            original = list(csv.DictReader(f, delimiter='\t'))
        self.assertEqual(sum(int(r['significant_motif_record_count']) for r in results),
                         sum(float(r['qvalue']) < 0.05 for r in original))
        self.assertFalse(any('0.0501' in str(r) for r in results))
        self.assertTrue(any(r['family_label'] == 'AP-1/bZIP' for r in results))
        self.assertEqual(self.run_cli(inp, out, '--summary').returncode, 2)

    def test_missing_q_column_fails_before_writes(self):
        inp = self.root/'noq.tsv'
        inp.write_text('motif\nMEF2A(MADS)\n')
        out = self.root/'out'
        run = self.run_cli(inp, out, '--summary')
        self.assertEqual(run.returncode, 2)
        self.assertFalse(out.exists())

    def test_invalid_q_fails_before_writes(self):
        inp = self.root/'badq.tsv'
        inp.write_text('motif\tqvalue\nFOXA1\tNaN\n')
        out = self.root/'out'
        run = self.run_cli(inp, out, '--summary')
        self.assertEqual(run.returncode, 2)
        self.assertFalse(out.exists())

    def test_missing_motif_column(self):
        inp = self.root/'bad.tsv'
        inp.write_text('gene\tqvalue\nFOXA1\t0.1\n')
        out = self.root/'out'
        self.assertEqual(self.run_cli(inp, out).returncode, 2)
        self.assertFalse(out.exists())

    def test_raw_homer_header(self):
        inp = self.root/'raw.tsv'
        inp.write_text('Motif Name\tq-value (Benjamini)\nFOXA1(Forkhead)/X\t0.001\n')
        out = self.root/'out'
        run = self.run_cli(inp, out, '--summary')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('FOX', (out/'annotated.tsv').read_text())

    def test_malformed_tsv(self):
        inp = self.root/'malformed.tsv'
        inp.write_text('motif\tqvalue\nFOXA1\n')
        out = self.root/'out'
        self.assertEqual(self.run_cli(inp, out).returncode, 2)
        self.assertFalse(out.exists())

if __name__ == '__main__':
    unittest.main()
