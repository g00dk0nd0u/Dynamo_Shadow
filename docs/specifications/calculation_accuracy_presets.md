# Calculation accuracy presets

Dynamo Player exposes `rough` (0.5 m / 30 minutes), `standard` (0.5 m / 15 minutes), and `high` (0.25 m / 15 minutes). The Player defaults to `standard`. A supplied Player preset overrides the corresponding settings JSON values; when the Player input is absent, the existing pure-Python diagnostic defaults remain unchanged. Accuracy is never reduced automatically when the grid-point limit is exceeded.

The duration grid analysis bounds are not clipped to the site boundary. The current calculation includes the bounds of every unified formal shadow polygon and then applies the analysis safety margin. When site-boundary geometry becomes available, the contract is the union of all unified shadow polygon bounds and the site-boundary bounds expanded by at least 10 m, followed by the analysis safety margin. The site boundary is a future legal-evaluation mask, not a duration-grid clipping boundary; this change does not implement site-boundary geometry processing.

Equal-time contours remain the original Marching Squares polylines from the duration grid. No Chaikin, spline/NURBS, moving-average, vertex-displacement, or display-only smoothing is applied.
