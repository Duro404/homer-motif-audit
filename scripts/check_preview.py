#!/usr/bin/env python3
"""Local, offline, non-publishing source-review smoke test."""
from __future__ import annotations
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-q'],cwd=ROOT,env=env)
    if p.returncode:
        raise SystemExit('FAIL: unit tests')
    with tempfile.TemporaryDirectory(prefix='homer-audit-release-', dir=os.environ.get('TMPDIR') or None) as d:
        out=Path(d)/'results'
        p=subprocess.run([sys.executable,'-B','-m','homer_audit.cli','annotate',
                          '--input',str(ROOT/'examples/synthetic_knownResults.txt'),
                          '--input-format','homer-known','--outdir',str(out),'--summary'],
                         cwd=ROOT,env=env,text=True,capture_output=True)
        if p.returncode:
            raise SystemExit('FAIL: CLI smoke: '+p.stderr.strip())
        expected=['annotated.tsv','summary.tsv','summary_evidence.tsv',
                  'summary_restricted_name_metadata.tsv','audit.json']
        missing=[n for n in expected if not (out/n).is_file()]
        if missing:
            raise SystemExit(f'FAIL: missing outputs {missing}')
        r=json.loads((out/'audit.json').read_text(encoding='utf-8'))
        if r.get('rows')!=5 or r.get('rc2_scientifically_validated_motif_family_claims')!=0:
            raise SystemExit('FAIL: semantic audit invariant')
        print('PASS: unit tests, synthetic CLI, output files, conservative claims')
        print('LIMITATION: no original raw public dataset rerun; legal publication NOT approved')

if __name__=='__main__':
    main()
