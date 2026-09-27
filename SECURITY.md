# Security Policy

## Reporting a vulnerability

**Do not open a public issue.** Use [Private Vulnerability Reporting](https://github.com/yeongseon/kpubdata/security/advisories/new) — it is enabled on this repository.

Please include, as far as you can:

- What an attacker can do, not only what looks wrong
- The smallest way to reproduce it
- Which commit or release you looked at

You will get an acknowledgement. If the report turns out to be a defect rather
than a vulnerability, it is moved to a normal issue and you are told so.

## What counts as a vulnerability here

This project handles **user-supplied API keys for Korean public data services**
(BYOK). The things we most want to hear about:

- **A provider credential reaching a host it should not.** A spec declares both
  the host to call and the credential to attach; `src/kpubdata/_hosts.py` gates
  that pairing. A way past that gate is the most serious report we can receive.
- **A credential appearing anywhere it is not supposed to** — a log line, an
  exception message, a cache file, a fixture, a URL in a traceback.
- **A fixture that can be forged** so a dataset counts as verified when it was
  never called.

Also in scope: anything that lets one user reach another user's data, and
anything that makes published data violate its provider's terms.

## What does not count

- A missing hardening measure with no reachable consequence
- Denial of service by simply sending a lot of requests
- Outdated dependencies with no exploitable path in this code — open a normal issue
- Findings from a scanner, pasted without a reachable path

## Supported versions

Only the latest release of each component receives fixes. Version and tag are
being reconciled (kpubdata-builder#690); until that lands, report against a
commit SHA rather than a version number.

## Known limits, stated deliberately

- `scripts/check_fixture_authorship.py` relies on the commit author name, which
  is self-asserted. It makes an accidental edit visible; it is not a boundary.
  The boundary is branch protection plus secret isolation.
- Some documentation is Korean. A report in either Korean or English is fine.
