# Process drift, maintenance and excursions

## Drift
Drift is a slow change in a process or measurement over time, for example from deposits building
up in a chamber, wear of parts or ageing of consumables. In time-ordered data drift shows up as
a gradual trend in a sensor, or as a change in the fail rate from one period to the next.

## Maintenance cycles
Preventive maintenance resets many slow drifts. Runs just after maintenance can behave
differently from runs just before it, so failures may cluster in parts of the maintenance cycle.
Comparing failures with maintenance dates is a standard way to test a drift hypothesis.

## Excursions
An excursion is a sudden, short departure from normal behaviour, for example after a part
failure, a wrong setting or a contaminated material lot. Excursions often affect a group of runs
close together in time and several related sensors at once.

## Consequences for analysis
When the process changes over time, a model or a threshold tuned on older data can stop working
on newer data. Evaluating on later runs than the training runs, and checking results period by
period, shows whether a finding holds over time or only in one window.
