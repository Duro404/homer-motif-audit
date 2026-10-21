"""RC2 interpretation guard: separate lexical labels, reference metadata, and proof.

No emitted field in this module proves PWM identity or TF occupancy.
Review triggers are not equivalent to biological approval/rejection.
"""
from __future__ import annotations

from typing import Dict

CLAIM_FIELDS = [
    "v03_annotation_origin", "v03_metadata_evidence_scope",
    "v03_native_family_for_name_only", "v03_reporting_group_name_only",
    "v03_reference_name_supported", "v03_family_claim_validated",
    "v03_claim_disposition", "v03_review_action",
]


def claim_fields(semantic: Dict[str, str], reference_concordance: str) -> Dict[str, str]:
    """Interpret a semantic result conservatively after reference-table conflict gates.

    Crucially, a no-review-needed record is not a biologically approved model.
    """
    name_status = semantic["v03_name_mapping_status"]
    level = semantic["v03_label_level"]
    review = semantic["v03_review_required"] == "TRUE"
    ref_conflict = reference_concordance in {
        "SELF_REPORTED_LABEL_DIFFERS", "PENDING_MANUAL_REVIEW"
    }
    supported = (
        name_status == "TF_NAME_METADATA_CLASSIFICATION_SUPPORTED"
        and not ref_conflict
        and level == "TF_SYMBOL_WITH_RESTRICTED_JASPAR_NAME_CROSSWALK"
        and not review
    )
    if ref_conflict or name_status == "LEGACY_LABEL_CONFLICT":
        origin = "REFERENCE_OR_LABEL_CONFLICT"
        scope = "WITHHELD_UNVERIFIED_REFERENCE_CONFLICT"
        disposition = "HOLD_CONFLICT_REQUIRES_REVIEW"
    elif supported:
        origin = "RESTRICTED_JASPAR_2026_TF_NAME_METADATA"
        scope = "TF_NAME_CLASS_FAMILY_CROSSWALK_ONLY"
        disposition = "NAME_METADATA_SUPPORTED_MOTIF_MODEL_UNVERIFIED"
    elif level in {
        "COMPOSITE_OR_DIMER_MODEL", "FUSION_OR_CHIMERIC_MODEL",
        "MULTI_PARTNER_MOTIF_GROUP", "MULTI_SUBUNIT_COMPLEX"
    }:
        origin = "HOMER_MODEL_NAME_INTERPRETATION"
        scope = "PARTNERS_OR_COMPONENTS_NOT_VERIFIED"
        disposition = "HOLD_AMBIGUOUS_MODEL_OR_COMPLEX"
    elif level == "BROAD_FAMILY_LABEL":
        origin = "GENERIC_HOMER_FAMILY_LABEL_NO_TF_IDENTITY"
        scope = "TF_MEMBER_NOT_IDENTIFIED"
        disposition = "HOLD_GENERIC_FAMILY_LABEL"
    elif level == "MEMBER_EXCEPTION_HOLD":
        origin = "HOMER_MODEL_NAME_INTERPRETATION"
        scope = "MEMBER_EXCEPTION_NOT_APPROVED"
        disposition = "HOLD_MEMBER_EXCEPTION"
    elif level == "EXACT_TF_SYMBOL":
        origin = "SPECIFIC_SYMBOL_WITHOUT_NATIVE_DB_CROSSWALK"
        scope = "TF_SYMBOL_NAME_ONLY"
        disposition = "PROVISIONAL_MOTIF_MODEL_NOT_VALIDATED"
    else:
        origin = "LEGACY_NAME_RULE_PROVISIONAL"
        scope = "NO_NATIVE_FAMILY_EVIDENCE_FOR_THIS_MOTIF"
        disposition = "PROVISIONAL_MOTIF_MODEL_NOT_VALIDATED"

    return {
        "v03_annotation_origin": origin,
        "v03_metadata_evidence_scope": scope,
        "v03_native_family_for_name_only": semantic["v03_reference_tf_family"] if supported else "",
        "v03_reporting_group_name_only": semantic["v03_display_group"] if supported else "",
        "v03_reference_name_supported": "TRUE" if supported else "FALSE",
        "v03_family_claim_validated": "FALSE",
        "v03_claim_disposition": disposition,
        "v03_review_action": "REVIEW_REQUIRED" if review else "NO_ADDITIONAL_REVIEW_TRIGGER_NOT_AN_APPROVAL",
    }
