# Release Policy (#528)

> A release happens only when every condition below is met.
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
1. prepare  → opens a release PR (version bump + CHANGELOG date)
2. review   → a human reviews and merges the PR
3. release  → CI gates run on the merged commit, then tag + GitHub Release
4. publish  → PyPI via publish-pypi.yml (trusted publisher)
```

No tag exists before the gates pass (#586). Re-runs are safe (#622).

## Version Alignment

All three repositories must declare versions that match their tags and artifacts.
`uv lock --check` catches lockfile drift in CI (#624). Builder and studio must
update their kpubdata dependency pin in the same Target Release or the next.

## First Formal Releases

| Repository | Version | Status |
|---|---|---|
| kpubdata | 0.8.0 | ✅ Released 2026-09-30 (#630) |
| builder | 0.1.0 | ✅ Released (tag exists) |
| studio | 0.1.0 | ✅ Released (package.json version) |

## Quarterly Re-check

- [ ] Terms matrix (`docs/policy/terms-matrix.md`) reviewed
- [ ] License fields in specs still match the terms matrix
- [ ] API keys still valid (probe results healthy)
