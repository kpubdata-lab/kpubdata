# Release notes — KPubData SDK

## Shared release-note contract

The full versioned `CHANGELOG.md` section is the **single source of truth**. Do not independently hand-edit a second release history. A GitHub Release is a short reading view generated from the same reviewed version entry.

For each **new release** add these exact sections to its CHANGELOG entry, in English, above the detailed Added / Changed / Fixed / Security entries:

1. `### Highlights`: **1–5** verified user-impact bullets. Lead with what users can now accomplish; do not repeat internal CI or governance details.
2. `### Upgrade notes`: explicit breaking changes, changed errors and required user/operator actions. Use exactly `- None.` **only after checking** that no action is needed.
3. `### Known limitations`: still-open, verified security, data correctness, availability and operational limitations with issue links. Use exactly `- None.` **only when reviewed and true**.

Keep the complete implementation history, issue references, technical measurements and contributor details under the normal detailed sections in CHANGELOG. Do not discard them to shorten the public body.

The public release should present only the three curated sections, the exact released install/upgrade command, a version-pinned full CHANGELOG link and a previous-tag comparison link when available. Avoid empty headings, duplicated full changelogs, placeholders, unverified numbers, claimed features not in the tagged commit and inaccurate security assurances.

### Release-time checks

- Confirm the tag, package version, CHANGELOG date, tested commit and actual release artifact match.
- Check each summary statement against the actual code/tests and correct stale metadata or dataset counts before tagging.
- Keep pre-release history and breaking-change migration instructions accurate.
- If any curated section is missing or empty, **fail before publishing/tagging**, not fall back silently to a 20,000-character change list.
- Apply changes to future releases only. Preserve historical release notes and changelog sections unless a separate, clearly documented factual correction is approved.
- Do not make a release merely to test the writing rules; use unit tests or a read-only preview.

### Example (illustrative, not an actual release)

```markdown
### Highlights

- Data columns now show understandable field labels (#123).

### Upgrade notes

- Catch `AuthError` instead of `TransportError` for refused credentials (#124).

### Known limitations

- Some provider endpoints still require a security migration (#125).

### Added

- Full implementation notes with precise scope and test evidence.
```

## SDK-specific operation

The existing `scripts/release_notes.py` stays the single release-note extraction implementation. `promote` dates the existing CHANGELOG section; `extract` retains the full-body interface for internal uses; the release action requests the concise public form. The complete published release remains browseable at `https://github.com/kpubdata-lab/kpubdata/blob/vX.Y.Z/CHANGELOG.md`.

The next SDK release is **not yet published**. Review the prepared v0.11.0 release PR and its dated changelog against main before merging; refresh the release branch if the reviewed CHANGELOG summary has changed. The release control gate and independent approval remain required. See #982.
