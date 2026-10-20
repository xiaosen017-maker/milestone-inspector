# Architecture and trust boundaries

```text
CLI (argparse)
  └── GitRepository
      ├── safe subprocess invocation (shell=False)
      ├── resolve ref → immutable full commit SHA
      ├── diff / history / snapshot tree reads
      └── report records → JSON / Markdown
```

## Design choices

1. **Offline by default.** The project does not contact GitHub, scrape websites, or require API keys. Inspect a local clone and record its immutable SHA.
2. **No `shell=True`.** All Git invocations use an explicit argv array. `rev-parse --end-of-options` stops user-supplied revision strings from being interpreted as flags.
3. **Filename safe.** Git's `-z` output is parsed using NUL delimiters. Rename/copy status entries contain both old and new path.
4. **Immutable source of truth.** Blob bytes are retrieved from commit trees rather than a possibly dirty working tree. SHA-256 is calculated over raw blob bytes.
5. **Bounded resources.** Snapshot blob/total limits and a maximum number of files prevent accidental unbounded processing. This is not a sandbox against malicious Git binaries or local filesystems.
6. **Honest signals.** The presence of README, LICENSE, CI etc. is labeled a *signal*, not an unearned 5-star rating.

## Security considerations

Running Git in arbitrary third-party working trees can encounter untrusted content or Git configuration. For untrusted inputs, clone in an isolated sandbox, disable hooks and custom filters, and apply OS-level memory, CPU and filesystem permissions. This code is a local inspection assistant, not a secure multi-tenant Git execution service.
