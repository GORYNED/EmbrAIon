# Contributing to EmbrAIon

Thanks for taking the time to improve EmbrAIon.

EmbrAIon is maintained by GORYNED. External contributions are welcome through pull requests, but submission does not guarantee acceptance. The maintainer decides what belongs in the upstream framework and may request changes, narrow scope, or decline a contribution.

## Contribution model

- External contributors propose changes through a fork and pull request.
- The stable `main` branch is maintained by GORYNED.
- Keep each pull request focused on one coherent purpose.
- Pull requests should pass the repository validation workflow before merge.
- Accepted pull requests are merged with **Squash merge**.
- EmbrAIon does not require a Contributor License Agreement (CLA).

## Before opening a pull request

For substantial behavior, architecture, policy, routing, schema, or compatibility changes, open or reference an issue first when practical. Small fixes and documentation corrections may go directly to a pull request.

Do not use a public issue or pull request to report a security vulnerability. See [SECURITY.md](SECURITY.md).

## Development setup

EmbrAIon requires Python 3.11 or newer.

From a source checkout:

```bash
python -m pip install -e .
python tools/source.py validate
python tools/source.py test unit
python tools/source.py test integration
python tools/source.py security scan --path . --fail-on high
python tools/source.py sync --host all --output build/generated --force
```

The CI matrix also validates supported behavior on Linux, Windows, and macOS.

Use a local `.venv` for development dependencies when the system Python is shared. The source runner selects that environment when present. `embraion validation run fast`, `affected`, and `full` use the same source entry point, even when the project runtime remains pinned to the previous stable release. Advance the self-host project pin and artifact lock only after the new release is published.

## Change expectations

A contribution should:

- preserve Core/adapter separation;
- keep project-specific semantics out of reusable Core;
- preserve privacy and access boundaries;
- include deterministic tests when deterministic behavior changes;
- update documentation when public behavior changes;
- describe compatibility or migration impact;
- avoid unrelated refactors;
- never include credentials, secrets, or private user data.

Generated or AI-assisted contributions are allowed, but the contributor is responsible for reviewing and validating the result.

## Licensing

Unless a file or directory states otherwise, accepted source-code and documentation contributions are provided under the repository's [MIT License](LICENSE).

The EmbrAIon and GORYNED names, logos, wordmarks, visual marks, and files under `brand/assets/` are governed separately by [TRADEMARKS.md](TRADEMARKS.md). Do not assume code-license rights grant brand or trademark rights.

## Conduct

Participation is subject to [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Support and compatibility

See [SUPPORT.md](SUPPORT.md) for supported platforms, Python versions, and the pre-1.0 compatibility contract.
