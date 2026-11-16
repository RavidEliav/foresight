# Model card

## Model purpose
The rf_regularized model is designed to identify potential failures in a system by scoring runs based on their likelihood of failure. It aims to assist engineers in focusing on the riskiest runs for further investigation.

## Training data
The model was trained on historical data, but specific details about the dataset, such as size and features, are not provided in the available sources.

## Metrics
The performance metrics for the rf_regularized model are summarized in the table below:

| Metric       | Value   | 95% Confidence Interval |
|--------------|---------|-------------------------|
| PR-AUC       | 0.085   | 0.054 - 0.151           |
| Recall       | 0.125   | 0.000 - 0.313           |
| Precision     | 0.075   | N/A                     |
| False Alarms | 37      | N/A                     |

The model's PR-AUC indicates that it performs better than random guessing, which has a PR-AUC of 0.061 [source: model_metrics.json].

## Limitations
- The model has a low test PR-AUC of 0.085 (95% CI 0.054-0.151), indicating poor performance in distinguishing between failing and non-failing runs compared to random guessing (0.061) [source: model_metrics.json].
- The recall at the alarm budget is only 0.125 (95% CI 0.000-0.313), meaning that 21 out of 24 failing runs were missed during testing [source: model_metrics.json].
- The fixed F2 threshold of 0.247 resulted in a recall of 0.000 in the test period, suggesting significant drift in the model's performance [source: model_metrics.json].
- The model generated 37 false alarms, which could lead to unnecessary scrap or rework [source: model_metrics.json].
- The model relies on a limited number of important sensors (f_103, f_205, f_460, f_130, f_153, f_033, f_468, f_028), which may not capture the full complexity of the system [source: model_metrics.json].
- The wide confidence intervals for performance metrics indicate uncertainty in the model's reliability [source: model_metrics.json].

## Ethical considerations
- The potential for missed failures reaching customers raises concerns about product safety and reliability [source: model_metrics.json].
- The high rate of false alarms could lead to automation bias, where operators may become desensitized to alarms, potentially ignoring critical warnings [source: model_metrics.json].
- The model's performance may be affected by drift, which could lead to outdated predictions and decisions based on inaccurate data [source: model_metrics.json].
- The anonymization of sensor data limits the ability to understand the physical implications of the model's predictions, making it difficult to assess the ethical impact of its deployment [source: model_metrics.json].
- The reliance on a small subset of sensors may introduce bias in the model's predictions, potentially overlooking important factors that contribute to failures [source: model_metrics.json].

## Intended use
The rf_regularized model is intended for use by engineers to identify and investigate the riskiest runs in a system. It is important to note that the model's limitations and ethical considerations should be taken into account when interpreting its predictions and making decisions based on its outputs.
