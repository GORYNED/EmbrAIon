---
name: dependency-upgrade
description: Upgrade a dependency through an exact reviewed version, transitive impact, migration, and consumer validation.
---

# Dependency Upgrade

Load for a requested dependency version change or a change whose solution requires one. Skip for ordinary feature work where the existing compatible dependency suffices; do not upgrade opportunistically.

1. Record the current exact version, requested dependency target, package source, supported runtime/platforms, direct consumers, lockfile or manifest owner, and project source-authority rules. Distinguish this update from a separately requested product change or publication; preserve the consuming project's version strategy. A framework upgrade alone supplies no product major-version decision or release authority. Do not use an uncontrolled `latest` target.
2. Read authoritative release notes, migration guidance, advisories, and license changes for the specific version span. Inspect transitive changes and conflicts. Distinguish verified facts from hypotheses and record source links or local artifact paths.
3. Update the minimal manifest and lock or resolved dependency artifacts together. Make only required API/configuration migrations and refresh affected dependency instructions or generated projections when necessary. Change README or agent prose only for an explicit request or a concrete newly inaccurate statement, with that reason visible in the diff. Preserve unrelated pins and project-owned version strategy.
4. Validate resolution and actual affected consumers, including build and focused behavior checks. Run required project CI or validation profiles and report platforms not exercised. If rollback is needed, identify the prior exact pin and affected data/configuration state.

Output: old/new exact versions, source evidence, transitive and migration impact, changed artifacts, consumer results, and residual risk. Follow canonical privacy, security, review, and release controls.

Stop when the requested dependency target and required consumer migrations have applicable evidence, or a material compatibility prerequisite blocks them. Report missing evidence as a limit; do not publish to obtain it. An old release plan or checkpoint does not expand the current request.
