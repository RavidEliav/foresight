# Metrics for rare failures

## Accuracy is misleading
When only a few percent of runs fail, a model that always predicts pass is almost always
correct and still useless. Metrics must focus on the failing class.

## Precision, recall and the PR curve
Recall is the share of failing runs that are caught; precision is the share of alarms that are
real failures. The precision-recall curve shows the trade-off over all thresholds, and its area
(PR-AUC) summarises it. For a random ranking the PR-AUC is about the fail rate, so a PR-AUC must
be compared with that baseline rather than with 1.

## ROC-AUC can look optimistic
ROC-AUC uses the false positive rate, which stays small when passing runs are plentiful even if
the alarms contain many false ones. On imbalanced data the PR curve is more informative about
how useful the alarms are.

## Alarm budgets
In operations the number of alarms an engineering team can follow up is limited. Evaluating
recall and precision when a fixed share of runs is flagged reflects that limit directly and
keeps working when the score distribution shifts over time.

## Uncertainty
With few failing runs in a test period, every metric has a wide confidence interval; bootstrap
intervals make this visible.
