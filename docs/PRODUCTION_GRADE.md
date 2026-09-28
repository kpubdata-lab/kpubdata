# Production-Grade Dataset Definition

> This document is the **single source of truth** for what "production-grade"
> means in KPubData. All other references link here. If you need to change
> the criteria, change this file — not the copies.

## Overview

A dataset progresses from **test-verified** to **production-grade** when it
meets all the criteria below. Studio adds a second tier for datasets that
are ready for the visual builder experience.

## Base Requirements (all providers)

### Source & Documentation
- [ ] `metadata.source_url` points to the official dataset page
- [ ] Provider is listed in `SUPPORTED_DATA.md` with correct status
- [ ] The dataset has a human-readable description

### Verification & Testing
- [ ] Schema contract test passes (`make verify DATASET=<id>`)
- [ ] Fixture exists with recorded metadata (`make record DATASET=<id>`)
- [ ] Replay verification passes (fixture → expected output match)
- [ ] Example script exists in `examples/<provider>/<dataset_key>.py`
- [ ] Example script runs deterministically in replay mode

### Data Quality
- [ ] Field types are declared in `fields[]` where applicable
- [ ] Formatted numerics (commas, whitespace) are handled by the executor (#461)
- [ ] Column casting is consistent across pages (#481)
- [ ] Validation report shows no uncastable fields, or issues are documented

### Operational
- [ ] Error paths return typed exceptions (not raw HTTP errors)
- [ ] Pagination works correctly (`list_all()` completes without data loss)
- [ ] The dataset works with `call_raw()` escape hatch

## Studio Additional Requirements

Datasets marked for Studio must additionally satisfy:

- [ ] Parameter form can be generated from the spec
- [ ] Preview renders correctly with real data
- [ ] Dataset appears in Studio's catalog discovery
- [ ] No known Studio-specific blockers

## Machine-Readable Version

See [production_grade.yaml](./production_grade.yaml) for a structured
version that CI can evaluate per-dataset.

## References

- #463 (this document's origin)
- #438 (agent automation pipeline — references these criteria)
- #452, #461, #481 (column casting evolution)
- #572 (validation report)
