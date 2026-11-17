# Robust statistics for sensor data

## Why robust statistics
The mean and the standard deviation are pulled strongly by a few extreme values. Sensor data
often contains spikes, stuck readings and outliers, so a few bad values can hide or exaggerate a
real change. The median and the median absolute deviation (MAD) are far less affected.

## Median absolute deviation
The MAD is the median of the absolute distances from the median. Multiplied by about 1.4826 it
estimates the standard deviation when the data are roughly normal, so it can replace the
standard deviation in a z-score.

## Robust z-scores
A robust z-score is (value minus median) divided by 1.4826 times the MAD, with the median and
MAD taken from a reference period. Values beyond about three in absolute size are commonly
treated as unusual.

## Caution with near-constant sensors
If a sensor barely varies in the reference period, its MAD is tiny and a small, harmless change
produces a very large z-score. Large z-scores from such sensors should be read with caution and
checked against the sensor's normal range before they are treated as a real excursion.
