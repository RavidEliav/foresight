# Missing values in sensor data

## Why values go missing
Sensor values can be missing because a sensor was offline, a recipe step was skipped or does not
exist on some tools, data collection failed, or a summary value could not be computed.

## Missing-data mechanisms
Values can be missing completely at random, missing in a way explained by other recorded data,
or missing for reasons related to the unobserved value itself. Only the first case is harmless
for most analyses.

## Missingness can be informative
If failing runs have more missing values than passing runs, the pattern of missingness itself
may carry information about the process, for example a different tool or recipe path. Counting
missing values per run is a simple way to keep that information.

## Imputation without leakage
Filling missing values with a statistic such as the median must use only the data available at
training time. Computing it from the whole dataset leaks information from the test period.
