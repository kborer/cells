# Maintenance and recovery

## Routine checks

Review Dependabot security fixes promptly and ordinary dependency updates weekly.
The Security workflow runs Python/Actions CodeQL, dependency review on PRs,
actionlint, and a vulnerability audit of development/build dependencies. Resolve
or document a finding based on its actual exploitability; do not hide failures
through blanket exclusions. Dependabot never merges or publishes automatically.

Nightly Endurance jobs run extended Hypothesis sequences and one simulated hour
per scene, plus fifteen-minute compact, overview, and raster/detail profiles.
Compact profiles use seeds 0 and 42 without resizing, so resizing cannot hide
blocked arrivals. Reports check entry completion, eligible budding progress,
free microbial populations, and immune diversity as well as finite counts.
Download their JSON reports to compare population history, allocation
retention, and early/late update latency. Limits are deliberately generous to
avoid treating shared-runner noise as a product regression. Failures still need
investigation. Seeded reproduction commands are in the logs. Coverage is reported
in CI and the Ubuntu Python 3.14 `.coverage` artifact. Paths are relative to the
repository: download it into your checkout and use `coverage html` locally
to locate missing branches. Coverage percentage is diagnostic, not a substitute
for assertions about behavior.

Require independent workflow/release review when a second maintainer joins.
CODEOWNERS only requests review; it does not provide independent review while
there is one owner. Account owners should use MFA/passkeys and retain account
recovery codes outside the repository. Current production approval deliberately
permits the sole maintainer to approve a run they started.

## Releases and failed publications

Follow the [release guide](RELEASING.md) for the authoritative preparation,
staging, promotion, and recovery steps. Distribution-specific instructions live
in [Ubuntu packaging](UBUNTU.md) and [Homebrew packaging](HOMEBREW.md).

Build artifacts expire under GitHub's retention policy. Preserve the successful
candidate's manifest and artifacts until promotion is complete. If artifacts
expire after a version was uploaded, a fresh candidate needs a new package version.
An immutable published release needs a new release for corrections.

## Signing-key backup and recovery

Keep an encrypted backup of your OpenPGP private key and its revocation
certificate in secure offline storage, separate from the computer and repository.
Test recovery with GnuPG in an isolated temporary keyring. Keep the passphrase
and account recovery codes in your password manager. Never send a private key,
passphrase, or revocation certificate to GitHub, Launchpad, an issue, or chat.

Before the key expires, extend it locally and publish the updated public key to
the Ubuntu keyserver; confirm Launchpad recognizes it before uploading. If lost,
restore from the protected backup or register a replacement key and confirm it
through Launchpad. If compromised, stop uploads, revoke the old key deliberately,
publish the revocation, remove its Launchpad authority, register a replacement,
and review uploads made during the exposure. Revocation is irreversible; the
maintainer must perform that decision and credential replacement.

If a GitHub/PyPI account is compromised, revoke sessions/tokens, recover the
account, inspect workflow and publisher changes, and review releases and signed
provenance. OIDC eliminates a long-lived PyPI upload token, not account compromise.
