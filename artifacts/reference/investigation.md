# Investigation

## Facts
- A total of 81 runs were flagged as anomalous, with a flag rate of 8.6% for failing runs compared to 4.9% for passing runs, resulting in a lift of 1.758 [source: anomaly_summary.json].
- Failing runs had an average of 14.058 sensors out of control limits, while passing runs had 12.202 sensors out of limits [source: anomaly_summary.json].
- Specific sensors showed significant discrepancies in out-of-control limits between failing and passing runs: f_040 was out of limits in 33.7% of failing runs versus 20.8% of passing runs, and f_059 was out of limits in 25.0% of failing runs compared to 9.9% of passing runs [source: anomaly_summary.json].
- The recommended risk ranking method, which combines model predictions with anomaly scores, identified the riskiest 10% of test runs (40 alarms) and found 5 of 24 failing runs, yielding a precision of 12.5% [source: risk_summary.json].
- Among the 5 most similar past runs to the test runs, the failure rate was 5.8% for failing test runs and 4.7% for passing test runs, indicating a training failure rate of 6.8%. This suggests that the similarity evidence is relatively weak [source: similar_runs.json].
- Run 1458, which is a passing run, had a risk score of 0.996 with the strongest signals being f_204:+115475.1, f_067:+7324.4, and f_338:+220.5 [source: risk_summary.json].
- The sensor f_059 shows a significant difference between failing and passing runs, with a median of 0.7223 for passing runs and 5.522 for failing runs, an effect size of 0.38, and a q-value of 2.5e-08, indicating strong statistical significance [source: eda_summary.json].
- The sensor f_103 also differs notably, with a median of -0.0102 for passing runs compared to -0.0082 for failing runs, an effect size of 0.34, and a q-value of 2.1e-06, suggesting it is associated with failing runs [source: eda_summary.json].
- Sensor f_247 has a median of 0.0262 for passing runs and 0.0421 for failing runs, with an effect size of 0.35 and a q-value of 0.00013, further supporting its association with failing runs [source: eda_summary.json].
- The sensor f_205 has a median of 7.66 for passing runs and 9.16 for failing runs, with an effect size of 0.24 and a q-value of 0.0027, indicating it is associated with failing runs [source: eda_summary.json].
- Among the most important sensors identified by permutation importance in the model, f_103 and f_205 are included, reinforcing their relevance in predicting failing runs [source: model_metrics.json].
- The overall monthly fail rates show a significant decline from 22.2% in July 2008 to 2.9% in September 2008, suggesting that while some sensors are consistently associated with failures, the overall trend indicates improvements in performance over time [source: eda_summary.json].
- Similar-run search (median imputation + standard scaling + PCA (30 components, 47% of variance), fitted on training runs; 5 nearest training runs (Euclidean), all earlier in time than the test runs): among the 5 most similar past runs, 5.8% failed for failing test runs vs 4.7% for passing test runs (training fail rate 6.8%) [source: similar_runs.json].

## Assumptions
- The analysis assumes that the sensors' performance is consistent across different runs and that the observed differences in sensor readings are indicative of underlying issues affecting run outcomes.
- It is assumed that the flagged anomalous runs are representative of the overall production process and that the failure rates observed in the test runs reflect true operational performance.

## Hypotheses
1. The sensor f_059 is associated with failing runs, as evidenced by its significant difference in median values (0.7223 for passing runs vs 5.522 for failing runs) and a strong q-value of 2.5e-08. Confidence: high (q < 0.001 and supported by the out-of-limit rate of 25.0% for failing runs vs 9.9% for passing runs).
2. The sensor f_103 is associated with failing runs, indicated by its median values (-0.0102 for passing runs vs -0.0082 for failing runs) and a q-value of 2.1e-06. Confidence: high (q < 0.001 and supported by its importance in the model).
3. The sensor f_040's higher out-of-limit rate in failing runs (33.7%) compared to passing runs (20.8%) suggests it may be a contributing factor to failures. Confidence: medium (strong statistical signal).
4. The overall decline in monthly fail rates from 22.2% to 2.9% indicates that improvements in the production process may be reducing the impact of certain sensors over time. Confidence: low (indirect evidence from historical trends). Background: Preventive maintenance resets many slow drifts, so runs just after maintenance can behave differently from runs just before it, suggesting that failures may cluster in parts of the maintenance cycle [background: process_drift_and_maintenance.md § Maintenance cycles].
5. The low precision of the risk ranking method (12.5%) indicates that while some sensors are associated with failures, the model's ability to predict failures is modest and may require further refinement. Confidence: low (weak evidence from model performance).

## Suggested verification
- To verify hypothesis 1, engineers could analyze the operational logs for sensor f_059 during both failing and passing runs to identify any patterns or anomalies.
- For hypothesis 2, a controlled experiment could be conducted to isolate the effects of sensor f_103 on run outcomes by manipulating its readings and observing the results.
- To test hypothesis 3, a detailed review of the maintenance records and the timing of failures related to sensor f_040 could provide insights into its role in the production process.
- For hypothesis 4, a longitudinal study comparing sensor performance and failure rates over time could help confirm the impact of improvements in the production process.
- To address hypothesis 5, engineers could refine the risk ranking method by incorporating additional features or adjusting the model parameters to enhance its predictive capability.
