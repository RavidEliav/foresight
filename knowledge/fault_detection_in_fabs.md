# Fault detection on equipment sensor data

## Fault detection and classification
Fabs commonly run fault detection and classification (FDC) systems. They collect equipment
sensor signals for every run, reduce each signal to summary values such as means, maxima or
step durations, and compare them with limits learned from good runs. The goal is to catch a
problem at the tool before many wafers are affected.

## Univariate and multivariate monitoring
Univariate monitoring checks each summary value against its own limits. Multivariate methods,
such as principal component analysis with Hotelling's T-squared and residual statistics, look
at many correlated signals together and can detect a combination that is unusual even when
every single value is within its limits.

## Feature selection on many signals
Equipment data typically contains hundreds of signals, many of them redundant, constant or
irrelevant to a given failure. Removing constant and duplicate signals, and ranking the rest by
their relation to the outcome, is a common first step before building a monitor or a model. The
SECOM dataset was published to benchmark exactly this kind of signal selection.

## Labels arrive later
The pass or fail result usually comes from a later test, long after the run. A signal at the
tool is valuable because it can warn earlier, but its link to the later failure is statistical
and must be confirmed.
