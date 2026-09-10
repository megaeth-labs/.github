# Shared actions

Composite actions every megaeth-labs repository consumes at `@main`. Two
families and one standalone action; each action directory has a README whose
input, output, step and error tables are generated from its `action.yml`.

<!-- generated: catalogue -->
| Action | Family | Does |
|---|---|---|
| [`claude-interactive`](claude-interactive/README.md) | [Claude CI](CLAUDE-CI.md) | Run the interactive @claude handler with centralized MegaETH permissions. |
| [`claude-issue-triage`](claude-issue-triage/README.md) | [Claude CI](CLAUDE-CI.md) | Run the centralized MegaETH Claude issue triage. |
| [`claude-label-check`](claude-label-check/README.md) | [Claude CI](CLAUDE-CI.md) | Run the centralized MegaETH Claude pull request label check. |
| [`claude-pr-review`](claude-pr-review/README.md) | [Claude CI](CLAUDE-CI.md) | Run the staged, incremental MegaETH Claude pull request review. |
| [`pr-lint`](pr-lint/README.md) | Standalone | Lint a pull request. Currently validates that the PR title follows Conventional Commits, posting a sticky comment on failure and removing it once fixed; further PR-level lint steps can be added here over time. Run as a step inside a job the consumer names, so the resulting status-check context is that job name. |
| [`release-assets`](release-assets/README.md) | [Release pipeline](RELEASE.md) | Attach files, plus a generated `SHA256SUMS`, to the GitHub Release for a tag. Re-runs replace assets of the same name (`--clobber`), so the step is idempotent. `dry_run` writes and prints `SHA256SUMS` but attaches nothing. Needs a token with `contents: write` on the repository (the job token is enough). Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-candidate`](release-candidate/README.md) | [Release pipeline](RELEASE.md) | Start a release (trunk-first). `stage: propose` bumps the version file on the default branch, drafts this release's changelog entry (dated at settle) from the commits since the previous tag, syncs the previous release's entry from its tag, and opens a `chore/release-candidate-vX.Y.Z` PR; `stage: cut`, run when that PR merges, creates `release-vX.Y.Z` at the merge commit. No tag is created at either stage — tags come from release-publish, once, at settlement. Run as a step in a job the consumer owns; the consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-publish`](release-publish/README.md) | [Release pipeline](RELEASE.md) | Publish a settled release. Normally runs when a `chore/release-settle-vX.Y.Z` PR merges into its release branch (or, with `commit` + `version` given, on an explicit commit that `release-settle` in `direct` mode just made): creates the annotated tag `vX.Y.Z` at the merge commit (exactly once — refuses if it exists, or if the branch moved after the settle PR was opened) and publishes the GitHub Release with the changelog section as notes. This is the only place in the release flow that creates a tag; merging the settle PR is the approval. The default branch's changelog catches up in the next release candidate PR — nothing is back-merged. The consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-publish-rust-crates`](release-publish-rust-crates/README.md) | [Release pipeline](RELEASE.md) | Publish an explicit list of workspace crates to crates.io at the release version. Verifies every listed crate's manifest version first, skips crates already published at that version (so a re-run after a partial failure finishes the rest), publishes the remainder in one `cargo publish -p … -p …` invocation — Cargo orders by dependency and waits for the index between crates (requires Cargo ≥ 1.90) — then polls crates.io until every crate reports the version. `dry_run` runs `cargo publish --dry-run`: full packaging and build verification, nothing uploaded. Run inside a job that has checked out the release tag and installed the toolchain the crates need. Never use `--workspace`: a crate without `publish = false` that was never meant to be published would go out with it. Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-settle`](release-settle/README.md) | [Release pipeline](RELEASE.md) | Propose settling a release candidate: verify `commit` is the tip of the release branch and carries the expected version, generate release notes from the commits since the previous tag, write them into the changelog (stamping the date onto the candidate's `## vX.Y.Z` entry), and — in the default `pr` mode — open a `chore/release-settle-vX.Y.Z` PR onto the release branch; merging that PR is the settlement decision and release-publish then tags the merge commit once. In `direct` mode the dispatch itself is the decision, gated by the `release` environment the consumer puts on the settle job (optionally also by `settlers`); the changelog commit is pushed straight to the release branch (the app must be a bypass actor on that branch's ruleset), and release-publish runs immediately on that commit. Run as a step in a job the consumer owns; the consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Needs `gh` and `python3` on the runner. Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-snapshot`](release-snapshot/README.md) | [Release pipeline](RELEASE.md) | The two bookends of a snapshot publish — a build of one commit pushed to the artifact registry with no tag and no GitHub Release, for components that deployments pin by commit. `stage: resolve` turns `ref` (a branch, tag or commit; empty means the run's own commit) into the coordinates the upload steps need: the full commit, and the registry `version` (the commit) and `path` (`<profile>/<label>`, e.g. `release/latest`) that match how deployment tooling addresses a snapshot. With `allowed_branches` it refuses a commit that is not reachable from one of those branches, so a dispatch cannot publish an unreviewed commit even though the environment only authorises the branch the workflow ran from. `stage: summary` writes the run summary after the uploads: where each file went, its checksum, and the manifest entry (`commit`, `version`, `profile`) a deployment repository pins; optionally it also records a commit status per package so the commit page shows what was published. Needs a checkout with history for `resolve` (the branch guard uses `merge-base`); nothing here is organisation-specific. Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-upload-artifact`](release-upload-artifact/README.md) | [Release pipeline](RELEASE.md) | Upload one file to Google Artifact Registry (generic repository) or a Cloud Storage bucket, idempotently: if the destination already holds a file, its hash is compared — identical means "already there" (success, nothing uploaded), different means failure, never a silent overwrite. Every destination is an input; nothing is defaulted. Authentication is the caller's job: run `google-github-actions/auth` (service-account key or Workload Identity Federation) before this step so `gcloud` is authenticated. `dry_run` computes the checksum and checks the destination but uploads nothing. Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
| [`release-verify-version`](release-verify-version/README.md) | [Release pipeline](RELEASE.md) | Run a command that prints a built artifact's version (`my-binary --version`) and require the output to match the release version, so a binary built from the wrong tree — or a tag that does not match the manifest — never reaches a publish step. By default the expected output is `<name> <version>` (the clap shape: the command's basename, then the version without its leading `v`); `expected` overrides it. A command that cannot run at all — missing library, crash, no such flag — fails the step even on a dry run: an artifact that does not execute is never publishable, and its exit code is never swallowed. A mismatch is a warning on a dry run, so a rehearsal reports what a real run would refuse and carries on, and a hard stop otherwise. Guide: .github/actions/RELEASE.md in megaeth-labs/.github. |
<!-- /generated -->

Family guides, next to the actions they cover:

- [RELEASE.md](RELEASE.md) — the release pipeline: candidate, settle,
  publish, publish targets; how it works, installing it in a repository,
  options, recovery.
- [CLAUDE-CI.md](CLAUDE-CI.md) — the Claude checks: PR review, label check,
  issue triage, interactive; how a round runs, installing, options,
  inspecting a run.

`release-tools/` is not an action: it holds the text helpers the release
actions share ([README](release-tools/README.md)).

## Consuming an action

- Reference it as `megaeth-labs/.github/.github/actions/<name>@main`. A merge
  to `main` here reaches every consumer at once; nothing is pinned.
- This repository's Settings → Actions → Access allows organisation
  repositories to use these actions (already set).
- Actions carry no organisation-specific defaults beyond the CI app's
  identity; everything else (secrets, destinations, files) is an input, and
  the templates under `workflow-templates/` carry this organisation's values.

## Changing an action

- `actions-test.yml` is the only gate: the unit tests of
  `claude-pr-review/review_pipeline.py` and `release-tools/*.py`, the
  end-to-end drive of `release-verify-version`, and the documentation check.
- After editing an `action.yml`, run `.github/scripts/action_docs.py`: it
  rewrites the generated blocks in that action's README and the catalogue
  above. CI runs it with `--check` and fails if the docs are stale. Prose
  outside the generated blocks is written by hand.
- A new action needs a directory with `action.yml`; the script creates its
  README skeleton, whose `Example` and `Notes` sections you then fill in.
- Templates in `workflow-templates/` are the reference callers: keep them in
  step with the actions they call.
