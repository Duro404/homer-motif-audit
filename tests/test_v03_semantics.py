"""Synthetic v0.3 candidate safety checks, not independent motif biological validation."""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from homer_audit.core import annotate,load_rules
from homer_audit.semantic import load_crosswalk,semantic_fields

ROOT=Path(__file__).resolve().parents[1]

class SemanticTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=load_rules()
  cls.crosswalk=load_crosswalk()
 def test_10_rules_bounded(self):
  self.assertEqual({x.rule_id for x in self.crosswalk.values()}, {'R03','R08','R09','R10','R11','R12','R13','R14','R16','R17'})
 def sem(self,name):return semantic_fields(name,annotate(name,self.rules,{}),self.crosswalk)
 def test_approved_examples(self):
  for name,rid in [('CEBPA(bZIP)','R03'),('FOXA1(Forkhead)','R08'),('SOX9(HMG)','R09'),('MEF2A(MADS)','R10'),('SRF(MADS)','R11'),('GATA4(Zf)','R12'),('RUNX1(Runt)','R13'),('SMAD3','R14'),('TEAD4','R16'),('FLI1(ETS)','R17')]:
   with self.subTest(name=name):
    x=self.sem(name)
    self.assertEqual(x['v03_reference_rule_id'],rid)
    self.assertEqual(x['v03_name_mapping_status'],'TF_NAME_METADATA_CLASSIFICATION_SUPPORTED')
    self.assertEqual(x['v03_review_required'],'FALSE')
    self.assertEqual(x['v03_tf_binding_proven'],'FALSE')
    self.assertEqual(x['v03_pwm_identity_tested'],'FALSE')
 def test_name_whitelist_is_not_regex_family(self):
  for name in ['CEBPG(bZIP)','SOX2(HMG)','ETS3(ETS)','GATA3','ATF6(bZIP)']:
   with self.subTest(name=name):self.assertEqual(self.sem(name)['v03_reference_rule_id'],'')
 def test_generic(self):
  for name,lv in [('ETS(ETS)/Promoter/Homer','BROAD_FAMILY_LABEL'),('AP-1(bZIP)/test','MULTI_PARTNER_MOTIF_GROUP'),('NFY(CCAAT)/test','MULTI_SUBUNIT_COMPLEX')]:
   with self.subTest(name=name):
    a=self.sem(name);self.assertEqual(a['v03_label_level'],lv)
    self.assertEqual(a['v03_review_required'],'TRUE');self.assertEqual(a['v03_tf_name_candidate'],'')
 def test_ctcf_is_a_name_not_binding(self):
  x=self.sem('CTCF(Zf)/experiment');self.assertEqual(x['v03_label_level'],'EXACT_TF_SYMBOL')
  self.assertEqual(x['v03_tf_name_candidate'],'CTCF');self.assertEqual(x['v03_review_required'],'FALSE')
  self.assertEqual(x['v03_tf_binding_proven'],'FALSE')
 def test_composite_and_fusions_override_tag(self):
  for name,lv in [('ETS:RUNX(ETS,Runt)','COMPOSITE_OR_DIMER_MODEL'),('FOXA1:AR(Forkhead,NR)','COMPOSITE_OR_DIMER_MODEL'),('RAR:RXR(NR)','COMPOSITE_OR_DIMER_MODEL'),('ARNT:AHR(bHLH)','COMPOSITE_OR_DIMER_MODEL'),('EWS:FLI1-fusion(ETS)','FUSION_OR_CHIMERIC_MODEL'),('EWS:ERG-fusion(ETS)','FUSION_OR_CHIMERIC_MODEL')]:
   with self.subTest(name=name):
    x=self.sem(name);self.assertEqual(x['v03_label_level'],lv)
    self.assertEqual(x['v03_review_required'],'TRUE')
    self.assertFalse(x['v03_reference_rule_id'])
 def test_cebp_slash_parsing(self):
  a=self.sem('C/EBPG(bZIP)/Homer');self.assertEqual(a['v03_reference_rule_id'],'')
  self.assertEqual(a['v03_label_level'],'LEGACY_PROVISIONAL_NAME_ANNOTATION')
 def test_specific_member_exceptions(self):
  for n in ['ATF2(bZIP)','ATF3(bZIP)','ATF6(bZIP)','BATF(bZIP)']:
   with self.subTest(name=n):
    x=self.sem(n)
    self.assertEqual(x['v03_review_required'],'TRUE')
    self.assertEqual(x['v03_label_level'],'MEMBER_EXCEPTION_HOLD')
 def test_unverified_legacy_never_claims_crosswalk(self):
  a=self.sem('MYOG(bHLH)')
  self.assertEqual(a['v03_name_mapping_status'],'NO_APPROVED_EXACT_TF_CROSSWALK')
  self.assertEqual(a['v03_reference_tf_family'],'')
 def test_idempotence(self):
  self.assertEqual(self.sem('MEF2A(MADS)'),self.sem('MEF2A(MADS)'))
 def test_conflicting_user_override_does_not_silently_approve(self):
  from homer_audit.core import Annotation
  a=Annotation('FOXA1(Forkhead)','FOXA1','FORKHEAD','Unclassified','user_curated_mapping','CURATED',True,'manual_reference_review_required')
  x=semantic_fields('FOXA1(Forkhead)',a,self.crosswalk)
  self.assertEqual(x['v03_review_status'],'PENDING_CONFLICT')
  self.assertEqual(x['v03_review_required'],'TRUE')

class CliSemanticTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('MOTIF_AUDIT_TEST_TMP',str(ROOT)))
  self.addCleanup(self.temp.cleanup)
  self.base=Path(self.temp.name)
 def test_cli_realistic_field_gates_and_audit(self):
  inp=self.base/'input.tsv';inp.write_text('motif\tqvalue\nFOXA1(Forkhead)\t0.0001\nETS(ETS)\t0.0002\nBATF(bZIP)\t0.02\nCTCF(Zf)\t0.2\nEWS:FLI1-fusion(ETS)\t0.4\n',encoding='utf8')
  out=self.base/'out'
  res=subprocess.run([sys.executable,'-B','-m','homer_audit.cli','annotate','--input',str(inp),'--outdir',str(out),'--summary'],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(res.returncode,0,res.stderr)
  with (out/'annotated.tsv').open(newline='',encoding='utf8') as f:rows=list(csv.DictReader(f,delimiter='\t'))
  self.assertEqual(len(rows),5)
  self.assertEqual(rows[0]['v03_reference_rule_id'],'R08')
  self.assertEqual(rows[1]['v03_review_required'],'TRUE')
  self.assertEqual(rows[2]['v03_review_required'],'TRUE')
  self.assertEqual(rows[3]['v03_review_required'],'FALSE')
  self.assertEqual(rows[4]['v03_label_level'],'FUSION_OR_CHIMERIC_MODEL')
  audit=json.loads((out/'audit.json').read_text())
  self.assertEqual(audit['v03_review_required_count'],3)
  self.assertEqual(audit['v03_approved_tf_name_metadata_hits'],1)
  self.assertFalse(audit['v03_tf_binding_proven'])
 def test_v03_input_columns_cannot_override(self):
  inp=self.base/'input.tsv';inp.write_text('motif\tv03_review_status\nFOXA1\tAPPROVED\n')
  res=subprocess.run([sys.executable,'-B','-m','homer_audit.cli','annotate','--input',str(inp),'--outdir',str(self.base/'out')],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(res.returncode,2);self.assertFalse((self.base/'out').exists())

class ReferenceConflictGateTests(unittest.TestCase):
 def test_pending_reference_cannot_be_overridden_by_native_name_crosswalk(self):
  import subprocess,csv,sys,tempfile,os
  from pathlib import Path
  root=Path(__file__).resolve().parents[1]
  inp=root/'examples/synthetic_knownResults.txt'
  reference=root/'examples/synthetic_reference_demo.tsv'
  with tempfile.TemporaryDirectory(dir=os.environ.get('MOTIF_AUDIT_TEST_TMP',str(root))) as d:
   out=Path(d)/'out'
   p=subprocess.run([sys.executable,'-B','-m','homer_audit.cli','annotate','--input',str(inp),
      '--outdir',str(out),'--reference-table',str(reference)],cwd=root,capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   with (out/'annotated.tsv').open(encoding='utf8',newline='') as f:rs=list(csv.DictReader(f,delimiter='\t'))
   fox=next(x for x in rs if x['motif_head']=='FOXA1')
   self.assertEqual(fox['v03_review_required'],'TRUE')
   self.assertEqual(fox['v03_review_status'],'PENDING_REFERENCE_TABLE_CONFLICT')
