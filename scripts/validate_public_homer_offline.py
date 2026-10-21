#!/usr/bin/env python3
"""Offline integration of RC2 on 3 publicly hosted HOMER tables.

No downloads. Pinned content hashes. The checks are software-behavior regression
checks, not independently labeled TF-classification accuracy or PWM validation.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,subprocess,sys
from collections import Counter
from pathlib import Path

SOURCES=[
 ('qbio_2018','2d47508cebdfb496d2a62f560c8f2785493acf1b',364,15),
 ('plate_scATAC_cluster1','c421ce4a78273910db478ee7fab126c1c8286b69',364,15),
 ('fetal_brain_ctcf_topic9','07ba17ad46a4b27dac27958186c154f93af9469c',440,16),
]

def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git_blob(data:bytes):return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
def records(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter='\t'))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source-dir',type=Path,required=True,help='Cache containing pinned public *_knownResults.txt originals')
 p.add_argument('--outdir',type=Path,required=True,help='New output directory (must not already exist)')
 p.add_argument('--tool-root',type=Path,default=Path(__file__).resolve().parents[1])
 a=p.parse_args()
 src=a.source_dir.resolve();out=a.outdir.resolve();tool=a.tool_root.resolve()
 if out == src or out == tool:
  p.error('Output directory cannot equal source or tool directory')
 if out.exists():p.error('Output directory exists. Choose a new one; no overwrites permitted.')
 if not (tool/'homer_audit/claims.py').is_file():p.error('RC2 candidate tool missing')
 # Check all inputs before writing anything.
 for dataset,blob,_,_ in SOURCES:
  f=src/(dataset+'_knownResults.txt')
  if not f.is_file() or git_blob(f.read_bytes())!=blob:
   p.error(f'Pinned public source missing or hash mismatch: {f}')
 out.mkdir(parents=True)
 (out/'_tmp').mkdir()
 env=dict(os.environ,TMPDIR=str(out/'_tmp'),PYTHONDONTWRITEBYTECODE='1')
 summaries=[];total=Counter()
 for ds,blob,n_expected,n_hits in SOURCES:
  f=src/(ds+'_knownResults.txt');run=out/('annotated_'+ds)
  command=[sys.executable,'-B','-m','homer_audit.cli','annotate','--input',str(f),
    '--input-format','homer-known','--outdir',str(run),'--summary']
  z=subprocess.run(command,cwd=tool,env=env,text=True,capture_output=True)
  if z.returncode!=0:raise RuntimeError(f'CLI failed for {ds}: {z.stderr.strip()[:1000]}')
  rs=records(run/'annotated.tsv');audit=json.loads((run/'audit.json').read_text())
  if len(rs)!=n_expected or audit['rows']!=n_expected:raise RuntimeError(f'Unexpected {ds} record count')
  observed=Counter(x['v03_label_level'] for x in rs)
  checked=sum(x['v03_name_mapping_status']=='TF_NAME_METADATA_CLASSIFICATION_SUPPORTED' for x in rs)
  if checked!=n_hits:raise RuntimeError(f'{ds}: name crosswalk count regression {checked}!={n_hits}')
  qsig=sum(float(x['q-value (Benjamini)'])<0.05 for x in rs)
  # RC2 scientific scope checks, distinct from lexical concordance.
  scope_counts=Counter(x['v03_claim_disposition'] for x in rs)
  supported=[x for x in rs if x['v03_reference_name_supported']=='TRUE']
  restricted=records(run/'summary_restricted_name_metadata.tsv')
  evidence=records(run/'summary_evidence.tsv')
  summary_legacy=records(run/'summary.tsv')
  def c(rows):return sum(int(x['significant_motif_record_count']) for x in rows)
  n_supported_sig=sum(x['v03_reference_name_supported']=='TRUE' and float(x['q-value (Benjamini)'])<0.05 for x in rs)
  if len(supported)!=n_hits or c(restricted)!=n_supported_sig or c(evidence)!=qsig or c(summary_legacy)!=qsig:
   raise RuntimeError(f'{ds}: evidence summary partition mismatch')
  if any(x['v03_family_claim_validated']!='FALSE' for x in rs):
   raise RuntimeError(f'{ds}: unsupported scientific validation claim')
  if any(x['v03_review_action']=='NO_ADDITIONAL_REVIEW_TRIGGER_NOT_AN_APPROVAL' and x['v03_review_required']=='TRUE' for x in rs):
   raise RuntimeError(f'{ds}: review action inconsistent with flag')
  if any(x['v03_reference_name_supported']=='FALSE' and x['v03_native_family_for_name_only'] for x in rs):
   raise RuntimeError(f'{ds}: native family leaked into unapproved record')
  summary={'dataset':ds,'rows':len(rs),'source_git_blob_sha1':blob,'source_sha256':sha(f),
   'annotated_sha256':sha(run/'annotated.tsv'),'q_lt_0_05':qsig,
   'restricted_name_metadata_hits':checked,
   'semantic_level_counts':dict(sorted(observed.items())),
   'claim_disposition_counts':dict(sorted(scope_counts.items())),
   'restricted_significant_record_hits':n_supported_sig,
   'evidence_summary_sha256':sha(run/'summary_evidence.tsv'),
   'restricted_summary_sha256':sha(run/'summary_restricted_name_metadata.tsv'),
   'review_required':sum(x['v03_review_required']=='TRUE' for x in rs),
   'generic_unreviewed':sum(x['motif_head'] in {'ETS','AP-1','NFY'} and x['v03_review_required']=='FALSE' for x in rs),
   'all_binding_proof_false':all(x['v03_tf_binding_proven']=='FALSE' for x in rs),
   'all_pwm_test_false':all(x['v03_pwm_identity_tested']=='FALSE' for x in rs),
   'all_family_claims_unvalidated':all(x['v03_family_claim_validated']=='FALSE' for x in rs)}
  if summary['generic_unreviewed'] or not summary['all_binding_proof_false'] or not summary['all_pwm_test_false'] or not summary['all_family_claims_unvalidated']:
   raise RuntimeError(f'Unsafe semantic assertion for {ds}')
  summaries.append(summary);total.update(observed)
  print('PASS',ds,'rows',len(rs),'name_only_hits',checked,'review',summary['review_required'],flush=True)
 report={'status':'PASS_PUBLIC_DATA_SOFTWARE_REGRESSION_ONLY_NOT_BIOLOGICAL_VALIDATION',
 'version':'0.3.0-rc2','source_files_verified':3,
 'motif_rows':sum(s['rows'] for s in summaries),
 'restricted_name_metadata_hits':sum(s['restricted_name_metadata_hits'] for s in summaries),
 'restricted_significant_record_hits':sum(s['restricted_significant_record_hits'] for s in summaries),
 'rc2_scientifically_validated_motif_family_claims':0,
 'semantic_level_counts':dict(sorted(total.items())),
 'total_v03_review_required':sum(s['review_required'] for s in summaries),
 'datasets':summaries,'interpretation':'No PWM identity or TF binding proven. Public HOMER dictionaries overlap.'}
 (out/'V03_RC2_PUBLIC_INTEGRATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('REPORT',out/'V03_RC2_PUBLIC_INTEGRATION.json')

if __name__=='__main__':main()
