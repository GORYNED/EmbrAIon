# Review

The canonical [Lead contract](../agents/lead.yaml) owns orchestration and final acceptance. Apply this workflow when the [independent review rule](../rules/review.md) or stricter project policy requires it.

1. Freeze the completed implementation candidate before independent review.
2. Lead assigns an independent read-only Reviewer and provides intent, contracts, diff, fresh validation evidence, and known risks.
3. Reviewer inspects applicable compatibility, lifecycle, security, and privacy concerns and reports prioritized material findings or an explicit no-material-findings result. Missing required evidence is not a pass.
4. Lead assigns remediation without giving the Reviewer implementation ownership.
5. Resolve or explicitly accept material findings according to policy. Validator collects fresh proportional regression evidence after fixes.
6. Re-review only when material changes invalidate prior review evidence. Treat it as a new bounded assignment and classify the actual delta. Prior complexity is risk evidence, not an inherited route. Narrow remediation checks may be substantial; renewed concurrency, lifecycle, compatibility, or architecture changes are complex.
7. Lead integrates the review and validation outcomes before final acceptance.
