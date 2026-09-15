# Domain profiles

Use the profile matching the source meaning and intended target domain. These are review criteria, not universal crosswalks or a list of mandated terminologies. The engine accepts any vocabulary/domain IDs present in a canonical export. Standard status and validity must come from that export, not this guide.

## Procedure

Compare performed action, anatomy, approach, extent, laterality, device/material, imaging guidance, contrast, primary/revision and planned/emergency context. Separate performance from preparation, standby, reports, follow-up and device management. An open fracture does not establish open reduction. A specimen category listing possible surgeries does not establish any surgery was performed. Resolve endarterectomy/atherectomy and other surprising terminology aliases using actual synonyms rather than word intuition alone.

For research: diagnostic angiography is not PCI; CABG and septal ablation are not acute coronary PCI; care without reperfusion is not thrombolysis; preparation for thrombectomy is not thrombectomy. Wound care alone does not establish SSI. CPR/ventilation/dialysis do not establish death. Onset, arrival, procedure/administration, discharge and readmission timestamps belong in event-level study logic.

## Drug

Compare all active ingredients, salt/ester where relevant, strength and concentration, denominator, dosage form, route, release characteristics, brand/generic distinction and clinical-drug versus ingredient level. Do not map a multi-ingredient product to one ingredient as EQUIVALENT. A strength-specific source mapped to an ingredient is broader and may be unsuitable for dose/exposure analysis. Different salt expressions and unit conversions need authoritative formulation evidence and arithmetic; do not infer equivalence from matching numbers.

RxNorm and RxNorm Extension are separate vocabulary IDs; a request may allow one or both. Drug administration as an event is different from the drug product. Do not force a pharmaceutical product into Procedure merely because the source catalogue is named procedures. Never infer prescribed dose or duration from package strength.

## Condition

Compare diagnosis, anatomy, subtype, severity, acute/chronic state, episode, laterality, causative organism, complication, certainty and present/history/family-history context. A past or ruled-out condition is not a current diagnosis. Symptoms and findings are not automatically confirmed diseases. Disease staging can belong in separate observations/measurements; preserve the source detail if a broader disease target is chosen.

Mortality cause and temporal complication attribution need clinical/event evidence. Do not infer them from a treatment or a broad diagnosis label alone.

## Measurement and laboratory tests

Compare analyte/component, property measured, timing, specimen/system, scale, method, challenge/adjustment, panel versus individual test and quantitative versus qualitative result. A serum concentration is not interchangeable with a urine concentration or a mass excretion rate. A report is not necessarily a test performance. Do not treat a panel as one analyte.

LOINC codes are measurement definitions, not values or units. Unit normalization is separate and may need numeric conversion. If the local snapshot puts the appropriate concept in Measurement rather than Procedure, flag the domain mismatch instead of choosing an unrelated Procedure target.

## Observation

Compare observed attribute, value versus question, assertion, certainty, timing, subject and context. Keep personal history, family history, social history, counseling, administrative details and findings distinct. Some source terms need an observation concept plus a value concept; the one-target engine must flag these if the intended ETL needs both and cannot represent the source safely.

## Device

Compare device type, intended function, anatomic use, implanted/external status, materials, dimensions, model and component. A device product label does not establish insertion, revision, removal or presence in a patient. The corresponding procedures or observations can be in different domains. Avoid inferring implantation from a purchase/charge entry.

## Unit

Preserve code case and punctuation. Check physical dimension, scale, numerator/denominator, substance-specific molar versus mass relationships, and whether the value is an arbitrary index or a true unit. UCUM case matters. Never call two differently scaled units EQUAL simply because they measure the same dimension. Numeric conversion requires a separately validated ETL transformation; this tool does not transform values.

Use the exact domain/vocabulary IDs in the supplied export. If units are nonstandard in a chosen system, configure that deliberately; do not turn off standard-concept checks for unrelated OMOP mappings.

## Visit and administrative terminology

Distinguish care setting, encounter type, admission/discharge event, service category and billing artifact. A specialist consultation does not necessarily identify a particular Visit concept or performed treatment. Administrative codes may be outside the selected clinical scope. Readmission requires a sequence of encounters and an explicit index definition.

## Other domains or non-OMOP terminologies

Define the meaning dimensions and intended use before reviewing. Supply a canonical concept export with stable identifiers, terminology/domain labels, validity and explicit standard status policy. The strings need not be numeric OMOP IDs. Retain namespace/version context to prevent collisions.

The engine is reusable across domains because those identifiers and policies are configurable. It does not natively parse every terminology distribution, validate every specialty's clinical semantics, or implement every target data model. Raw RF2, OWL, FHIR terminology servers and vendor formats need an explicit adapter and its own verification. Do not label a concept OMOP-standard without an OMOP source.
