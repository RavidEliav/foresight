# Investigation

## Facts
- A total of 81 runs were flagged as anomalous, with a flag rate of 8.6% for failing runs compared to 4.9% for passing runs, resulting in a lift of 1.758 [source: anomaly_summary.json].
- Failing runs had an average of 14.058 sensors out of control limits, while passing runs had 12.202 sensors out of limits [source: anomaly_summary.json].
- Specific sensors showed significant discrepancies between failing and passing runs: f_040 was out of limits in 33.7% of failing runs versus 20.8% of passing runs, and f_059 was out of limits in 25.0% of failing runs compared to 9.9% of passing runs [source: anomaly_summary.json].
- The recommended risk ranking is a combined approach, which, when flagging the riskiest 10% of test runs (40 alarms), identifies 5 out of 24 failing runs, yielding a precision of 12.5% [source: risk_summary.json].
- Among the 5 most similar past runs to the test runs, the failure rate was 5.8% for failing test runs and 4.7% for passing test runs, indicating a weak association with the training failure rate of 6.8% [source: similar_runs.json].
- The strongest signals for the riskiest run (1458, labeled as pass) included f_204 with a signal of +115475.1, which should be treated with caution due to the potential for large z-scores from small changes in sensors that barely varied during training [source: risk_summary.json].
- The sensor f_059 shows a significant difference between failing and passing runs, with a median of 0.7223 for passing runs and 5.522 for failing runs, an effect size of 0.38, and a q-value of 2.5e-08, indicating strong statistical significance [source: eda_summary.json].
- The sensor f_103 also differs notably, with a median of -0.0102 for passing runs compared to -0.0082 for failing runs, an effect size of 0.34, and a q-value of 2.1e-06, suggesting it is associated with failing runs [source: eda_summary.json].
- Sensor f_247 has a median of 0.0262 for passing runs and 0.0421 for failing runs, with an effect size of 0.35 and a q-value of 0.00013, further supporting its association with failing runs [source: eda_summary.json].
- The sensor f_205 has a median of 7.66 for passing runs and 9.16 for failing runs, with an effect size of 0.24 and a q-value of 0.0027, indicating it is associated with failing runs [source: eda_summary.json].
- Among the most important sensors identified by permutation importance in the model, f_103 and f_205 are included, reinforcing their relevance in predicting failing runs [source: model_metrics.json].
- The model's test PR-AUC of 0.085 indicates limited predictive power, but the inclusion of sensors like f_103 and f_205, which show significant differences in failing versus passing runs, suggests they may still hold importance in identifying risks [source: model_metrics.json].
- Similar-run search (median imputation + standard scaling + PCA (30 components, 47% of variance), fitted on training runs; 5 nearest training runs (Euclidean), all earlier in time than the test runs): among the 5 most similar past runs, 5.8% failed for failing test runs vs 4.7% for passing test runs (training fail rate 6.8%) [source: similar_runs.json].

## Assumptions
- The analysis assumes that the sensors' readings are reliable indicators of the process conditions and that the differences observed between failing and passing runs are meaningful.
- It is assumed that the flagged anomalous runs are indicative of underlying issues in the production process.
- The analysis assumes that the historical data used for comparison is representative of the current production conditions.

## Hypotheses
1. The sensor f_059 is associated with failing runs, as it shows a significant difference in out-of-limit rates (25.0% for failing runs vs 9.9% for passing runs) and has a strong statistical significance with a q-value of 2.5e-08. Confidence: high (q < 0.001 and supported by the out-of-limit rate).
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

2. The sensor f_103 is associated with failing runs, as it has a median of -0.0102 for passing runs compared to -0.0082 for failing runs, with a q-value of 2.1e-06 indicating strong statistical significance. Confidence: high (q < 0.001 and supported by the model importance).
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

3. The sensor f_247 is associated with failing runs, as it has a median of 0.0421 for failing runs compared to 0.0262 for passing runs, with a q-value of 0.00013 indicating strong statistical significance. Confidence: high (q < 0.001 and supported by the model importance).
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

4. The average number of sensors out of control limits is associated with failing runs, as failing runs had an average of 14.058 sensors out of limits compared to 12.202 for passing runs. Confidence: medium (strong statistical signal).
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

## Suggested verification
- Engineers could review equipment logs and maintenance records to identify any correlations between sensor readings and maintenance events, particularly focusing on the timing of failures relative to maintenance cycles.
- Controlled experiments could be conducted to isolate the effects of specific sensors, such as f_059 and f_103, on the production process to confirm their associations with failures.
- Further analysis of the flagged anomalous runs could be performed to determine if there are common patterns or conditions that lead to failures, including examining the environmental conditions during those runs.
- A deeper investigation into the historical performance of sensors, particularly f_059, f_103, and f_247, could provide insights into their reliability and any potential drift over time.
