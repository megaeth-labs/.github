# Releasing: operator runbook

How a megaeth-labs repository ships a release, who does what, and what to do
when a step stops. This page is the short operator view; the mechanics of each
action are in the [release guide](../.github/actions/RELEASE.md) and the
per-action READMEs linked below.

## Who acts: the identity model

| Identity | Does | Never does |
|---|---|---|
| `mega-gutenberg[bot]` (the release app) | Every write of the release: the candidate PR, the `release-vX.Y.Z` branch, the settle PR, the tag, the GitHub Release, the dist-docs PR | Nothing is approved by it; it is not a reviewer |
| `mega-maxwell[bot]` (the CI app) | Only ever reads, as far as a release is concerned: at most a read-only token for private dependencies | Create a branch, PR, tag or Release of a release; appear as a git identity or PR-author filter in a release workflow |
| A human reviewer | Reviews and merges the candidate PR and the settle PR; adds the `compat:` label | - |

The gutenberg token can be minted only in a job that runs in the `release`
environment. The [app-token lint](#app-token-lint) enforces both halves of this
split on every workflow change.

## The four flows

Each flow ends in a push (or a merge) that the next flow listens for; there is
no polling. The read-only `route` step ([`release-route`](../.github/actions/release-route/README.md))
decides what a push means: `cut`, `refresh`, `publish` or `skip`, with a
one-sentence reason in the job log.

1. **Candidate: push to the default branch, then the cut.** An operator starts
   the Release Candidate workflow with the version (and optionally
   `base_commit`). Gutenberg opens a `chore/release-candidate-vX.Y.Z` PR that
   bumps the version file and drafts the changelog entry. A reviewer adds the
   `compat:` label (see [the reviewer step](#the-reviewer-step-the-compat-label))
   and merges it. The merge is a push to the default branch; `route` finds the
   merged, gutenberg-authored candidate PR and answers `cut`, and
   [`release-candidate`](../.github/actions/release-candidate/README.md) creates
   `release-vX.Y.Z` at the merge commit. With `base_commit`, the PR targets a
   release branch that `propose` already cut, so there is no `cut`.
2. **Settle: push to `release-vX.Y.Z`, then the settle PR.** The creation of the
   branch (and every later push to it) starts the Release Settle workflow.
   Once the candidate has landed on the branch, `route` answers `refresh` and
   [`release-settle`](../.github/actions/release-settle/README.md) opens or
   updates one long-lived `chore/release-settle-vX.Y.Z` PR onto the release
   branch, with the changelog entry for the commits since the previous tag. New
   commits on the release branch refresh the same PR. A manual dispatch refreshes
   every eligible release branch (or the one named by `version`) and never
   publishes.
3. **Tag: merge the settle PR.** A reviewer adds the `compat:` label and merges
   the settle PR. That is the release decision; nothing waits for a click on a
   run. The merge is a push to the release branch; `route` re-checks that the PR
   is gutenberg's, that it settled exactly the branch tip it was merged onto, and
   answers `publish`. [`release-publish`](../.github/actions/release-publish/README.md)
   then creates the annotated tag `vX.Y.Z` at the merge commit (once) and the
   GitHub Release with the changelog section as notes. A settle PR that went stale
   before it merged publishes nothing; `route` answers `refresh` and a fresh PR
   follows.
4. **Assets: the tag push (the Release) fires On Release.** Publishing the
   Release runs the repository's `on-release.yml`, which builds, verifies the
   version ([`release-verify-version`](../.github/actions/release-verify-version/README.md)),
   uploads ([`release-upload-artifact`](../.github/actions/release-upload-artifact/README.md)),
   attaches [release assets](../.github/actions/release-assets/README.md), and
   publishes crates. Repositories that keep release notes in `dist-docs` (mega-reth)
   also open the dist-docs PR in this workflow, as gutenberg.

## Environments and their variables

| Environment | Holds | Deployment policy | Reviewers |
|---|---|---|---|
| `release` | variable `RELEASE_APP_CLIENT_ID` (the app's Client ID, not the numeric App ID); secret `RELEASE_APP_PRIVATE_KEY` | the default branch and `release-v*` branches (add the tag `v*` only where a release-event job needs gutenberg, such as mega-reth's dist-docs job) | none: merging the settle PR is the decision |
| `publish` | `CARGO_REGISTRY_TOKEN`, `GCP_AUTH_KEY` (the publish targets) | tags `v*` | none |

`environment: release` appears only in `release-candidate.yml`,
`release-settle.yml` and `on-release.yml` (lint rule L5). A job in `publish` that
only reads private dependencies may also mint a gutenberg token, but only with
`permission-contents: read` (L2).

Rulesets the app relies on:

- `v*` tag ruleset: bypass actors are the repository admin role and
  mega-gutenberg. No other app.
- `release-*` branch ruleset: no app bypass, so the settle PR is genuinely
  reviewed. Required checks use `do_not_enforce_on_create: true`; "require
  branches to be up to date" is on; merge methods include squash or merge, not
  rebase only.
- A repository whose `prohibit-force-push` ruleset covers all branches (mega-reth
  does) must exempt the release app for `refs/heads/chore/release-*`;
  otherwise the update of the candidate or settle PR branch is rejected.

## The dry-run flag

`on-release.yml` has a `dry_run` input, true by default when dispatched. A
rehearsal runs every job (build, verify, check destinations, `cargo publish
--dry-run`) and uploads, publishes and attaches nothing. Start it from the
Actions tab with the workflow's ref set to the tag `vX.Y.Z` and `dry_run`
ticked; a run started by the Release event is never a dry run. The same flag
exists as `dry_run` on [`release-assets`](../.github/actions/release-assets/README.md),
[`release-upload-artifact`](../.github/actions/release-upload-artifact/README.md),
[`release-publish-rust-crates`](../.github/actions/release-publish-rust-crates/README.md)
and [`release-verify-version`](../.github/actions/release-verify-version/README.md).
The candidate and settle workflows have no dry-run: their output is a PR, which
is itself the preview.

## Copying a template

The reference callers live in [`workflow-templates/`](../workflow-templates/).
In a repository, use "New workflow → By megaeth-labs", or copy the file by
hand and edit the placeholders (version file, changelog, destinations). For
example, to copy the snapshot template into a clone of your repository:

```sh
cp workflow-templates/snapshot-publish.yml /path/to/my-repo/.github/workflows/
```

Copy the release templates the same way: `release-candidate.yml`,
`release-settle.yml`, `on-release.yml` and `app-token-lint.yml`. Then check the
copy before pushing (from a checkout of this repository):

```sh
python3 .github/scripts/app_token_lint.py --repo my-repo /path/to/my-repo/.github/workflows
```

> The release templates are being rewritten for the push-driven flow in a
> separate change; `workflow-templates/README.md` is not part of this commit,
> so this page links the directory rather than that file.

## The reviewer step: the `compat:` label

Every PR into the default branch or a `release-*` branch must carry a label
starting with `compat:` (mega-reth's required check "Compatibility Label Check",
in `pr-title.yml`). The patch/minor/major call is a per-release judgement, so
the pipeline leaves `pr_labels` empty on the candidate and settle PRs. The
reviewer adds the label to both PRs while reviewing. `pr-title.yml` also
listens for `labeled`, so adding the label re-runs the check and turns it green;
no push or manual re-run is needed.

## Troubleshooting

Messages are quoted from the actions and from
[`app_token_lint.py`](../.github/scripts/app_token_lint.py). `::error::` stops the
run; `::warning::` and the route `skip` reason do not.

### Route says skip

| Message | Meaning and action |
|---|---|
| `no merged candidate PR matches this push` | A push to the default branch that is not the merge of a candidate PR. Normal for every other push. |
| `PR #N author X does not match mega-gutenberg[bot]` | The PR was not opened by gutenberg (for example a hand-made or pre-migration PR). It never cuts or publishes. Close it and start the release again. |
| `the candidate has not landed on this branch yet` | The release branch still has the old version. Nothing to do until the candidate PR merges into it. |
| `vX.Y.Z is not greater than latest tag` | The branch is older than the latest tag. Not a release. |
| `vX.Y.Z is already published` | The tag and the Release both exist. |
| `merged settle PR #N was stale (settled …, tip was …); a fresh settle PR follows` | The branch moved after the settle PR was written. Review and merge the fresh PR. |
| `vX.Y.Z is tagged but has no Release: re-run the release-settle run for the settle PR's merge commit … to finish publishing` (also a `::warning::`) | `publish` died between tag and Release. Re-run the failed run for that merge commit; it creates the missing Release. |
| `no route for kind=…, event=…, ref=…` | The event is not one the pipeline handles. |

### Errors from the actions

| Message | Meaning and action |
|---|---|
| `release-route needs full history; check out with fetch-depth: 0` | The route job's checkout is shallow. |
| `cut needs the commit and pr_number inputs (the release-route outputs)` | The `cut` job did not pass the route outputs. |
| `candidate PR #N has not been merged; cut only runs for a merged candidate` | `cut` ran for a PR that was closed unmerged. |
| `candidate PR #N targets '…', not the default branch '…'` | Only a candidate merged into the default branch is cut. |
| `branch <name> already exists` | The branch was cut before. If the release was abandoned, delete the branch and propose again. |
| `release candidates start from the default branch (…); this run is on …` | Dispatch the candidate workflow from the default branch. |
| `base_commit … is not reachable from the default branch (…); a release must ship code that landed on trunk` | Choose a commit that is on the default branch. |
| `$FILE at $COMMIT says X, expected Y` | The version file does not carry the release version at that commit. |
| `could not merge … into …; close the settle PR so the next run recreates it` | A refresh conflicts with the settle PR branch. Close the settle PR; the next settle run recreates it. |
| `… is not the tip of release-vX.Y.Z (tip is …). Settle the tip, or move the branch first.` | The branch moved while the settle ran. Re-run on the current tip. |
| `release branch drifted: settle PR settled X but the branch tip at merge was Y. Re-run release-settle on the current tip.` | The settle PR was merged after the branch moved. Re-run, review the fresh PR. |
| `settle PR body has no '<!-- release-settle: ... -->' marker; refusing to publish an unverifiable settlement` | The PR body was edited. Close it and let settle recreate it. |
| `settle PR #N was opened by '…', not by 'mega-gutenberg[bot]' …; refusing to publish from it` | A hand-made settle PR never publishes. |
| `tag vX.Y.Z already exists … and is not an unfinished release of …; a release is published once` | Publish refuses to retag. Investigate the existing tag. |
| `::warning::… lacks workflows that <default> has: … — a release-event workflow runs from the tagged commit's tree …` | The release branch is missing a workflow that the default branch has (usually `on-release.yml`). Add it to the branch through its own PR before merging the settle PR, or the Release publishes with nothing attached. |

### App-token lint errors

Each is reported as `::error file=<path>::<job>/<step>: <rule>: <message>`.

| Code | Message | Fix |
|---|---|---|
| L1 | `Maxwell token requests permission-contents: write; Maxwell may only write pull-requests and issues` | Drop the permission, or mint a gutenberg token in a release job. A `permission-…` that is an expression is refused too. |
| L2 | ``Gutenberg token needs `environment: release` (or `publish` with only permission-contents: read), job has none`` | Put the job in `environment: release`. |
| L3 | `no Maxwell token in a release workflow; mint a Gutenberg token instead` | Replace the Maxwell token. |
| L3 | `read-only dependency token names the repository itself (…)` | Remove the repository from `repositories:`; the checkout uses the job token. |
| L4 | `mega-maxwell[bot] is not a release identity` | Use `mega-gutenberg[bot]` as git identity and PR-author filter. |
| L5 | ``environment `release` is only for release-candidate.yml, release-settle.yml and on-release.yml`` | Move the job, or use a different environment. |
| parse | `malformed YAML …`, `not a workflow: the document is not a mapping`, `no such file or directory`, `no workflow files (*.yml, *.yaml) found` | Fix the input; a file that cannot be read never lints clean. |

## App-token lint

The check is `app-token-lint` ([README](../.github/actions/app-token-lint/README.md)),
run on every workflow change through the `app-token-lint.yml` template. Its
unit tests run in this repository's `actions-test.yml`. See the
[root README](../README.md#app-tokens-maxwell-and-gutenberg) for the rules in
one paragraph.

## Keeping this page honest

The generated tables in the action READMEs must match their `action.yml` (`python3 .github/scripts/action_docs.py` rewrites them). Confirm nothing drifted:

```sh
python3 .github/scripts/action_docs.py --check
```
