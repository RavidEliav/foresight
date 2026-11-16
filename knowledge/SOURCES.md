# Knowledge base sources

Small, curated background documents for the Investigation crew (requirements §18.2). Every
document was **written for this project** in our own words (MIT license, like the code). The
facts come from the public sources listed below; no text is copied from them.

Background knowledge is general. It may support reasoning such as "drift patterns like this are
often linked to equipment wear", but it never links an anonymized SECOM sensor to a physical
cause, and it is always labelled **Background**, never **Evidence**.

| File | Topic | Based on (public sources) |
|---|---|---|
| `spc_control_charts.md` | Control charts, control limits, run rules | NIST/SEMATECH e-Handbook of Statistical Methods, ch. 6.3 (public domain, U.S. Government work): https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3.htm |
| `robust_statistics.md` | Median, MAD, robust z-scores | NIST/SEMATECH e-Handbook, ch. 1.3.5.6 (measures of scale): https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm |
| `semiconductor_yield_loss.md` | Kinds of yield loss and their usual causes | NIST/SEMATECH e-Handbook case studies (semiconductor processing); general industry knowledge summarised in our own words |
| `process_drift_and_maintenance.md` | Drift, tool wear, maintenance cycles, excursions | NIST/SEMATECH e-Handbook ch. 6 (process monitoring); general industry knowledge |
| `fault_detection_in_fabs.md` | Fault detection and classification (FDC) on equipment sensor data | McCann et al., "Causality Challenge: Benchmarking relevant signal components for effective monitoring and process control" (the SECOM paper), JMLR W&CP 6, 2010: https://proceedings.mlr.press/v6/mccann10a.html |
| `secom_dataset.md` | What SECOM is and is not | UCI Machine Learning Repository, SECOM (dataset 179, CC BY 4.0): https://archive.ics.uci.edu/dataset/179/secom |
| `imbalanced_metrics.md` | PR-AUC, ROC-AUC, recall and precision for rare failures | Saito & Rehmsmeier, PLOS ONE 10(3): e0118432, 2015 (CC BY 4.0): https://doi.org/10.1371/journal.pone.0118432 |
| `multiple_testing.md` | Many sensors tested at once, false discovery rate | Benjamini & Hochberg, J. R. Stat. Soc. B 57(1), 1995; NIST/SEMATECH e-Handbook ch. 7 |
| `nonparametric_tests.md` | Mann-Whitney U test and rank-based effect size | NIST/SEMATECH e-Handbook ch. 7.3 (nonparametric tests) |
| `anomaly_detection.md` | Isolation Forest and its limits | Liu, Ting & Zhou, "Isolation Forest", IEEE ICDM 2008: https://doi.org/10.1109/ICDM.2008.17 |
| `missing_sensor_data.md` | What missing sensor values can mean | Little & Rubin, *Statistical Analysis with Missing Data* (missing-data mechanisms), summarised |
| `root_cause_practice.md` | How engineers verify a hypothesis | NIST/SEMATECH e-Handbook ch. 5 (designed experiments); general quality-engineering practice |

Changing a document changes the knowledge index automatically (it is keyed by the content).
