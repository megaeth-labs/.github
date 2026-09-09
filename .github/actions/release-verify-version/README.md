# Release · Verify Version

`uses: megaeth-labs/.github/.github/actions/release-verify-version@main`

<!-- generated: description -->
Run a command that prints a built artifact's version (`my-binary --version`) and require the output to match the release version, so a binary built from the wrong tree — or a tag that does not match the manifest — never reaches a publish step. By default the expected output is `<name> <version>` (the clap shape: the command's basename, then the version without its leading `v`); `expected` overrides it. A command that cannot run at all — missing library, crash, no such flag — fails the step even on a dry run: an artifact that does not execute is never publishable, and its exit code is never swallowed. A mismatch is a warning on a dry run, so a rehearsal reports what a real run would refuse and carries on, and a hard stop otherwise. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `command` | yes |  | Shell command that prints the version, e.g. `target/release/my-binary --version`. Runs under `bash -o pipefail`, so a pipe to `head -n1` is fine for tools that print more. |
| `version` | yes |  | The release version, `vX.Y.Z` or `X.Y.Z` (the tag is fine). |
| `expected` | no | `{name} {version}` | Expected output, trailing whitespace ignored. `{version}` expands to the version without a leading `v`, `{name}` to the basename of the command's first word. |
| `dry_run` | no | `false` | `true`: do everything except the irreversible step (upload, attach, publish), and report what would have happened. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `actual` | What the command printed. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Verify the version
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

Between the build and the first publish step, once per binary:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-verify-version@main
  with:
    command: target/release/my-binary --version
    version: ${{ env.TAG }}          # vX.Y.Z is fine; the v is stripped
    dry_run: ${{ env.DRY_RUN }}
```

Tools that print more than `name version` get `expected`, e.g.
`expected: "v{version}"` or a `command` piped through `head -n1`.

## Notes

- A command that exits non-zero fails the step even on a dry run: an
  artifact that does not run is never publishable, and its exit code is never
  swallowed (stderr goes to the log).
- A mismatch is a warning on a dry run and a failure otherwise.
- Only flags the binary actually answers work: a workspace that builds clap
  without its `help` feature has `--version` (where `version` is declared)
  but no `--help`.
