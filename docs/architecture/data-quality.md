# Data Quality and Source Assessment

## Purpose

This document defines initial quality controls for market observations, documents, events, and research evidence. Quality flags describe known properties and limitations; they do not turn uncertain data into certainty.

## Validation dimensions

### Completeness

Check required fields, expected time coverage, missing intervals, and missing values. Distinguish values not provided by source, not applicable, unavailable due to retrieval failure, withheld/restricted, and unknown reason.

Do not silently replace missing values with zero, forward-fill them, or interpolate them. Any imputation must be explicit, separately versioned, and appropriate to the research task.

### Integrity and validity

Validate types, units, identifiers, timestamp parsing, numeric domains, and schema conformance. For OHLCV candles, check applicable invariants such as:

- high is not below open, close, or low;
- low is not above open, close, or high;
- volume is non-negative when the metric definition requires it;
- interval start precedes interval end;
- values conform to declared precision and unit.

A failed check should create a validation result or quarantine state, not silently discard the source record.

### Consistency

Compare records across time, related fields, and sources where meaningful. Differences between exchanges, quote currencies, aggregation methods, or provider methodologies are not automatically errors. Comparisons require compatible definitions and units.

### Duplicates

Use source-native IDs where reliable, supplemented by scoped logical keys and content hashes. Distinguish exact duplicate retrievals from legitimate repeated publications, revisions, and separate observations that happen to share values.

### Outliers and anomalies

Flag unusual values using documented, context-appropriate rules. Preserve the original observation. A statistical outlier may be a real market event; automated deletion is prohibited by default. Review should consider venue, liquidity, market conditions, neighboring intervals, and independent sources.

### Revisions and late arrivals

Track corrected, superseded, provisional, and late-arriving records explicitly. Preserve prior versions and the time each version became available. Research datasets must declare which revision policy they use.

## Source assessment

Assess sources using documented evidence across dimensions such as publisher identity/accountability, primary versus secondary relationship to the event or measurement, methodology/transparency, historical coverage and timestamp precision, consistency and correction practices, independence from corroborating sources, access stability/rate limits/operational latency, and licensing/retention/redistribution permissions.

Do not collapse these dimensions into an unexplained universal trust score. If a later workflow uses ratings or rankings, it must disclose criteria, evidence, scope, reviewer, and limitations. A source can be reliable for one data type and unsuitable for another.

## Evidence handling

For each evidence item, record its origin, extraction context, availability time, and relationship to the relevant claim or hypothesis. Preserve supporting evidence, contradicting evidence, alternative explanations, unresolved disputes, and analyst interpretation separately from source content.

Independent corroboration must be assessed for actual independence. Multiple outlets repeating one original report do not necessarily constitute multiple independent sources.

## Quality states

A proposed vocabulary:

- `valid`: passed applicable automated checks;
- `valid_with_warnings`: usable with documented limitations;
- `quarantined`: requires review before normal use;
- `rejected`: invalid for the specified use, with reason retained;
- `unknown`: insufficient information to assess.

These states are contextual. A record rejected for one analytical use may remain useful as evidence of what a source published.

## Operational reporting

Every ingestion or transformation run should report counts for received, accepted, warned, quarantined, rejected, duplicated, and revised records, where applicable. Reports should include rule/version identifiers and representative failure reasons.

## Research safeguards

- Preserve original records and validation outcomes.
- Do not equate missing data with zero activity.
- Do not remove outliers without an auditable rule and rationale.
- Do not treat repeated copies of one report as independent corroboration.
- Do not infer causality from correlation, source reliability, or temporal proximity alone.
- Exclude future or not-yet-available information from point-in-time analysis.
