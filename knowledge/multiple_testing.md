# Testing many sensors at once

## The multiple testing problem
When hundreds of sensors are each tested for a difference between failing and passing runs,
some will look significant by chance alone. At a 5% level, roughly one test in twenty gives a
false positive when there is no real difference.

## False discovery rate
The Benjamini-Hochberg procedure controls the false discovery rate: the expected share of false
positives among the findings that are reported. It turns each p-value into an adjusted value
(often called a q-value). Reporting sensors with q below 0.05 means that, on average, at most
about 5% of the reported sensors are expected to be false findings.

## Strength of evidence
A very small q-value means the difference is unlikely to be chance, not that it is large or
important. The size of the difference and agreement with other, independent signals are needed
to judge how much a finding matters.
