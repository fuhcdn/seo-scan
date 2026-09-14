"""red_team_rubric — anchored 0-5 rubric owned by the Red-Team Scoring Auditor.
Every criterion has written anchors. 5 requires independently corroborated,
unambiguous evidence; if a meaningful one-point improvement exists, 5 is not
allowed. Separated from the generator and strict reviewer by design."""

RUBRIC_SRC = {
    "evidence_accuracy": {
        "c1_direct_observation_tied_to_customer_url": {
            "0": "no customer-owned URL or fabricated claim",
            "1": "URL exists but no direct observation / claim unsupported",
            "2": "observation generic, stale, incomplete or weakly tied to recommendation",
            "3": "specific observation + recommendation exist; limitation/causal link incomplete",
            "4": "specific direct observation, buyer question, gap, mechanism, limitation present & consistent",
            "5": "level 4 + corroborated by current structured evidence, no meaningful ambiguity"},
        "c2_evidence_limitation_disclosure": {
            "0": "limitations never mentioned where needed",
            "1": "one generic limitation",
            "2": "limitations present but boilerplate",
            "3": "most material claims carry limitations",
            "4": "every material claim carries a specific limitation",
            "5": "level 4 + limitations independently verifiable from the cited pages"}},
    "finding_distinctness": {
        "c1_no_overlap": {"0": "near-duplicate findings", "1": "2+ findings overlap heavily",
                          "2": "one clear overlap", "3": "minor wording overlap only",
                          "4": "distinct gaps, distinct pages", "5": "level 4 + each gap maps to a distinct business lever"},
        "c2_no_inflation": {"0": "count inflated with duplicates", "2": "padding visible",
                            "3": "count honest but thin", "4": "count justified by evidence",
                            "5": "level 4 + every finding survives a why-separately test"}},
    "customer_specificity": {
        "c1_customer_owned_scope": {"0": "foreign/generic targets", "2": "some non-customer pages referenced",
                                    "4": "every action targets one exact customer-owned URL",
                                    "5": "level 4 + each target verified live in this run"},
        "c2_buyer_language": {"0": "generic SEO speak", "2": "partly buyer-anchored",
                              "4": "every mechanism reasons from the customer's buyer journey",
                              "5": "level 4 + buyer questions quoted verbatim from evidence"}},
    "customer_context_integrity": {
        "c1_no_foreign_content": {"0": "foreign customer content present", "4": "no foreign content anywhere",
                                  "5": "level 4 + positive checks quoted for every section"},
        "c2_context_binding": {"0": "name/domain/goal inconsistent", "4": "all sections share one context",
                               "5": "level 4 + context lock fields quoted"}},
    "business_logic_integrity": {
        "c1_model_consistency": {"0": "recommendations contradict the business model",
                                 "4": "every action fits the model", "5": "level 4 + model assumptions stated"},
        "c2_internal_contradictions": {"0": "sections contradict", "4": "no contradictions found",
                                       "5": "level 4 + cross-section comparison documented"}},
    "commercial_priority_discipline": {
        "c1_status_honesty": {"0": "DO NOW with unresolved approvals", "4": "status matches approvals exactly",
                              "5": "level 4 + every approval item enumerated"},
        "c2_priority_reasoning": {"0": "no ordering rationale", "4": "rationale per status",
                                  "5": "level 4 + dependencies between actions stated"}},
    "action_executability": {
        "c1_brief_completeness": {"0": "missing DoD/owner/signal", "4": "DoD, owners, signal, baseline, window, scale rule all present",
                                  "5": "level 4 + each element action-specific, not templated"},
        "c2_placement_precision": {"0": "vague placement", "4": "exact placement on exact page",
                                   "5": "level 4 + placement quoted against live page structure"}},
    "action_scope_discipline": {
        "c1_single_url": {"0": "one action spans unrelated pages", "4": "one action = one primary URL, scope clean",
                          "5": "level 4 + rendered text free of other-page references"},
        "c2_explicit_exclusions": {"0": "silent scope creep", "4": "exclusions stated",
                                   "5": "level 4 + follow-on actions enumerated with required own fields"}},
    "claims_safety": {
        "c1_hypothesis_labelling": {"0": "unproven performance claims as fact", "4": "unprovable statements hypothesis-labelled",
                                    "5": "level 4 + each hypothesis names its validation data source"},
        "c2_no_superlatives": {"0": "superlative market claims", "4": "no unsupported superlatives",
                               "5": "level 4 + wording checked section-by-section"}},
    "roadmap_consistency": {
        "c1_status_derivation": {"0": "roadmap contradicts statuses", "4": "roadmap renders from investment_status only",
                                 "5": "level 4 + every roadmap cell traced to an action"},
        "c2_timeline_honesty": {"0": "promises without basis", "4": "preparation-only until approvals",
                                "5": "level 4 + day ranges justified"}},
    "journey_map_integrity": {
        "c1_row_binding": {"0": "rows from another job/template", "4": "every row bound to current actions+pages",
                           "5": "level 4 + each row's signal matches its action"},
        "c2_no_fallback": {"0": "hard-coded fallback map visible", "4": "no fallback content",
                           "5": "level 4 + row count matches action count"}},
    "pdf_customer_readiness": {
        "c1_no_internal_leaks": {"0": "internal IDs/paths/placeholders visible", "4": "customer-clean",
                                 "5": "level 4 + appendix boundary verified"},
        "c2_language_quality": {"0": "truncated/broken/generic text", "4": "clean professional copy",
                                "5": "level 4 + no template phrases remaining"}},
    "delivery_artifact_integrity": {
        "c1_render_integrity": {"0": "render failed/corrupt", "4": "single render, verified",
                                "5": "level 4 + SHA chain documented"},
        "c2_scan_clean": {"0": "safety scan fails", "4": "scan clean",
                          "5": "level 4 + scan rules enumerated"}},
}

# Category-specific evidence source requirements (AUDIT_EVIDENCE_CATEGORY_MISMATCH)
CATEGORY_EVIDENCE_SOURCES = {
    "delivery_artifact_integrity": ["artifact manifest", "rendered sha", "reviewer sha",
                                    "scanned sha", ".for-email sha", "scanner result",
                                    "delivery-gate verification"],
    "journey_map_integrity": ["journey map page", "action id", "primary url",
                              "observed friction", "first signal", "action object"],
    "action_scope_discipline": ["exact placement", "scope note", "cta destination",
                                "definition of done", "qa requirements", "scale rule",
                                "action primary url"],
}
