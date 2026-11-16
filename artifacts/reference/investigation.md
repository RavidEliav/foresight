# Investigation

## Facts
- A total of 81 runs were flagged as anomalous, with a flag rate of 8.6% for failing runs compared to 4.9% for passing runs, resulting in a lift of 1.758 [source: anomaly_summary.json].
- Failing runs had an average of 14.058 sensors out of control limits, while passing runs had 12.202 sensors out of limits [source: anomaly_summary.json].
- Specific sensors showed significant differences in out-of-limit rates between failing and passing runs: f_040 was out of limits in 33.7% of failing runs versus 20.8% of passing runs, and f_059 was out of limits in 25.0% of failing runs versus 9.9% of passing runs [source: anomaly_summary.json].
- The recommended risk ranking method is combined, which was chosen based on time-ordered cross-validation; this method flagged the riskiest 10% of test runs (40 alarms) and identified 5 out of 24 failing runs, yielding a precision of 12.5% [source: risk_summary.json].
- Among the top riskiest runs, Run 1458 (timestamp: 2008-10-11, label: pass) had a risk score of 0.996, with strong signals from sensors f_204, f_067, and f_338 [source: risk_summary.json].
- Run 1397 (timestamp: 2008-10-07, label: pass) also had a high risk score of 0.995, with significant signals from sensors f_198, f_338, and f_205 [source: risk_summary.json].
- Sensor f_059 shows a significant difference between failing and passing runs, with a median of 0.7223 for passing runs and 5.522 for failing runs, an effect size of 0.38, and a q-value of 2.5e-08, indicating strong statistical significance [source: eda_summary.json].
- Sensor f_103 also differs notably, with a median of -0.0102 for passing runs compared to -0.0082 for failing runs, an effect size of 0.34, and a q-value of 2.1e-06, suggesting it is associated with failing runs [source: eda_summary.json].
- Sensor f_205 has a median of 7.66 for passing runs and 9.16 for failing runs, with an effect size of 0.24 and a q-value of 0.0027, indicating it is associated with failing runs [source: eda_summary.json].
- The most important sensors identified by permutation importance in the model include f_103 and f_205, which aligns with their statistical significance in differentiating between failing and passing runs [source: model_metrics.json].
- The model selected (rf_regularized) shows that f_103 and f_205 are among the most important sensors, reinforcing their association with failing runs [source: model_metrics.json].
- The overall monthly fail rates indicate a significant drop from 22.2% in July 2008 to 2.9% in September 2008, suggesting that while some sensors are consistently associated with failures, the overall trend in failures is decreasing [source: eda_summary.json].

## Assumptions
- The analysis assumes that the sensors' out-of-limit rates are indicative of the production process's performance.
- It is assumed that the risk ranking method used is appropriate for identifying failing runs.
- The analysis assumes that the historical data reflects current production conditions and sensor behavior.

## Hypotheses
1. **Hypothesis 1**: The significant difference in out-of-limit rates for sensor f_059 (25.0% for failing runs vs. 9.9% for passing runs) is associated with the likelihood of a run failing. Confidence: high (q-value of 2.5e-08 and supported by the model's importance ranking).
2. **Hypothesis 2**: The out-of-limit rate for sensor f_103 (with a median of -0.0102 for passing runs and -0.0082 for failing runs) is associated with an increased risk of failure. Confidence: high (q-value of 2.1e-06 and supported by its importance in the model).
3. **Hypothesis 3**: The average number of sensors out of control limits (14.058 for failing runs vs. 12.202 for passing runs) is associated with the likelihood of a run failing. Confidence: medium (strong statistical signal from the average counts).
4. **Hypothesis 4**: The overall trend of decreasing fail rates from 22.2% in July 2008 to 2.9% in September 2008 is associated with improvements in the production process or sensor calibration. Confidence: low (indirect evidence from monthly fail rates).

## Suggested verification
- For **Hypothesis 1**, an engineer could analyze the historical performance of sensor f_059 in relation to run outcomes and conduct controlled experiments to assess its impact on failures.
- For **Hypothesis 2**, reviewing maintenance records and calibration logs for sensor f_103 could provide insights into its performance and correlation with failures.
- For **Hypothesis 3**, a detailed analysis of runs with varying numbers of sensors out of limits could be conducted to establish a clearer relationship with failure rates.
- For **Hypothesis 4**, a review of process changes or maintenance activities during the period of decreasing fail rates could help verify the association with improvements in production.
