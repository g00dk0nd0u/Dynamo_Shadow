# debug_logging_v1

## Purpose

Development debug logging provides a small, sanitized JSON artifact for Codex / ChatGPT / GitHub review before formal footprint polygon generation, unit conversion, and geometry processing are implemented.

This is review support only. It does not implement formal footprint polygons, CurveLoop creation, Revit unit conversion, site boundary loop extraction, true solar time, sun vectors, shadow projection, legal judgement, or Revit element creation.

## Enablement

Debug logging is disabled by default.

Enable it with:

```json
{
  "debug_log_enabled": true
}
```

When enabled, the default output is:

```text
debug_logs/latest_debug.json
```

The file is overwritten on each enabled run. Timestamped run logs are not generated.

## Optional path settings

- `debug_log_dir`: relative directory only; default `debug_logs`.
- `debug_log_filename`: fixed JSON filename only; default `latest_debug.json`.

Absolute paths, `..`, path separators in filenames, and growth patterns such as `run_*.json`, `raw_*.json`, or `private_*.json` are rejected with warnings and fall back to safe defaults.

## OUT fields

Both success and failure outputs include:

- `debug_log`
- `debug_log_policy`

`debug_log` records whether logging was enabled, attempted, written, and any non-fatal write warnings or errors.

## Committed review artifacts

Small sanitized review samples under `debug_logs/` may be committed, for example:

- `debug_logs/latest_debug.json`
- `debug_logs/sample_no_inputs.json`
- `debug_logs/sample_basic_settings.json`

Do not commit raw Revit object dumps, client/project names, personal paths, huge geometry payloads, or timestamp-growth logs.

## Privacy and local path redaction

Committed debug logs must be sanitized more strictly than runtime-only diagnostics. Absolute/local paths must never be written to committed logs or to `OUT.debug_log.path`; `OUT.debug_log.path` and `OUT.debug_log.relative_path` are relative display paths only.

String-level redaction is mandatory, not only dictionary-key filtering. Warnings, error summaries, traceback-like strings, object summaries, and fallback messages must pass through privacy redaction before they can appear in a debug log.

Forbidden content includes local user paths, usernames, email addresses, client/project names, OneDrive paths, common user folders, UNC/network paths, raw Revit objects, and Dynamo/Revit object repr strings. Privacy scan failures in committed `debug_logs/*.json` artifacts are merge blockers.
