# Dynamo Custom Selection serialization

Dynamo Player Custom Selection nodes must use Dynamo's native Custom Selection
serialization shape so Player can populate the Display / Value rows.

For `CoreNodeModels.Input.CustomSelection, CoreNodeModels` nodes:

- Store options in `SerializedItems`.
- Each entry must contain display text as `Name` and the Python-output value as `Item`.
- Do not use the legacy/non-native `Items` list or per-entry `Value` field.
- Set `SelectedIndex` and `SelectedString`, where `SelectedString` matches the
  selected entry's `Name`.
- Keep the output port metadata as `Name: "Value"` and
  `Description: "The selected Value"`.
- Top-level Dynamo Player `Inputs[].Value` stores the selected display string,
  while the Python node receives the selected `SerializedItems[].Item` value.
