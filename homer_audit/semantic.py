"""Conservative name semantics. This DOES NOT test PWMs or prove binding."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from .core import Annotation, core_parts

REFERENCE = Path(__file__).with_name('reference_name_rules_v04.tsv')
V03_FIELDS = ['v03_label_level','v03_tf_name_candidate','v03_display_group',
  'v03_reference_tf_class','v03_reference_tf_family','v03_reference_rule_id',
  'v03_reference_matrix_ids','v03_reference_source','v03_name_mapping_status',
  'v03_review_required','v03_review_reason','v03_review_status',
  'v03_pwm_identity_tested','v03_tf_binding_proven']

@dataclass(frozen=True)
class NameCrosswalk:
    rule_id: str
    tf_name: str
    class_name: str
    family: str
    display: str
    legacy_label: str
    matrix_ids: str
    source: str


def load_crosswalk(path:Path=REFERENCE):
    if not path.is_file():raise ValueError('Missing bundled name-only crosswalk')
    with path.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f,delimiter='\t')
        need={'rule_id','eligible_tf_exact','jaspar_class','jaspar_family',
          'display_label','legacy_label','matched_matrix_ids','source_reference',
          'scientific_review_state'}
        if not rd.fieldnames or not need.issubset(rd.fieldnames):raise ValueError('Invalid crosswalk TSV schema')
        out={}; seen=set()
        for r in rd:
            rid=r['rule_id'].strip()
            if not rid or rid in seen:raise ValueError('Duplicate reference rule')
            seen.add(rid)
            if r['scientific_review_state']!='SCIENTIFICALLY_ACCEPTED_NATIVE_METADATA_ONLY':
                raise ValueError('Rule does not have limited scientific metadata approval')
            if not all(r[k].strip() for k in need):raise ValueError('Incomplete crosswalk row')
            for name in r['eligible_tf_exact'].split(';'):
                name=name.strip().upper()
                if not name or name in out:raise ValueError('Duplicate or empty TF in crosswalk')
                out[name]=NameCrosswalk(rid,name,r['jaspar_class'],r['jaspar_family'],
                  r['display_label'],r['legacy_label'],r['matched_matrix_ids'],r['source_reference'])
    if len(seen)!=10:raise ValueError('This candidate expects exactly 10 limited rules')
    return out


def semantic_fields(name:str, a:Annotation, reference):
    _,head,_=core_parts(name)
    out={k:'' for k in V03_FIELDS}
    out.update(v03_label_level='LEGACY_PROVISIONAL_NAME_ANNOTATION',
      v03_name_mapping_status='NO_APPROVED_EXACT_TF_CROSSWALK',
      v03_review_required='TRUE' if a.review_required else 'FALSE',
      v03_review_reason='LEGACY_NAME_RULE_NOT_SCIENTIFICALLY_APPROVED',
      v03_review_status='PENDING_NOT_NATIVE_REFERENCE_APPROVED',
      v03_pwm_identity_tested='FALSE',v03_tf_binding_proven='FALSE')
    # The order is intentionally conservative: fusion/composite before specific TF rules.
    if 'FUSION' in head or 'CHIMER' in head:
        out.update(v03_label_level='FUSION_OR_CHIMERIC_MODEL',
          v03_review_required='TRUE',v03_review_reason='FUSION_IDENTITY_UNRESOLVED')
    elif ':' in head:
        out.update(v03_label_level='COMPOSITE_OR_DIMER_MODEL',
          v03_review_required='TRUE',v03_review_reason='COMPOSITE_PARTNERS_UNRESOLVED')
    elif head in {'ATF2','ATF3','ATF6','BATF'}:
        out.update(v03_label_level='MEMBER_EXCEPTION_HOLD',
          v03_review_required='TRUE',v03_review_reason='ATF_BATF_EXCEPTION_NOT_APPROVED')
    elif head=='ETS':
        out.update(v03_label_level='BROAD_FAMILY_LABEL',v03_display_group='ETS',
          v03_review_required='TRUE',v03_review_reason='GENERIC_ETS_TF_UNSPECIFIED')
    elif head in {'AP-1','AP1'}:
        out.update(v03_label_level='MULTI_PARTNER_MOTIF_GROUP',v03_display_group='AP-1',
          v03_review_required='TRUE',v03_review_reason='AP1_PARTNERS_UNSPECIFIED')
    elif head in {'NFY','NF-Y'}:
        out.update(v03_label_level='MULTI_SUBUNIT_COMPLEX',v03_display_group='NF-Y',
          v03_review_required='TRUE',v03_review_reason='NFY_SUBUNIT_UNSPECIFIED')
    elif head=='CTCF':
        out.update(v03_label_level='EXACT_TF_SYMBOL',v03_tf_name_candidate='CTCF',
          v03_review_reason='SPECIFIC_NAME_NOT_BINDING_PROOF',
          v03_review_status='TF_NAME_ONLY_BINDING_NOT_PROVEN')
    elif head in reference:
        r=reference[head]
        conflict=(a.family_label!=r.legacy_label or a.evidence_method=='user_curated_mapping')
        out.update(v03_label_level='TF_SYMBOL_WITH_RESTRICTED_JASPAR_NAME_CROSSWALK',
          v03_tf_name_candidate=head,v03_display_group=r.display,
          v03_reference_tf_class=r.class_name,v03_reference_tf_family=r.family,
          v03_reference_rule_id=r.rule_id,v03_reference_matrix_ids=r.matrix_ids,
          v03_reference_source=r.source,
          v03_name_mapping_status='LEGACY_LABEL_CONFLICT' if conflict else 'TF_NAME_METADATA_CLASSIFICATION_SUPPORTED',
          v03_review_required='TRUE' if conflict or a.review_required else 'FALSE',
          v03_review_reason='LEGACY_REFERENCE_CONFLICT' if conflict else 'NAME_METADATA_ONLY_NOT_PWM',
          v03_review_status='PENDING_CONFLICT' if conflict else 'TF_NAME_CLASS_SUPPORTED_MOTIF_UNVERIFIED')
    return out
