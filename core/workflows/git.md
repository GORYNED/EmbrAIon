# Git and GitHub mechanics

This page is the one place for the Git and GitHub mechanics behind the [worktree](worktree.md) and [delivery](delivery.md) workflows. Those workflows keep the universal rules: an isolated workspace, a reviewed change identity, and integration proof. This page says how each is realized on Git and GitHub. It adds no rule and changes no command behavior.

## Prerequisite

Git is a stated prerequisite of EmbrAIon, and GitHub is the supported hosting and delivery surface. The canonical statement is the Requirements section of the installation page of the EmbrAIon documentation (`docs/getting-started/installation.md` in the source repository). Here and in the workflows there is only a reference to it.

## Repository scope

Serialize mutation per Git common directory. Every linked worktree of a repository shares one common directory, so it is the scope of one serialized mutation and of the repeated eligibility checks before each operation.

## Refs

Delete a remote ref only when its expected SHA still matches, and a local ref only after associated worktrees are released. A proved squash merge is the only exception to ordinary local branch deletion.

## Publication

The portable `worktree publish --task-id <id> --branch <branch>` explicitly creates an absent remote ref with a create-only lease and records its verified creation. After further task commits, the same command updates the previously published ref only when its recorded SHA still matches. Retain the original creation receipt and the verified update chain; an external push cannot substitute for a supported publication update.

## Merged pull request evidence

For a merged PR, verify the repository, head branch and SHA, target branch, merge commit ancestry, and absence of open PRs using the branch as head or base. Squash integration requires exact PR head evidence; patch similarity is insufficient.

## Reviewed change identity

On GitHub the reviewed change is identified by the pull request source HEAD SHA, its base, and the resulting diff. [Delivery](delivery.md) confirms that identity before an authorized squash merge. The squash commit receives a new SHA after merge; source HEAD confirmation applies before that operation.
