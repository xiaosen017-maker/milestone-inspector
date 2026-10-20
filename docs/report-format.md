# Report format — schema v1

## `inspect` JSON

- `base_sha`, `head_sha`: full, resolved Git commit object identifiers.
- `base_is_ancestor`: result of `git merge-base --is-ancestor`.
- `commit_count`: `git rev-list --count base..head`. Not a measure of developer effort.
- `changes_by_type`: counts by Git status prefix (`A`, `M`, `D`, `R` etc.).
- `changed_files`: `{status, path, old_path}` items. `old_path` is null unless Git detected a rename or copy.
- `recent_commits`: last 25 short subjects by default. Subjects are untrusted text supplied by repo history.
- `head_repository_signals`: whether common files were detected at the target commit.
- `limitations`: explanation of what the tool does *not* establish.

## `snapshot` JSON

- `commit_sha`: full immutable commit identifier.
- `files`: path, mode, Git object ID, byte size and SHA-256 over Git blob data.
- `file_count`, `total_blob_bytes`: accounting fields.
- `warnings`: submodule and LFS-pointer caveats; symbolic links are hashed as link-target bytes.
- `algorithm`: describes the digest target.

`null` hashes for gitlink/submodule entries are intentional: no external repository content is assumed or fetched.

### Reproducibility

Different machines that have the same Git object database, SHA resolution and this tool's version should produce identical JSON for the same immutable refs. Git configuration may affect rename detection; preserve the repository's Git version and the report when using the output as external evidence.
