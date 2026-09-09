# Release · Assets

`uses: megaeth-labs/.github/.github/actions/release-assets@main`

<!-- generated: description -->
Attach files, plus a generated `SHA256SUMS`, to the GitHub Release for a tag. Re-runs replace assets of the same name (`--clobber`), so the step is idempotent. `dry_run` writes and prints `SHA256SUMS` but attaches nothing. Needs a token with `contents: write` on the repository (the job token is enough). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `tag` | yes |  | Tag of the Release to attach to. |
| `files` | yes |  | Newline-separated paths to attach. |
| `token` | no | `${{ github.token }}` | Token for the GitHub API calls this action makes. |
| `dry_run` | no | `false` | `true`: do everything except the irreversible step (upload, attach, publish), and report what would have happened. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `sha256sums` | Path of the generated SHA256SUMS file. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Checksums
1. Attach to the Release
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `no files listed`
- `file not found: $f`
<!-- /generated -->

## Example

```yaml
- uses: megaeth-labs/.github/.github/actions/release-assets@main
  with:
    tag: ${{ env.TAG }}
    files: |
      target/release/my-binary
      target/release/my-other-binary
    dry_run: ${{ env.DRY_RUN }}
```

The job needs `permissions: contents: write`; the default `token` (the job
token) is enough.

## Notes

- Generates `SHA256SUMS` with file names only, so it verifies from a
  download directory, and attaches it with the files.
- Re-runs replace assets of the same name (`--clobber`), so the step is
  idempotent; keep it in a concurrency group so two runs never overlap.
- `dry_run` prints the sums and attaches nothing.
