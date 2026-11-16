# Model card

## Model purpose
The rf_regularized model is designed to identify critical failures in operational runs by flagging the riskiest 10% of the runs scored. It aims to enhance safety and reliability by catching potential failures before they reach customers [source: model_metrics.json].

## Training data
The model was trained on historical operational data, utilizing various sensor readings to predict failures. The specific details of the training dataset, including the volume and diversity of data, are not disclosed [source: model_metrics.json].

## Metrics
The performance of the rf_regularized model is evaluated using the following metrics:

| Metric       | Value   | 95% Confidence Interval |
|--------------|---------|-------------------------|
| PR-AUC       | 0.085   | 0.054 - 0.151           |
| Recall       | 0.125   | 0.000 - 0.313           |
| Precision     | 0.075   | N/A                     |
| Alarms       | 40      | N/A                     |

The model's PR-AUC of 0.085 indicates poor performance in distinguishing between failing and non-failing runs compared to the random guessing baseline PR-AUC of 0.061 [source: model_metrics.json].

## Limitations
- The model has a low test PR-AUC of 0.085 (95% CI 0.054-0.151), indicating poor performance in distinguishing between failing and non-failing runs compared to random guessing (0.061) [source: model_metrics.json].
- The recall at the alarm budget is only 0.125 (95% CI 0.000-0.313), meaning that 21 out of 24 failing runs were missed during testing [source: model_metrics.json].
- The fixed F2 threshold of 0.247 resulted in a recall of 0.000 in the test period, suggesting significant drift in the model's performance [source: model_metrics.json].
- The model produced 37 false alarms, which could lead to unnecessary scrap or rework [source: model_metrics.json].
- The wide confidence intervals for performance metrics indicate uncertainty in the model's reliability [source: model_metrics.json].
- The model relies on a limited number of important sensors (f_103, f_205, f_460, f_130, f_153, f_033, f_468, f_028), which may not capture all relevant information [source: model_metrics.json].

## Ethical considerations
- The potential for missed failures reaching customers raises concerns about product safety and reliability [source: model_metrics.json].
- The high rate of false alarms could lead to automation bias, where operators may become desensitized to alarms, potentially ignoring critical warnings [source: model_metrics.json].
- The model's reliance on anonymized sensors limits transparency and accountability in understanding its decision-making process [source: model_metrics.json].
- The presence of drift in the model's performance suggests that it may not adapt well to changing conditions, which could lead to ethical implications in operational contexts [source: model_metrics.json].

## Intended use
The rf_regularized model is intended for use in operational environments where identifying critical failures is essential for safety and reliability. It is designed to assist engineers in flagging the riskiest runs, but users should be aware of its limitations and the potential consequences of false alarms and missed failures [source: model_metrics.json].
