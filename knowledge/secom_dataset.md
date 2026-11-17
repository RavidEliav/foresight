# The SECOM dataset

## What it contains
SECOM comes from a semiconductor manufacturing process and is published by the UCI Machine
Learning Repository. It has 1,567 production runs, each with 590 sensor or process measurement
values, a pass or fail label from in-house line testing and a timestamp. About 104 runs fail,
which makes the classes strongly imbalanced.

## What it does not contain
The features are anonymized: their names and physical meaning are not published, so no feature
can be linked to a specific tool, chamber or quantity. Some features are constant and many
contain missing values. Nothing in the data identifies equipment, lots or maintenance events.

## Intended use
The dataset was released to study feature selection: finding the signals that matter among
many irrelevant or noisy ones. Results on SECOM are about statistical association; any physical
interpretation needs information that is not part of the dataset.

## License
SECOM is available under the Creative Commons Attribution 4.0 license.
