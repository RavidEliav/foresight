# Statistical process control and control charts

## Purpose of a control chart
A control chart plots a process measurement over time against a center line and upper and lower
control limits. The limits describe the variation the process shows when only common causes are
acting. A point outside the limits, or an unusual pattern inside them, is a signal of a special
cause worth investigating. A signal says that something changed; it does not say what changed.

## Control limits are not specification limits
Control limits come from the process's own past behaviour, usually the mean plus and minus three
standard deviations estimated from an in-control period. Specification limits come from the
product requirements. A process can be in control and still produce out-of-specification
product, and a single point beyond the control limits does not mean the product is bad.

## Run rules
Besides single points beyond three standard deviations, rule sets such as the Western Electric
rules flag patterns that are unlikely by chance: two of three consecutive points beyond two
standard deviations on the same side, four of five beyond one standard deviation on the same
side, or a long run of points on one side of the center line. Using more rules finds small
shifts sooner but also raises more false alarms.

## Many charts at once
When hundreds of variables are charted, some points fall outside three-sigma limits by chance
alone. With many sensors, an individual out-of-limit reading is weak evidence; a sensor that is
out of limits more often in failing runs than in passing runs is stronger evidence.

## Phase I and Phase II
Limits are first estimated from historical data believed to be in control (Phase I) and then
used to monitor new data (Phase II). Limits estimated from data that already contains shifts are
too wide and hide problems.
