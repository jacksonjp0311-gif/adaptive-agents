# Release checklist

Run locked tests, formatting, clippy, demo, evaluation, cargo package --allow-dirty --no-verify and a local cargo install. Review public files for private data. Publish only after explicit authorization. This initial release was authorized as public; the license remains undecided and crates.io publishing is disabled.

Tag v0.1.1, attach the complete source ZIP and SHA256 checksum, and verify the release asset, remote tag, commit and both CI matrix jobs. Archive should exclude target, local-install, demo-store and .git. A Library ZIP is a convenience copy; use the confirmed release commit for source identity.
