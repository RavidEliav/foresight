# Nonparametric comparison of two groups

## Mann-Whitney U test
The Mann-Whitney U test (also called the Wilcoxon rank-sum test) asks whether values in one
group tend to be larger than in the other. It works on ranks, so it needs no normality
assumption and is not dominated by outliers, which suits skewed sensor data.

## Effect size
A rank-based effect size, such as the rank-biserial correlation, describes how strongly the two
groups are separated, from zero for no separation to one for complete separation. Small effects
can be highly significant when groups are large, so the effect size and the p-value answer
different questions.

## Association, not cause
A significant difference between failing and passing runs shows an association. The sensor
could reflect the cause, be affected by the same underlying condition, or differ for an
unrelated reason such as the time period in which most failures happened.
