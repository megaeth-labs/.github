# Release · Publish Rust Crates

`uses: megaeth-labs/.github/.github/actions/release-publish-rust-crates@main`

<!-- generated: description -->
Publish an explicit list of workspace crates to crates.io at the release version. Verifies every listed crate's manifest version first, skips crates already published at that version (so a re-run after a partial failure finishes the rest), publishes the remainder in one `cargo publish -p … -p …` invocation — Cargo orders by dependency and waits for the index between crates (requires Cargo ≥ 1.90) — then polls crates.io until every crate reports the version. `dry_run` runs `cargo publish --dry-run`: full packaging and build verification, nothing uploaded. Run inside a job that has checked out the release tag and installed the toolchain the crates need. Never use `--workspace`: a crate without `publish = false` that was never meant to be published would go out with it. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `crates` | yes |  | Newline- or comma-separated crate names, in any order. Only these are published. |
| `version` | yes |  | Release version every listed crate must be at; X.Y.Z or vX.Y.Z (the tag). |
| `token` | no |  | crates.io API token (CARGO_REGISTRY_TOKEN). Unused in dry_run. |
| `dry_run` | no | `false` | `true`: `cargo publish --dry-run` for every listed crate (even ones already on crates.io), publish nothing. |
| `index_timeout_seconds` | no | `600` | How long to wait for crates.io to report every published version. |
| `extra_args` | no |  | Extra arguments appended to `cargo publish` (e.g. `--no-verify`). |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `published` | Crates published by this run (comma-separated; empty in dry_run). |
| `skipped` | Crates already at this version on crates.io, skipped. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Verify crate versions
1. Skip crates already published
1. Publish
1. Wait for crates.io to index *(only if `inputs.dry_run != 'true' && steps.publish.outputs.published != ''`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `no crates listed`
- `crates.io returned $code for $c@$VERSION`
- `token is required to publish (or set dry_run: true)`
- `crates.io has not indexed $c@$VERSION after ${TIMEOUT}s`
<!-- /generated -->

## Example

From `workflow-templates/on-release.yml`, in a job under
`environment: publish`:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-publish-rust-crates@main
  with:
    crates: |
      my-crate-core
      my-crate
    version: ${{ env.TAG }}
    token: ${{ env.DRY_RUN != 'true' && secrets.CARGO_REGISTRY_TOKEN || '' }}
    dry_run: ${{ env.DRY_RUN }}
```

## Notes

- An explicit allowlist, never `--workspace`: crates without
  `publish = false` that are not meant for crates.io would otherwise go out.
- Every listed crate's manifest must already be at `version` (the candidate
  PR did that); crates already on crates.io at that version are skipped, so
  a re-run is safe.
- One `cargo publish -p … -p …` for the rest — Cargo ≥ 1.90 orders and
  waits between dependent crates — then the index is polled until every
  version is visible (`index_timeout_seconds`).
- `dry_run` runs `cargo publish --dry-run` for every listed crate, including
  ones already published, and uploads nothing; the token is not needed.
