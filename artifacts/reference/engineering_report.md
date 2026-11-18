# Engineering report

## What was detected
The analysis of production runs from July 19, 2008, to October 17, 2008, revealed a fail rate of 6.6%, corresponding to 104 failing runs out of 1567 recorded runs [source: data_profile.json]. Notably, there were significant variations in monthly failure rates, with a decline from 22.2% in July to 2.9% in September, followed by an increase to 6.1% in October [source: eda_summary.json]. Additionally, 20 sensors exhibited significant differences in readings between failing and passing runs, indicating potential areas for further investigation [source: eda_summary.json].

## Supporting statistical evidence
The data quality review confirmed a high level of confidence in the dataset, with successful validation checks and a low missing cells ratio of 1.56% after cleaning [source: validation_summary.json]. The Mann-Whitney U test indicated that several sensors, including f_059, f_103, and f_247, had strong statistical significance in differentiating between failing and passing runs, with q-values less than 0.001 [source: eda_summary.json]. Specifically, sensor f_059 had a median of 5.522 for failing runs compared to 0.7223 for passing runs, while f_103 and f_247 also showed notable differences in their median values [source: eda_summary.json].

## Important abnormal parameters
The investigation flagged 81 runs as anomalous, with a flag rate of 8.6% for failing runs compared to 4.9% for passing runs [source: anomaly_summary.json]. Failing runs had an average of 14.058 sensors out of control limits, while passing runs had 12.202 sensors out of limits [source: anomaly_summary.json]. Specific sensors, such as f_040 and f_059, showed significant discrepancies in out-of-limit rates between failing and passing runs, further highlighting the need for targeted monitoring [source: anomaly_summary.json].

## Hypotheses
1. The sensor f_059 is associated with failing runs, as it shows a significant difference in out-of-limit rates (25.0% for failing runs vs 9.9% for passing runs) and has a strong statistical significance with a q-value of 2.5e-08. Confidence: high (q < 0.001 and supported by the out-of-limit rate).  
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

2. The sensor f_103 is associated with failing runs, as it has a median of -0.0102 for passing runs compared to -0.0082 for failing runs, with a q-value of 2.1e-06 indicating strong statistical significance. Confidence: high (q < 0.001 and supported by the model importance).  
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

3. The sensor f_247 is associated with failing runs, as it has a median of 0.0421 for failing runs compared to 0.0262 for passing runs, with a q-value of 0.00013 indicating strong statistical significance. Confidence: high (q < 0.001 and supported by the model importance).  
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

4. The average number of sensors out of control limits is associated with failing runs, as failing runs had an average of 14.058 sensors out of limits compared to 12.202 for passing runs. Confidence: medium (strong statistical signal).  
   Background: A significant difference between failing and passing runs shows an association. The sensor could reflect the cause, be affected by the same underlying condition, or differ for an unrelated reason such as the time period in which most failures happened. [background: nonparametric_tests.md § Association, not cause]

## Recommended next steps
Engineers should review equipment logs and maintenance records to identify correlations between sensor readings and maintenance events, particularly focusing on the timing of failures relative to maintenance cycles. Controlled experiments could be conducted to isolate the effects of specific sensors, such as f_059 and f_103, on the production process. Further analysis of the flagged anomalous runs should be performed to determine common patterns or conditions leading to failures. Additionally, a deeper investigation into the historical performance of sensors f_059, f_103, and f_247 could provide insights into their reliability and any potential drift over time.

## Data quality and model limitations
The data quality review indicated a high level of integrity, but the model's test PR-AUC of 0.085 suggests limited predictive power in distinguishing between failing and non-failing runs [source: model_metrics.json]. The model generated 37 false alarms, which could lead to unnecessary scrap or rework [source: model_metrics.json]. Furthermore, the reliance on a limited number of important sensors may not capture the full complexity of the system, raising concerns about the model's long-term applicability and the need for continuous monitoring and retraining [source: model_metrics.json].
