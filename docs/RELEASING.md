# Releasing: operator runbook

How a megaeth-labs repository ships a release, who does what, and what to do
when a step stops. This page is the short operator view; the mechanics of each
action are in the [release guide](../.github/actions/RELEASE.md) and the
per-action READMEs linked below.

## Who acts: the identity model

| Identity | Does | Never does |
|---|---|---|
| `mega-gutenberg[bot]` (the release app) | Every write of the release: the candidate PR, the `release-vX.Y.Z` branch, the settle PR, the tag, the GitHub Release | Nothing is approved by it; it is not a reviewer |
| `mega-maxwell[bot]` (the CI app) | CI outside the release workflows | Mint any token in a release workflow, even read-only; appear as a git identity or PR-author filter there. Private dependency reads use a separate read-only Gutenberg token. |
| A human reviewer | Reviews and merges the candidate PR and, when needed, the settle PR; approves the `release` environment for either publish path; adds the `compat:` label where the repository requires it | - |

The [app-token lint](#app-token-lint) refuses a gutenberg token anywhere
outside the allowlisted release workflow files (`release-candidate.yml`,
`release-settle.yml`, `on-release.yml`, rule L2') on
every workflow change. The publish job runs in the
`release` environment; the jobs that propose, cut and settle run without one,
and the candidate's `refresh` job mints its token without one too.

## The four flows

Each flow starts from a push (or a merge) the previous one made; there is no
polling. The core workflows accept a candidate dispatch in flow 1 and a settle
dispatch in flows 2 and 3. The read-only `route` step
([`release-route`](../.github/actions/release-route/README.md)) decides what a
push or a dispatch means: `cut`, `refresh`, `publish` or `skip`, with a
one-sentence reason in the job log.

1. **Candidate: push to the default branch, then the cut.** An operator starts
   the Release Candidate workflow with the version (and optionally
   `base_commit`). Gutenberg opens a `chore/release-candidate-X.Y.Z` PR that
   bumps the version file and drafts the changelog entry from non-merge commit
   subjects under an undated `## vX.Y.Z` heading; the notes generator is never
   given a date. A reviewer adds the `compat:` label where required
   (see [the reviewer step](#the-reviewer-step-the-compat-label))
   and merges it. The merge is a push to the default branch; `route` finds the
   merged, gutenberg-authored candidate PR and answers `cut`, and
   [`release-candidate`](../.github/actions/release-candidate/README.md) creates
   `release-vX.Y.Z` at the merge commit. With `base_commit`, `propose` creates
   the release branch at that commit itself and aims the candidate PR at it, so
   the PR merges into the release branch and `cut` never runs.

   While a trunk candidate is open, every push to the default branch starts the
   workflow's `refresh` job for it: the refresh merges the default branch into
   the candidate's head (a merge commit, never a rebase; the branch history is
   not rewritten) and re-drafts the changelog. That push clears approvals under
   `require_last_push_approval`, so the merge must be re-approved afterwards.
   Candidates proposed with `base_commit` are not refreshed: they belong to
   their release branch and never pick up changes from trunk.

2. **Settle: push to `release-vX.Y.Z`, then the settle PR.** The creation of the
   branch (and every later push to it) starts the Release Settle workflow.
   Once the candidate has landed on the branch, `route` answers `refresh`.
   [`release-settle`](../.github/actions/release-settle/README.md) then checks
   the changelog too: if the tip equals the candidate merge, no settle PR or
   tag exists, and the section matches regenerated notes (or changelog handling
   is disabled), the state is `clean`. It writes nothing and creates no settle
   PR; publish it with the versioned dispatch in flow 3. Push routing cannot
   see changelog state, so `refresh` in the route log and `clean` in the action
   are consistent, not a failed PR creation.

   Otherwise, `needs-settle-pr` opens or updates one long-lived
   `chore/release-settle-vX.Y.Z` PR onto the release
   branch, with the changelog entry for the commits since the previous tag.
   The heading stays undated here too. New commits on the release branch
   refresh the same PR. A dispatch with a blank `version` refreshes every eligible
   release branch and never publishes; dispatching a named `version` is flow 3.

3. **Publish: merge the settle PR, or dispatch a clean branch.** Two paths,
   one publish step.

   *Merge the settle PR:* a reviewer adds the `compat:` label where required
   and merges it.
   The merge is a push to the release branch; `route` re-checks that the PR is
   gutenberg's, that it settled exactly the branch tip it was merged onto, and
   answers `publish`. This is the path a branch takes when it carries fixes on
   top of the candidate: the fixes refresh the settle PR, and merging it is the
   release decision.

   *The branch is exactly the candidate merge:* settlement is state-derived.
   Dispatch Release Settle with `version` and `route` computes the settlement
   state from the repository: the candidate PR's merge commit, whether that
   commit is an ancestor of the branch tip, whether a settle PR is open, and
   whether the tag and the GitHub Release exist. A clean state (the tip equals
   the candidate merge, no settle PR is open, the version is unpublished)
   routes to `publish` with `settle_source=dispatch`. Dispatch routing does not
   compare the changelog section; publish checks it against regenerated notes
   and refuses a mismatch before tagging. Refresh first with a blank-version
   dispatch if that happens. Commits beyond the candidate merge or an open settle PR
   route to `refresh` instead. A version whose tag and Release both exist is
   skipped when its tag is at the candidate merge, and so is one whose candidate
   is not an ancestor of the tip. A tag elsewhere is blocked by this dispatch
   path, including one created from a settle PR; re-run that publication's
   original push-triggered run to recover it. A tag
   that exists at the candidate merge without its Release (a run that died
   between the two steps) routes to `publish` again and resumes.

   Both paths run [`release-publish`](../.github/actions/release-publish/README.md)
   in the review-gated `release` environment, so the dispatch path also waits
   for a human approval. Publish re-reads the PR through the API (the settle PR
   for a push; the candidate PR and the current branch tip for a dispatch,
   checked again right before the tag push), creates the annotated tag `vX.Y.Z`
   at the merge commit once, and publishes the GitHub Release. The Release body
   is the version's changelog section as written in the tagged tree, verbatim;
   no date is injected. A settle PR that went stale before it merged publishes
   nothing; `route` answers `refresh` and a fresh PR follows.

4. **Assets: publishing the Release fires On Release.** The `release: published`
   event runs the repository's `on-release.yml`, which builds, verifies the
   version ([`release-verify-version`](../.github/actions/release-verify-version/README.md)),
   uploads ([`release-upload-artifact`](../.github/actions/release-upload-artifact/README.md)),
   attaches [release assets](../.github/actions/release-assets/README.md), and
   publishes crates.

## Environments and their variables

| Environment | Holds | Deployment policy | Reviewers |
|---|---|---|---|
| `release` | `CARGO_REGISTRY_TOKEN`, `GCP_AUTH_KEY` (the publish targets) | default branch, `release-v*` branches and tags `v*` | one, required: a versioned dispatch publishes without a PR, so the environment review is its approval |
| `snapshot` | `GCP_AUTH_KEY` for snapshot uploads | the branch the workflow is dispatched from | none; outside the release review gate |

`release` is the single gated environment for tagging, Release creation and
artifact upload; snapshots use `snapshot`. The release-app credentials (`MEGA_GUTENBERG_CLIENT_ID`
variable, `MEGA_GUTENBERG_PK` secret) resolve at organization scope, with
the organization secret granted access to each consumer repository, so
the candidate's `refresh` job mints its token with no environment.

`environment: release` may appear only in
`release-candidate.yml`, `release-settle.yml` and `on-release.yml` (lint rule
L5).

Rulesets the app relies on:

- `v*` tag ruleset: bypass actors are the repository admin role and
  mega-gutenberg. No other app.
- `release-*` branch ruleset: no app bypass, so the settle PR is genuinely
  reviewed. Required checks use `do_not_enforce_on_create: true`; "require
  branches to be up to date" is on; merge methods include squash or merge, not
  rebase only.
- No exemption from a `prohibit-force-push` ruleset is needed, even one that
  covers all branches (mega-reth's does): nothing in the pipeline force-pushes
  any branch. A re-dispatched candidate supersedes the open one: it closes
  that PR with a comment, deletes its `chore/release-candidate-*` branch,
  pushes a fresh one as a new ref and opens a fresh PR. A re-run settle
  fast-forwards its own open PR's branch, or closes a PR it does not maintain
  and starts a new branch. The app does need to delete those branches, so a
  ruleset that restricts deletions must not cover `refs/heads/chore/release-*`.

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
The candidate and settle workflows have no dry-run: the candidate and the
settle refresh produce PRs, which are themselves the preview, and the publish
path is gated by the `release` environment's review instead.

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

Each template ships with a `.properties.json` sidecar for the organization's
"New workflow" picker; consumers copy the YAML into `.github/workflows/`,
not the sidecar. The core templates use `VERSION` with `version_pattern: plain`;
the bump command is a commented example, not an enabled Cargo setup. Use
`.github/scripts/copy_templates.py` to render the core workflows with the
repository's version file, pattern, bump command and private dependency repos.

Required PR checks must run for PRs targeting `release-v*`, not just the
default branch. For example, a consumer `lint.yml` with
`pull_request.branches: [main]` needs `[main, "release-v*"]` (use the actual
default branch). Check test and label workflows too, including job conditions
and path filters. A candidate aimed at a release branch otherwise has no
required checks, and the follow-up settle PR has the same problem. For
`base_commit` candidates, add the corrected lint/test workflows to
`release_workflows` so they are carried from the default branch in the candidate
PR; the default list carries only `release-settle.yml` and `on-release.yml`.
An existing release branch needs those CI changes carried onto it too.

## The reviewer step: the `compat:` label

Where the consumer requires it, every PR into the default branch or a
`release-*` branch must carry a label starting with `compat:` (for example,
mega-reth's "Compatibility Label Check" in `pr-title.yml`). This is a consumer
check, not a gate implemented by the shared release actions.
The patch/minor/major call is a per-release judgement, so
the pipeline leaves `pr_labels` empty on the candidate and settle PRs. The
reviewer adds the label to both PRs while reviewing. Mega-reth's `pr-title.yml` also
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
| `not refreshing a settle PR: vX.Y.Z is not newer than the latest published tag vA.B.C (rule: …)` | The branch is not newer than the latest `vX.Y.Z` tag. Not a release. |
| `refusing to publish settle PR #N: vX.Y.Z is not newer than the latest published tag vA.B.C (rule: a version is published only when it is newer than every vX.Y.Z tag)` | An older line (a hotfix branch) was settled after a newer release was published. It is not tagged, so the newer Release stays latest. Cut the fix as a version above vA.B.C instead. |
| `vX.Y.Z is already published` | The tag and the Release both exist. |
| `merged settle PR #N was stale (settled …, tip was …); a fresh settle PR follows` | The branch moved after the settle PR was written. Review and merge the fresh PR. |
| `vX.Y.Z is tagged but has no Release: re-run the release-settle run for the settle PR's merge commit … to finish publishing` (also a `::warning::`) | `publish` died between tag and Release. For a settle-PR publication, re-run the original push-triggered run at that merge commit. A versioned dispatch resumes only a tag at the candidate merge, not a settle-PR merge. |
| `vX.Y.Z already has a published tag and Release` | A versioned dispatch named a finished release. Nothing to do. |
| `candidate merge … is not an ancestor of tip …` | A versioned dispatch, but the branch history no longer contains the candidate merge (rewritten, or the wrong branch). Skipped; restore the branch or start the release again. |
| `vX.Y.Z points to …, not candidate merge …` | Versioned dispatch blocks a tag not at the candidate merge. A settle-PR merge tag is legitimate: re-run its original push-triggered run if its Release is missing. Investigate any other unexpected tag target. |
| `release branch release-vX.Y.Z does not exist` | A versioned dispatch named a version that was never cut. |
| `no route for kind=…, event=…, ref=…` | The event is not one the pipeline handles. |

### Errors from the actions

| Message | Meaning and action |
|---|---|
| `release-route needs full history; check out with fetch-depth: 0` | The route job's checkout is shallow. |
| `cannot read the version file: FILE does not exist at … ` / `… does not parse with version_pattern '…'` | The route's `version_file` or `version_pattern` does not match the repository (or the settle step). The route fails, it does not skip: fix the workflow. |
| `cut needs the commit and pr_number inputs (the release-route outputs)` | The `cut` job did not pass the route outputs. |
| `candidate PR #N has not been merged; cut only runs for a merged candidate` | `cut` ran for a PR that was closed unmerged. |
| `candidate PR #N targets '…', not the default branch '…'` | Only a candidate merged into the default branch is cut. |
| `branch <name> already exists: vX.Y.Z was already cut from its merged candidate, so there is nothing left to propose; settle it from <name>` | The release was proposed before. Settle the existing branch, or delete it and propose again. |
| `release candidates start from the default branch (…); this run is on …` | Dispatch the candidate workflow from the default branch. |
| `base_commit … is not reachable from the default branch (…); a release must ship code that landed on trunk` | Choose a commit reachable from the default branch, or on the latest release line between its merge-base with trunk and the latest exact `vX.Y.Z` tag. Other side branches are refused. |
| `$FILE at $COMMIT says X, expected Y` | The version file does not carry the release version at that commit. |
| `could not merge … into …; close the settle PR so the next run recreates it` | A refresh conflicts with the settle PR branch. Close the settle PR; the next settle run recreates it. |
| `… is not the tip of release-vX.Y.Z (tip is …). Settle the tip, or move the branch first.` | The branch moved while the settle ran. Re-run on the current tip. |
| `release branch drifted: settle PR settled X but the branch tip at merge was Y. Re-run release-settle on the current tip.` | The settle PR was merged after the branch moved. Re-run, review the fresh PR. |
| `settle PR body has no '<!-- release-settle: ... -->' marker; refusing to publish an unverifiable settlement` | The settlement cannot be verified. The PR is already merged on this path: refresh the current release tip with a blank-version settle dispatch and review the replacement PR; do not invent a marker. |
| `settle PR #N was opened by '…', not by 'mega-gutenberg[bot]' …; refusing to publish from it` | A hand-made settle PR never publishes. |
| `tag vX.Y.Z already exists (at …), not at …; a release is published once` | Publish refuses to retag. Investigate the existing tag. |
| `Refusing to publish an older version::settle PR #N: vX.Y.Z is not newer than the latest published tag vA.B.C …` | Publish re-checks the route's order rule, in the guard and again right before the tag push. Nothing was tagged. |
| `::warning title=Not the latest Release::vX.Y.Z is published without becoming latest …` | A newer Release was published while this one was in flight. The Release exists but GitHub's "latest" stays on the newer one. |
| `release-vX.Y.Z moved to … after this refresh of … started …` | A refresh lost the race to a settle-PR merge or a newer push. It wrote nothing; the run for the new tip refreshes the settle PR. |
| `::notice title=Already tagged::vX.Y.Z is already tagged, so this refresh … does not open or update a settle PR for it` | The release was published while this refresh ran. Nothing to do. |
| `settle_source must be pr or dispatch, got '…'` | The publish job's wiring is broken; fix the workflow. |
| `changelog section for vX.Y.Z at … disagrees with regenerated notes; let the settle refresh land first, then publish.` | Dispatch routing does not compare notes. Dispatch with a blank `version` to refresh; review and merge the resulting settle PR rather than retrying the unchanged versioned dispatch. |
| `candidate PR #N is not merged` / `candidate PR #N merge_commit_sha is '…', not the requested commit …` | A dispatch publish, but the candidate PR route resolved is not the merged candidate for this version. |
| `release_branch is required for dispatch settlement` | The publish job did not pass the route's `release_branch` output. |
| `candidate PR #N head ref is '…', expected chore/release-candidate-X.Y.Z` / `candidate PR #N base is '…', expected '…' or '…'` / `candidate PR #N author is '…', expected '…'` | A dispatch publish re-verifies the candidate PR through the API and refuses a PR that is not gutenberg's candidate into the default or release branch. |
| `release branch '…' tip is '…'; a fresh publish without a tag requires exact tip equality …` / `… resuming an existing tag requires … to be an ancestor of the tip …` | The branch moved or no longer contains the tagged candidate. A new versioned dispatch refreshes a moved, untagged branch through a settle PR; an existing candidate tag can resume only while it remains an ancestor. |
| `::warning::… lacks workflows that <default> has: …` | The release branch is missing a workflow that the default branch has (usually `on-release.yml`). A release-event workflow runs from the tagged commit's tree, so add it to the branch through its own PR before merging the settle PR, or the Release publishes with nothing attached. |

### App-token lint errors

Each is reported as `::error file=<path>::<job>/<step>: <rule>: <message>`.

| Code | Message | Fix |
|---|---|---|
| L1 | `Maxwell token requests permission-contents: write; Maxwell may only write pull-requests and issues` | Drop the permission, or mint a gutenberg token in one of the allowlisted release workflow files. A `permission-…` that is an expression is refused too. |
| L2' | `Gutenberg token may be minted only in on-release.yml, release-candidate.yml, release-settle.yml; file is …` | Move the token step into one of the three exact allowlisted release workflow files; filename prefixes do not grant access. |
| L3 | `no Maxwell token in a release workflow; mint a Gutenberg token instead` | Replace the Maxwell token. |
| L3 | `read-only dependency token names the repository itself (…)` | Remove the repository from `repositories:`; the checkout uses the job token. |
| L4 | `mega-maxwell[bot] is not a release identity` | Use `mega-gutenberg[bot]` as git identity and PR-author filter. |
| L5 | ``environment `release` is only for on-release.yml, release-candidate.yml, release-settle.yml`` | Move the job, or use a different environment. |
| L6 | `Maxwell token requests no permission-* inputs, so it gets every permission of the installation (contents write included); list the permissions it needs` (also for Gutenberg, and for any app token in a release job) | Add the `permission-<x>:` inputs the job needs. |
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
