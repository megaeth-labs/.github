# Release · Snapshot

`uses: megaeth-labs/.github/.github/actions/release-snapshot@main`

<!-- generated: description -->
The two bookends of a snapshot publish — a build of one commit pushed to the artifact registry with no tag and no GitHub Release, for components that deployments pin by commit. `stage: resolve` turns `ref` (a branch, tag or commit; empty means the run's own commit) into the coordinates the upload steps need: the full commit, and the registry `version` (the commit) and `path` (`<profile>/<label>`, e.g. `release/latest`) that match how deployment tooling addresses a snapshot. With `allowed_branches` it refuses a commit that is not reachable from one of those branches, so a dispatch cannot publish an unreviewed commit even though the environment only authorises the branch the workflow ran from. `stage: summary` writes the run summary after the uploads: where each file went, its checksum, and the manifest entry (`commit`, `version`, `profile`) a deployment repository pins; optionally it also records a commit status per package so the commit page shows what was published. Needs a checkout with history for `resolve` (the branch guard uses `merge-base`); nothing here is organisation-specific. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `stage` | yes |  | `resolve` (before the build) or `summary` (after the uploads). |
| `ref` | no |  | Branch, tag or commit to publish. Empty: the run's own commit (`github.sha`). |
| `allowed_branches` | no |  | Comma-separated branches the commit must be reachable from (`origin/<branch>` after a full checkout). Empty: no guard. |
| `profile` | no | `release` | Build profile that names the first path segment (`release`, `profiling`, …). |
| `label` | no | `latest` | Second path segment. Snapshots use `latest`; the deployment manifest pins the commit. |
| `commit` | no |  | (summary) The commit that was published — the `commit` output of the resolve stage. |
| `entries` | no |  | (summary) One line per uploaded file: `<package> <uri> <sha256> <status>`, the outputs of `release-upload-artifact` (`status` is `uploaded`, `exists` or `dry-run`). |
| `record_status` | no | `false` | (summary) `true`: create a commit status `snapshot/<package>` on the commit for every entry, linking to this run; needs `token` with `statuses: write`. Dry runs record nothing. |
| `token` | no | `${{ github.token }}` | (summary) Token for the commit statuses. |
| `dry_run` | no | `false` | `true`: the summary says so and no status is recorded. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `commit` | (resolve) The full commit SHA that will be built. |
| `short` | (resolve) Its 12-character prefix. |
| `version` | (resolve) The registry version to upload under — the commit. |
| `path` | (resolve) The registry path to upload under — `<profile>/<label>`. |
| `describe` | (resolve) `git describe --tags --always` of the commit, for logs and binaries. |
| `branch` | (resolve) The first of `allowed_branches` the commit was found on (empty when no guard). |
| `packages` | (summary) Comma-separated package names from `entries`. |
| `manifest` | (summary) The manifest entries as YAML text, `<package>` → `commit`, `version`, `profile` per package, for a follow-up that pins them somewhere. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Resolve the commit *(only if `inputs.stage == 'resolve'`)*
1. Write the summary *(only if `inputs.stage == 'summary'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `not a git checkout; check the repository out first (fetch-depth: 0)`
- `profile must be a plain word, got`
- `label must be a plain word, got`
- `cannot resolve`
- `$ref (${commit:0:12}) is not on any allowed branch ($ALLOWED); refusing to publish a commit that has not landed there`
- `commit must be the full SHA from the resolve stage, got`
- `entries is empty; pass one`
- `malformed entry:`
<!-- /generated -->

## Example

The two bookends of `workflow-templates/snapshot-publish.yml`; the build and
the uploads sit between them:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0                       # the branch guard needs history

- uses: megaeth-labs/.github/.github/actions/release-snapshot@main
  id: snapshot
  with:
    stage: resolve
    ref: ${{ inputs.ref }}               # empty: this run's commit
    allowed_branches: main               # refuse anything not landed on main
    profile: release

- run: git checkout --quiet ${{ steps.snapshot.outputs.commit }}
- run: cargo build --release -p my-binary

- uses: google-github-actions/auth@v3
  with:
    credentials_json: ${{ secrets.GCP_AUTH_KEY }}

- uses: megaeth-labs/.github/.github/actions/release-upload-artifact@main
  id: upload
  with:
    file: target/release/my-binary
    kind: artifact-registry
    project: my-gcp-project
    location: my-region
    repository: my-generic-repository
    package: my-binary
    version: ${{ steps.snapshot.outputs.version }}   # the commit
    path: ${{ steps.snapshot.outputs.path }}         # release/latest

- uses: megaeth-labs/.github/.github/actions/release-snapshot@main
  with:
    stage: summary
    commit: ${{ steps.snapshot.outputs.commit }}
    entries: |
      my-binary ${{ steps.upload.outputs.uri }} ${{ steps.upload.outputs.sha256 }} ${{ steps.upload.outputs.status }}
    record_status: "true"                # needs statuses: write
```

The run summary then carries the table of uploads and the manifest entry a
deployment repository pins:

```yaml
my-binary:
  commit: "<full sha>"
  version: "latest"
  profile: "release"
```

## Notes

- A snapshot is addressed by commit: the registry version *is* the commit,
  and `<profile>/<label>` (default `release/latest`) is the path inside it —
  the same layout the tagged pipeline writes with the tag in place of
  `latest`. Re-running on the same commit is a no-op for files already
  there (`release-upload-artifact` compares hashes).
- The environment on the job authorises the ref the workflow was
  *dispatched* on, not the commit `ref` selects; `allowed_branches` closes
  that gap by refusing any commit not reachable from those branches.
- `resolve` prefers `origin/<ref>` when `ref` names a branch, then anything
  git can resolve, then a fetch of `ref` from origin.
- No tag, no GitHub Release, no changelog. Traceability comes from the
  environment's deployment record on the commit, the run summary, and —
  with `record_status` — a `snapshot/<package>` commit status linking to
  the run. A commit that must become a versioned release goes through the
  tagged pipeline.
