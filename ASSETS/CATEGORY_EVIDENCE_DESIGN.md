# CATEGORY-EVIDENCE REPAIR DESIGN
# (owner directive 2026-09-14h — CATEGORY_EVIDENCE_INSUFFICIENT enforcement)

## 1. delivery_artifact_integrity
- **Evidence source required:** artifact manifest (candidate SHA, strict reviewer SHA, red-team input SHA, scanned SHA, .for-email SHA, mock attachment SHA), scanner output, delivery-gate verification result
- **Evidence source NOT allowed:** PDF visible text, PDF header, report prose, executive summary
- **Required artifact/manifest fields:** candidate SHA, reviewer PASS record (signed), scanner hard_fails=[], SHA chain equality proof, mock delivery record
- **Required PDF page/section evidence:** N/A — this category is scored from the artifact manifest, NOT from PDF visible text
- **Programmatic validation:** the auditor itself computes csha=sha256(pdf_bytes), runs gate5_scan_final_pdf, verifies SHA equality with reviewer-approved SHA and mock attachment SHA. It checks scan["clean"] and scan["hard_fails"]==[].
- **Hard fail trigger:** scan["hard_fails"] non-empty; SHA mismatch; auditor cannot read artifact; manifest incomplete
- **How a passing report proves this:** the auditor's own deterministic check confirms single render + clean scan + 3-way SHA + gate SHA match. The evidence IS the computed SHA values and scan output, not customer-visible text.

## 2. customer_context_integrity
- **Evidence source required:** whole-report extracted-text foreign-term scan (all 9 foreign terms checked against full visible text); whole-report domain/URL ownership scan (every https URL in visible text checked against approved customer domain); customer-context manifest (company_name, primary_domain, business_goal from job); report-wide company/domain consistency result
- **Evidence source NOT allowed:** PDF header quote alone; a single page's foreign-content check; executive summary text
- **Required artifact/manifest fields:** job.company_name, job.url (→ approved domain), job.order_id; extracted visible text (full document)
- **Required PDF page/section evidence:** the auditor's own scan output listing every foreign term checked and result (found/not-found); every URL domain found in visible text and whether it matches the approved domain
- **Programmatic validation:** the auditor scans full visible text for all 9 foreign terms (screen-printing, embroidery, /gallery/, get-a-quote, quote-form, apparel, garment, printing, apple imprints) + every URL domain; if any found → hard fail
- **Hard fail trigger:** any foreign term found; any non-approved URL domain found; context-lock fields inconsistent
- **How a passing report proves this:** the scan output itself is the evidence — a list of every term checked with result "not found" and every URL domain with "matches approved domain"

## 3. finding_distinctness
- **Evidence source required:** all finding texts (not just Finding 1); a pairwise overlap check across all finding gaps and target URLs; distinct-page verification
- **Evidence source NOT allowed:** a single Finding 1 quote; executive summary text; one gap description
- **Required artifact/manifest fields:** all finding gaps (from evidence cards), all target URLs, all action IDs
- **Required PDF page/section evidence:** the auditor must compare every finding's specific_gap against every other finding's specific_gap (pairwise), and verify all target URLs are distinct
- **Programmatic validation:** the auditor builds a pairwise gap-overlap matrix from the finding cards; if any two findings share >50% gap text or the same target URL → hard fail. Also checks that the LLM's distinctness score cites at least 3 finding IDs.
- **Hard fail trigger:** duplicate gaps; same target URL for 2+ actions; LLM distinctness score >90 but cited fewer than 3 finding IDs
- **How a passing report proves this:** the auditor's pairwise matrix shows all 5 findings with distinct gaps and distinct URLs; the LLM citation quotes at least 3 different finding IDs.

## 4. roadmap_consistency
- **Evidence source required:** roadmap rows (from rendered PDF text); each corresponding action ID; each action's investment_status; each action's approval_dependency; timeline text; scale rule text
- **Evidence source NOT allowed:** executive summary status; a single action's status; investment matrix heading alone
- **Required artifact/manifest fields:** action investment_status map; rendered roadmap text (from PDF visible text); approval dependency per action
- **Required PDF page/section evidence:** the auditor extracts the roadmap section from visible PDF text and cross-references every roadmap row's ACT ID against the action objects; checks that each row's status matches the action's investment_status
- **Programmatic validation:** the auditor uses gate5_check_roadmap_status_consistency + gate5_check_priority_consistency; additionally checks that every ACT-xxx in the roadmap text exists in the action set and that DO NOW wording does not appear for VALIDATE FIRST actions
- **Hard fail trigger:** roadmap status contradicts action investment_status; ACT ID in roadmap not in action set; DO NOW wording for an action with unresolved approval
- **How a passing report proves this:** the cross-reference output shows every roadmap row matched to an action with consistent status and approval dependency.

## 5. business_logic_integrity
- **Evidence source required:** the actual business_mechanism text per finding; the hypothesis/limitation label per mechanism; the linked action's primary URL; the validation data source named in the limitation
- **Evidence source NOT allowed:** a generic disclaimer ("nothing is guaranteed"); a single mechanism quote; the executive summary alone
- **Required artifact/manifest fields:** business_mechanism per evidence card; hypothesis/limitation labels per action; linked action's primary URL; named validation data source
- **Required PDF page/section evidence:** the auditor extracts each finding's mechanism text from visible PDF text and verifies that each contains (a) hypothesis/limitation labelling, (b) a named validation data source, (c) a linked action URL
- **Programmatic validation:** the auditor checks every mechanism text for presence of hypothesis/limitation wording and validation source; if a mechanism has neither → hard fail
- **Hard fail trigger:** any mechanism lacks hypothesis/limitation label; any mechanism lacks a named validation source; any mechanism states a behavioural inference as fact
- **How a passing report proves this:** every mechanism in the visible PDF text carries a hypothesis label and a validation source, verified programmatically.
