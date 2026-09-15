# Detailed terminology mapping method

## 1. Define what the mapping must mean

Write down the source system and version, target terminology and version, target domain, intended ETL table, research priorities, acceptable loss of detail, reviewer label and scope of authorized edits. A terminology is not a domain: SNOMED has concepts in multiple OMOP domains, while an OMOP domain can use multiple terminologies. Use exact vocabulary/domain IDs from the supplied release.

Distinguish three tasks: validate an automatic target; replace an unsuitable target; interpret an underspecified source. The last task can need a catalogue definition or local expert. A high similarity score cannot provide missing clinical information.

When only a raw source list exists, the same workflow creates mappings from an initially empty target column. This engine does not pretend its search ranking is an Usagi automapping score.

## 2. Profile the source before changing it

Check:

- Encoding, comma versus tab delimiter, duplicate headers, malformed records and empty labels.
- Unique source-code count; leading zeros; reused codes across systems/versions.
- Existing APPROVED/FLAGGED rows and review provenance.
- Target ID/name/domain fields, missing targets, score distribution and occurrence frequencies.
- Abbreviations, truncation, translations, modifiers, punctuation and bundled descriptions.
- Source catalogue classes and explicit context that distinguish identical labels.

Preserve strings as strings. `00123` is not the integer `123`; unit codes can be case-sensitive. Do not infer a imaging modality from an unexplained billing prefix. An inferred prefix meaning needs catalogue evidence and a recorded rationale.

Save the byte-exact input, SHA256, priority document, source schema and immutable row identities. A row ID includes the baseline hash, record ordinal and original content. It cannot silently migrate to another file. `group_id` groups similar source/target/context records to assist review, not to authorize copying a decision automatically.

## 3. Establish the target evidence set

Use the supplied local vocabulary first. For Athena, read CONCEPT, CONCEPT_SYNONYM and VOCABULARY. Check:

1. Target concept exists with the exact identifier.
2. Vocabulary and domain are in the selected scope.
3. Standard concept status is `S` for standard OMOP mapping.
4. Invalid reason is empty.
5. As-of date is within both validity bounds.
6. Concept name/code metadata matches the identifier.

The SQLite index stores preferred names, synonyms, eligibility and the source-file hashes. It retains selected-vocabulary concepts outside the chosen domain or validity window for explanations, but search results contain eligible targets only. A target from a vocabulary not indexed returns unknown; consult the raw export if its provenance matters.

An active concept is not automatically a correct mapping. An exact label may still be an ambiguous abbreviation, context-dependent phrase or misleading synonym. The generalized workflow requires explicit review for exact candidates too.

## 4. Prioritize the work without dropping the remainder

Read the full research document. Translate it into a short set of navigation tags, with reasons for their clinical relevance. Examples: coronary intervention, stroke reperfusion, device complications, wound/infection care and critical-care interventions. For another study, use its actual questions.

Optional regular expressions help surface terms. They are neither exhaustive phenotypes nor evidence that an event occurred. Record the patterns in `priority_rules` and keep their source document. Review high-priority terms first, including high-score suggestions, then the remainder across all score ranges. Use frequency only when real counts are available; do not treat -1 as an observed frequency.

## 5. Review source meaning against target meaning

For each row, explicitly compare:

| Dimension | Common failure |
|---|---|
| Action | Implantation versus removal, assessment versus treatment, incision versus excision |
| Entity/anatomy | Gallbladder versus urinary bladder, ureter versus urethra, coronary versus cerebral |
| Method/route | CT versus ultrasound; open versus endoscopic; IV versus intra-arterial |
| Extent | Total versus partial; single versus multiple; unilateral versus bilateral |
| Qualifiers | Planned versus emergency; primary versus revision; donor versus recipient |
| Negation | Care without thrombolysis mapped to thrombolytic treatment |
| Alternatives | A or B mapped to a target requiring A and B |
| Components | A report or charge category mistaken for the procedure it describes |
| Time/context | Follow-up management mistaken for a new insertion or administration |

Use the matching domain profile for additional attributes. Read the whole source string; a strong shared noun is insufficient.

For a proposed replacement, inspect local terms and metadata. Search with a clinically faithful shorter expression when necessary; document what you omitted. Search `--any-word` broadens retrieval only. Confirm aliases through actual synonym records or an authoritative terminology definition. Do not approve a similar-sounding procedure by guessing an abbreviation expansion.

## 6. Decide status and relationship separately

| Relationship | Source → target meaning | Workflow treatment |
|---|---|---|
| EQUAL | Intentionally the same concept, with enough evidence beyond a coincidental label | Approve when eligible and supported |
| EQUIVALENT | Same clinical meaning expressed differently | Approve when eligible and supported |
| WIDER | Target covers a broader meaning or omits a source restriction/component | Approve only under the agreed broader-mapping policy; otherwise flag |
| NARROWER | Target adds a restriction not justified by the source | Flag |
| INEXACT | Overlap with additional or conflicting meaning on either side | Flag |
| UNMATCHED | No supported match in the declared target scope after an appropriate search | Flag; define whether the failure is scope-specific |
| UNREVIEWED | Current target is unresolved; insufficient evidence to establish a relation | Flag if inspected, otherwise leave UNCHECKED |

Target breadth follows the [HL7 ConceptMap equivalence definitions](https://hl7.org/fhir/R4/codesystem-concept-map-equivalence.html). Usagi exposes the corresponding equivalence choices and supports comments and approved-only export. [Usagi usage](https://ohdsi.github.io/Usagi/usage.html).

Every completed row decision has an evidence trail, even when its optional mapping comment is empty. Do not claim no concept exists across an entire terminology after a narrow keyword search. Prefer an unresolved flag with the searches tried and missing information.

The engine supports one target per input row. A bundled procedure may require several concepts. If a broader single target would discard an essential study component, flag it and record the proposed decomposition. Do not turn `A and/or preparation for B` into two performed procedures.

## 7. Validate hierarchy and phenotype use

For key targets, inspect relevant ancestor links and synonyms. Test the actual concept IDs against the proposed study anchors; not every clinically related concept appears under an intuitively named ancestor in every OMOP release. Save presence and absence checks. An absent hierarchy edge is not a clinical contradiction.

Keep vocabulary mapping distinct from cohort/phenotype construction. Source and target codes represent meaning; event data determine occurrence, timing and outcomes. Link the appropriate OMOP records and define study logic separately. The [OMOP CDM specification](https://ohdsi.github.io/CommonDataModel/cdm54.html) describes the relevant tables and temporal fields.

## 8. Record decisions and provenance

Save incremental JSONL decisions against exact `row_ids`. Provide a substantive rationale and references such as `concept:4184832`, `local-catalogue:version/code`, or a primary-source URL plus access date. A reference's existence does not prove the rationale: the reviewer must inspect it.

The scripts validate identifier and status structure, eligible targets, evidence presence, row coverage and authorized changes. They cannot mechanically verify clinical equivalence. Reviewer attribution must not falsely represent an independent human sign-off.

Retain original automatic scores. When replacing a target, explain that the score belongs to the old suggestion. Set status-change timestamps in epoch milliseconds; retain original provenance fields. An unresolved flagged status has a review timestamp, not an approval timestamp.

## 9. Perform final quality checks

Before applying:

- All rows in scope have an explicit decision; separately count preserved prior reviews.
- Approved targets are eligible and use an allowed equivalence.
- Broader and flagged mappings have explanations; corrected targets have consistent names/codes/domains.
- Important qualifiers and source namespaces have not been lost without comment.
- Same code/context does not have conflicting approved targets.
- Approved subset, flags, audit and full mapping agree.
- Original row order, codes, unrelated columns and source/creation provenance survive CSV round-trip.
- Input, queue, index and preview hashes still agree with the review.

Use `render --complete`; an incomplete render is a progress artifact and cannot be applied. Inspect high-score disagreements and research-priority flags. Sampling is a final consistency check, not a substitute for full coverage.

## 10. Apply, hand off and resume

If input updates were authorized, apply the exact validated preview. A lock and hash checks protect against competing runs and most external-file changes; close or reload active editors because there is no cross-application transaction with Usagi. Keep the receipt and baseline. Do not commit to a live ETL database as part of this file workflow.

Report reviewed/preserved/pending counts, approvals, flags, corrected targets, broader approvals, vocabulary snapshot and output paths. Explain what remains unresolved and what evidence would resolve it. For a later source or vocabulary version, create a new run and revalidate inherited decisions; do not reuse baseline row IDs.
