# Data contracts

Keep shared payload definitions and synthetic or sanitized examples in this directory. Finalize the first sample before developing independent consumers.

Each sample needs a schema version, rider/session/source identity, restart-aware sequence identity, observation time with clock semantics, metric/unit, quality and input mode (`live`, `replay` or `synthetic`). Missing values must be distinguishable from zero.

Initial measurements are heart rate and, if verified, board speed/heel/trim. Add motion data after defining its axes, timing and calibration. Update producers and consumers together when semantics change.
