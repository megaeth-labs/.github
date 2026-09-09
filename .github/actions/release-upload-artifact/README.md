# Release · Upload Artifact

`uses: megaeth-labs/.github/.github/actions/release-upload-artifact@main`

<!-- generated: description -->
Upload one file to Google Artifact Registry (generic repository) or a Cloud Storage bucket, idempotently: if the destination already holds a file, its hash is compared — identical means "already there" (success, nothing uploaded), different means failure, never a silent overwrite. Every destination is an input; nothing is defaulted. Authentication is the caller's job: run `google-github-actions/auth` (service-account key or Workload Identity Federation) before this step so `gcloud` is authenticated. `dry_run` computes the checksum and checks the destination but uploads nothing. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `file` | yes |  | Path of the file to upload. |
| `kind` | yes |  | `artifact-registry` (generic repository) or `gcs` (bucket object). |
| `dry_run` | no | `false` | `true`: do everything except the irreversible step (upload, attach, publish), and report what would have happened. |
| `project` | no |  | GCP project id (artifact-registry). |
| `location` | no |  | Registry location, e.g. asia-northeast1 (artifact-registry). |
| `repository` | no |  | Generic repository name (artifact-registry). |
| `package` | no |  | Package name (artifact-registry). |
| `version` | no |  | Package version (artifact-registry); a leading `v` is stripped, so the tag can be passed. |
| `path` | no |  | Optional folder inside the package version (artifact-registry). |
| `bucket` | no |  | Bucket name, without gs:// (gcs). |
| `object` | no |  | Object path inside the bucket (gcs). |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `sha256` |  |
| `uri` | Where the file lives (or would live) after this step. |
| `status` | `uploaded`, `exists` (identical file already there) or `dry-run`. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Validate inputs and hash the file
1. Upload
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `file not found: $FILE`
- `$v is required for kind artifact-registry`
- `$v is required for kind gcs`
- `kind must be artifact-registry or gcs, got`
- `gcloud is not on this runner`
- `gcloud is not authenticated — run google-github-actions/auth before this step`
- `$uri already exists with a DIFFERENT file (sha256 $have vs $SHA); versions are immutable — refusing`
- `$uri already exists with a DIFFERENT file (sha256 $have vs $SHA) — refusing to overwrite a published artifact`
<!-- /generated -->

## Example

Authenticate first, then one step per file:

```yaml
- uses: google-github-actions/auth@v3
  with:
    credentials_json: ${{ secrets.GCP_AUTH_KEY }}

- uses: megaeth-labs/.github/.github/actions/release-upload-artifact@main
  with:
    file: target/release/my-binary
    kind: artifact-registry
    project: my-gcp-project
    location: my-region
    repository: my-generic-repository
    package: my-binary
    version: ${{ env.TAG }}
    dry_run: ${{ env.DRY_RUN }}
```

For a bucket: `kind: gcs`, `bucket`, `object` instead of the registry inputs.

## Notes

- Idempotent by hash: an identical file at the destination is `exists`
  (success, nothing uploaded); a different one is a failure, never an
  overwrite. `status` and `uri` tell the caller what happened.
- Artifact Registry paths are `<package>/<version>/<file>`, with an optional
  `path` folder inside the version; a leading `v` on `version` is stripped so
  the tag can be passed.
- Authentication is the caller's: `google-github-actions/auth` (service
  account key or Workload Identity) before this step. The action checks that
  `gcloud` holds a usable credential rather than trusting the account list.
