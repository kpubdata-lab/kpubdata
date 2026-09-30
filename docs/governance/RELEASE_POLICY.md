# Release Policy

> This file lists **what is checked** before a release (#528). **When** each
> repository may release is decided in one place,
> [compatibility.md §5.1](../compatibility.md#release-cadence): kpubdata on demand,
> at most once every seven days; KPubData Builder and KPubData Studio once a month,
> in the week holding the month's last Thursday; a critical patch, with an issue
> number, is the only exception. The `release-window` gate enforces it.
> The release decision itself is a human action (POLICY §14).

## Version Scheme

Semantic Versioning. Pre-1.0 minor bumps may carry breaking changes.

```
kpubdata:   MAJOR.MINOR.PATCH
builder:    MAJOR.MINOR.PATCH
studio:     MAJOR.MINOR.PATCH
```

## Release Criteria (all must be met)

### 1. Code Quality
- [ ] All CI gates pass on main (lint, type check, tests, coverage, docs)
- [ ] No `priority:high` or `severity:critical` issues open against the Target Release
- [ ] The artifact installs and starts in a clean environment (`pip install kpubdata==X.Y.Z` in a fresh venv)

### 2. Verification
- [ ] Spec datasets: `make verify` passes (schema → fixture → replay → example)
- [ ] Live-API verification ran within the last 90 days (or documented why not)
- [ ] Cross-repo E2E passes (kpubdata → builder → studio on a Korean runner)

### 3. Documentation
- [ ] CHANGELOG has no empty `[Unreleased]` section
- [ ] Breaking changes have migration notes
- [ ] Compatibility matrix (`compatibility.json`) updated
- [ ] API_SPEC.md reflects any public API changes

### 4. Process
- [ ] Every issue in the Target Release is Done or explicitly Deferred
- [ ] A tracking issue exists for the Target Release
- [ ] **A human approves** (POLICY §14 — an agent never gives final approval)

## Release Process

The release workflow (`.github/workflows/release.yml`) enforces the ordering:

```
0. window   → release-window gate (§5.1) — first step of prepare and release
1. prepare  → opens a release PR (version bump + CHANGELOG date)
2. review   → a human reviews and merges the PR
3. release  → CI gates run on the merged commit, then tag + GitHub Release
4. publish  → a person dispatches publish-pypi.yml with the tag (trusted publisher)
```

No tag exists before the gates pass (#586). A re-run after the tag was pushed but the
GitHub Release was not created finishes the release (#687). A re-run after a
`release-window` refusal does nothing — it replays the same event; release with
`mode=release` inside the window, or with `critical_patch` and `critical_issue`.
[PACKAGING.md](https://github.com/yeongseon/kpubdata/blob/main/PACKAGING.md#release) has the step-by-step procedure.

## Version Alignment

All three repositories must declare versions that match their tags and artifacts.
`uv lock --check` catches lockfile drift in CI (#624). Builder's kpubdata pin raise
may merge at any time — a pin is not a release; users get it with the next monthly
Builder release (§5.1). Studio has no kpubdata pin: it depends only on Builder's
HTTP/OpenAPI contract (ADR 0007).

## First Formal Releases

Facts from `gh release list` (2026-09-30):

| Repository | Latest release | Date |
|---|---|---|
| kpubdata | v0.8.0 | 2026-09-30 |
| kpubdata-builder | v0.4.0 | 2026-09-28 (v0.1.0 on 2026-05-28 before it) |
| kpubdata-studio | v0.4.0 | 2026-09-28 (its first release; same version as Builder, ADR 0004) |

Whether these count as the first *formal* releases under the criteria above is a
person's call (POLICY §14).

## Quarterly Re-check

- [ ] Terms matrix (`docs/policy/terms-matrix.md`) reviewed
- [ ] License fields in specs still match the terms matrix
- [ ] API keys still valid (probe results healthy)
