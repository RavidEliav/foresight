# Anomaly detection on run data

## Isolation Forest
Isolation Forest scores how easy a point is to separate from the rest with random splits.
Unusual runs are isolated with few splits and get high scores. It needs no labels, so it can
flag new kinds of problems that never appeared in training.

## Limits in high dimensions
With hundreds of variables, a problem that affects only a few sensors changes a run's overall
score very little, so whole-profile methods can miss localized problems. Per-sensor checks such
as robust z-scores complement them by pointing at the specific signals that are unusual.

## Unusual is not the same as bad
An anomaly is a run that differs from the reference period. It may be a failure, a harmless
change such as a new recipe, or a data problem. Anomaly flags are most useful when failing runs
are flagged clearly more often than passing runs, and when they are combined with other
evidence.
