# Investigation

## Facts
- A total of 81 runs were flagged as anomalous, with a flag rate of 8.6% for failing runs compared to 4.9% for passing runs, resulting in a lift of 1.758 [source: anomaly_summary.json].
- On average, failing runs had 14.058 sensors out of control limits, while passing runs had 12.202 sensors out of limits [source: anomaly_summary.json].
- Specific sensors showed significant discrepancies in out-of-limits rates: f_059 was out of limits in 25.0% of failing runs versus 9.9% of passing runs; f_040 was out of limits in 33.7% of failing runs versus 20.8% of passing runs; and f_247 was out of limits in 20.2% of failing runs versus 8.0% of passing runs [source: anomaly_summary.json].
- The recommended risk ranking is combined, chosen by time-ordered cross-validation, and flagging the riskiest 10% of test runs (40 alarms) identified 5 of 24 failing runs, yielding a precision of 12.5% [source: risk_summary.json].
- Run 1458, labeled as pass, had a risk score of 0.996 with the strongest signals being f_204:+115475.1, f_067:+7324.4, and f_338:+220.5 [source: risk_summary.json].
- Run 1397, also labeled as pass, had a risk score of 0.995 with strongest signals from f_198:+38.5, f_338:+38.3, and f_205:+35.0 [source: risk_summary.json].
- The sensor f_059 shows a significant difference between failing and passing runs, with a median of 0.7223 for passing runs and 5.522 for failing runs, an effect size of 0.38, and a q-value of 2.5e-08, indicating strong statistical significance [source: eda_summary.json].
- The sensor f_103 also differs notably, with a median of -0.0102 for passing runs compared to -0.0082 for failing runs, an effect size of 0.34, and a q-value of 2.1e-06, suggesting it is associated with failing runs [source: eda_summary.json].
- Sensor f_247 has a median of 0.0262 for passing runs and 0.0421 for failing runs, with an effect size of 0.35 and a q-value of 0.00013, further supporting its association with failing runs [source: eda_summary.json].
- The sensor f_205 has a median of 7.66 for passing runs and 9.16 for failing runs, with an effect size of 0.24 and a q-value of 0.0027, indicating it is also associated with failing runs [source: eda_summary.json].
- Among the most important sensors identified by permutation importance in the model, f_103 and f_205 are included, reinforcing their relevance in predicting failing runs [source: model_metrics.json].
- The model's test PR-AUC of 0.085 indicates limited predictive power, but the sensors identified (including f_103 and f_205) are still among the most associated with failing runs, as evidenced by their statistical significance and importance in the model [source: model_metrics.json].

## Assumptions
- The analysis assumes that the sensors' out-of-limit rates are indicative of the overall production process performance.
- It is assumed that the flagged anomalous runs are representative of the underlying issues affecting production quality.
- The model's performance is assumed to reflect the relationships between sensor readings and run outcomes.

## Hypotheses
1. **Hypothesis 1**: The sensor f_059 is associated with failing runs, as evidenced by its significant difference in out-of-limits rates (25.0% for failing vs. 9.9% for passing) and a strong q-value of 2.5e-08. Confidence: high (strong statistical significance and independent signal).
2. **Hypothesis 2**: The sensor f_103 is associated with failing runs, supported by its median difference (-0.0102 for passing vs. -0.0082 for failing) and a q-value of 2.1e-06. Confidence: high (strong statistical significance and independent signal).
3. **Hypothesis 3**: The sensor f_247 is associated with failing runs, as indicated by its median difference (0.0262 for passing vs. 0.0421 for failing) and a q-value of 0.00013. Confidence: high (strong statistical significance and independent signal).
4. **Hypothesis 4**: The sensor f_205 is associated with failing runs, supported by its median difference (7.66 for passing vs. 9.16 for failing) and a q-value of 0.0027. Confidence: medium (one strong statistical signal).
5. **Hypothesis 5**: The overall higher average number of out-of-limit sensors in failing runs (14.058) compared to passing runs (12.202) is associated with the likelihood of failure. Confidence: medium (one strong statistical signal).

## Suggested verification
- For Hypothesis 1, analyze the logs of sensor f_059 during both failing and passing runs to confirm its out-of-limit behavior correlates with run outcomes.
- For Hypothesis 2, review the operational conditions during runs with significant f_103 readings to assess their impact on production quality.
- For Hypothesis 3, conduct a controlled experiment to manipulate conditions affecting f_247 and observe the resulting run outcomes.
- For Hypothesis 4, compare the operational conditions of runs with high f_205 readings against those with lower readings to evaluate their influence on failure rates.
- For Hypothesis 5, perform a statistical analysis to determine if the average number of out-of-limit sensors can predict run outcomes in a controlled setting.
