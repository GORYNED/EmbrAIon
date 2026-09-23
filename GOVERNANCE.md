# Governance

EmbrAIon is maintained by GORYNED.

## Maintainer model

GORYNED is the upstream maintainer and final decision-maker for repository scope, architecture, policy, releases, and accepted contributions.

The repository is not governed by contributor voting or a multi-party steering committee at this stage.

## Main branch

The stable `main` branch is maintained by GORYNED.

External contributors do not need direct write access. They propose changes through Pull Requests.

Maintainer-authored changes may be committed directly to `main` when appropriate. Repository validation remains the evidence gate for those changes.

## Pull Requests

External Pull Requests are reviewed by the maintainer.

Acceptance requires, as applicable:

- appropriate scope;
- green validation;
- compatibility awareness;
- security/privacy review;
- alignment with Core ownership and architecture.

Accepted external Pull Requests use **Squash merge** so each accepted contribution becomes one coherent commit in `main`.

## Releases

Published release tags use the `vX.Y.Z` form.

Release tags are intended to be immutable:

- do not force-move an existing release tag;
- do not delete and recreate a published release tag;
- publish a new version when a released artifact must change.

The automated release workflow validates release commits before creating a new tag and publishing artifacts.

## Security

Security vulnerabilities are handled privately according to [SECURITY.md](SECURITY.md).

## Conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Licensing

No CLA is required. Contributions accepted into MIT-licensed source or documentation are distributed under the repository's applicable license. Brand and trademark rights remain governed by [TRADEMARKS.md](TRADEMARKS.md).
