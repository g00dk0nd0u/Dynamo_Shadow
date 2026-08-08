# debug_logging_v1

## Purpose

Development debug logging provides a small, sanitized JSON artifact for local diagnostics and review. Formal geometry and calculation prototypes now exist, but debug output remains diagnostic-only.

This is review support only and is not an input to the calculation pipeline. It does not implement site-boundary masks, 5 m / 10 m lines, legal judgement, or permit certification.

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
<runtime bundle>/debug_logs/latest_debug.json
```

The base directory is the folder containing `Shadow.dyn`, `script.py`, and
`shadow_debug.py`; it never depends on the process current working directory.
The file is overwritten on each enabled run. Timestamped run logs are not generated.

## Optional path settings

- `debug_log_dir`: relative to the runtime bundle directory only; default `debug_logs`.
- `debug_log_filename`: fixed JSON filename only; default `latest_debug.json`.

Absolute paths, `..`, path separators in filenames, and growth patterns such as `run_*.json`, `raw_*.json`, or `private_*.json` are rejected with warnings and fall back to safe defaults.

## OUT fields

Both success and failure outputs include:

- `debug_log`
- `debug_log_policy`

`debug_log` records whether logging was enabled, attempted, written, and any non-fatal write warnings or errors.

## Committed review artifacts

Runtime files under `debug_logs/` are ignored and must not be committed. Fixed sanitized samples required by tests or repository checks belong under `tests/fixtures/debug_logs/`, for example:

- `tests/fixtures/debug_logs/sample_no_inputs.json`
- `tests/fixtures/debug_logs/sample_basic_settings.json`

Do not commit raw Revit object dumps, client/project names, personal paths, huge geometry payloads, or timestamp-growth logs.

## Privacy and local path redaction

Committed debug logs must be sanitized more strictly than runtime-only diagnostics. Absolute/local paths must never be written to committed logs or to `OUT.debug_log.path`; `OUT.debug_log.path` and `OUT.debug_log.relative_path` are relative display paths only.

String-level redaction is mandatory, not only dictionary-key filtering. Warnings, error summaries, traceback-like strings, object summaries, and fallback messages must pass through privacy redaction before they can appear in a debug log.

Forbidden content includes local user paths, usernames, email addresses, client/project names, OneDrive paths, common user folders, UNC/network paths, raw Revit objects, and Dynamo/Revit object repr strings. Privacy scan failures in committed fixture JSON artifacts are merge blockers.

## Unit conversion summary in debug logs

Sanitized debug logs may include `unit_conversion_diagnostics` and policy summaries. Logs must not include personal paths, usernames, email addresses, client/project names, OneDrive paths, raw Revit object representations, or large geometry payloads. The privacy scan must pass whenever debug logs are committed.

## Unit conversion summary

Debug log payloads include a compact `unit_conversion_summary` with conversion backend, fallback factors, raw-field preservation status, converted-field status, and diagnostic-only usage flags. This summary must remain sanitized and must not include raw Revit objects, full geometry arrays, local paths, email addresses, OneDrive paths, or client/project names.
