# Release Settle

`uses: megaeth-labs/.github/.github/actions/release-settle@main`

<!-- generated: description -->
Propose settling a release candidate: verify `commit` is the tip of the release branch and carries the expected version, generate release notes from the commits since the previous tag, write them into the changelog (stamping the date onto the candidate's `## vX.Y.Z` entry), and — in the default `pr` mode — open a `chore/release-settle-vX.Y.Z` PR onto the release branch; merging that PR is the settlement decision and release-publish then tags the merge commit once. In `direct` mode the dispatch itself is the decision, gated by the `release` environment the consumer puts on the settle job (optionally also by `settlers`); the changelog commit is pushed straight to the release branch (the app must be a bypass actor on that branch's ruleset), and release-publish runs immediately on that commit. Run as a step in a job the consumer owns; the consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Needs `gh` and `python3` on the runner. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | GitHub App installation token (e.g. the Maxwell app). Pushes the settle branch and opens the PR so that it triggers CI. |
| `version` | yes |  | Version being settled, X.Y.Z or vX.Y.Z. |
| `commit` | yes |  | Full SHA to settle. Must be the current tip of the release branch: the settlement is a statement about a specific commit, and the tip is the only commit a later merge can build on. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json); the same value as in release-candidate. |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `release_branch` | no |  | Defaults to `<release_branch_prefix>X.Y.Z`. |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog the entry is written to (Keep-a-Changelog style, newest first). |
| `settle_mode` | no | `pr` | `pr` (default): open a settle PR. `direct`: settle and publish now, from this dispatch. |
| `settlers` | no | `any` | Who may settle in `direct` mode. `any` (default): no actor check — the settle job's `release` environment and its required reviewers are the gate, so use it only with `environment:` on that job. Otherwise a comma-separated list of GitHub logins and/or the keyword `admin` (the dispatching actor must have admin permission on the repository, checked with `github_token`), as an extra restriction on who may start a settle. |
| `github_token` | no | `${{ github.token }}` | Job token used for the `admin` permission check in `direct` mode. |
| `pr_labels` | no |  | Comma-separated labels for the settle PR (for repos whose label gates apply to release branches too). |
| `git_user_name` | no | `mega-maxwell[bot]` | Committer identity for the commits this action makes. |
| `git_user_email` | no | `290560214+mega-maxwell[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | The normalised version, X.Y.Z. |
| `pr_url` | URL of the settle PR. |
| `notes_file` | Path of the generated release-notes markdown. |
| `settled_commit` | `direct` mode: the changelog commit that was tagged. |
| `tag` | `direct` mode: the tag created. |
| `release_url` | `direct` mode: the GitHub Release created. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Configure git auth
1. Guard
1. Compare workflows with the default branch
1. Authorise the settler (direct mode) *(only if `inputs.settle_mode == 'direct'`)*
1. Generate release notes
1. Write changelog and open settle PR *(only if `inputs.settle_mode != 'direct'`)*
1. Write changelog onto the release branch (direct mode) *(only if `inputs.settle_mode == 'direct'`)*
1. Remove git auth *(only if `always()`)*
1. Tag and publish (direct mode) — `megaeth-labs/.github/.github/actions/release-publish` *(only if `inputs.settle_mode == 'direct'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `commit must be a full 40-hex SHA, got`
- `release branch $branch does not exist`
- `tag v$version already exists — this release is settled`
- `$COMMIT is not the tip of $branch (tip is $tip). Settle the tip, or move the branch first.`
- `$FILE at $COMMIT says $actual, expected $version`
- `$version is not newer than the latest tag ${latest:-<none>}`
- `$ACTOR is not authorised to settle directly (settlers: $SETTLERS)`
- `$CHANGELOG already carries exactly this v$VERSION entry; nothing to settle`
- `could not push the settle commit to $BRANCH — the branch moved since $COMMIT, or the app is not a bypass actor on its ruleset`
<!-- /generated -->

## Example

Direct mode, as in `workflow-templates/release-settle.yml` — the job
declares `environment: release`, so the run waits for that environment's
reviewers before this step runs:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-settle@main
  with:
    token: ${{ steps.app-token.outputs.token }}
    version: ${{ inputs.version }}
    commit: ${{ inputs.commit }}      # full SHA of the release-branch tip
    version_file: Cargo.toml
    version_pattern: toml
    changelog_file: CHANGELOG.md
    settle_mode: direct
    settlers: admin
```

Leave out `settle_mode` and `settlers` (and the job's `environment:`) to
settle by PR instead.

## Notes

- Guards, in order: `commit` is a full SHA; the release branch exists; the
  tag does not; `commit` is the branch tip; the version file at `commit`
  says the version; the version is newer than the latest `v*` tag. Then a
  warning if `commit` lacks a workflow the default branch has (a `release`
  event runs `on-release.yml` from the tag's tree).
- `direct`: the dispatcher must match `settlers`; the dated entry is
  committed straight onto the release branch (the app must bypass its
  ruleset) and `release-publish` runs in the same job with `commit` and
  `version` set.
- `pr`: pushes `chore/release-settle-vX.Y.Z` and opens the settle PR. A
  re-run closes the previous settle PR, deletes its branch and pushes a fresh
  one; nothing is force-pushed.
- The full flow, installation and recovery: [RELEASE.md](../RELEASE.md).
