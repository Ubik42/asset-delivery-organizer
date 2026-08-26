# Machine-readable capabilities

`asset-delivery-organizer.v1.json` declares the installed tool's contracts, desktop/CLI/API interfaces, supported rule versions, scan semantics, audit invariants, guarded organization capabilities and explicitly unsupported DCC mutations. Its companion JSON Schema describes the manifest protocol.

The files are generated from runtime constants and strict models. Run `python scripts/export_capabilities.py` only for an intentional update; normal validation uses `--check` and fails on drift. Installed environments can read the same current declaration with `ado-capabilities` without locating this repository.
