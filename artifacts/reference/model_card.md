# Model card

## Model purpose
The rf_regularized model is designed to identify failing runs in a system by predicting potential failures based on sensor data. Its primary goal is to flag the riskiest 10% of runs for further investigation, thereby assisting engineers in maintaining system reliability [source: model_metrics.json].

## Training data
The model was trained on historical data, utilizing time-ordered cross-validation to ensure that the training and testing phases reflect real-world scenarios. The training data included various sensor readings, although specific details about the dataset are not disclosed [source: model_metrics.json].

## Metrics
The performance of the rf_regularized model is summarized in the following table:

| Metric       | Value   | 95% Confidence Interval |
|--------------|---------|-------------------------|
| PR-AUC       | 0.085   | 0.054 - 0.151           |
| Recall       | 0.125   | 0.000 - 0.313           |
| Precision    | 0.075   | N/A                     |
| False Alarms | 37      | N/A                     |
| Fails Caught | 3       | N/A                     |
| Missed Fails | 21      | N/A                     |

The model achieved a mean PR-AUC of 0.1589 during training, which is significantly better than the random guessing baseline PR-AUC of 0.061 [source: model_metrics.json].

## Limitations
- The model has a low test PR-AUC of 0.085 (95% CI 0.054-0.151), indicating poor performance in distinguishing between failing and non-failing runs compared to random guessing (0.061) [source: model_metrics.json].
- The recall at the alarm budget is only 0.125 (95% CI 0.000-0.313), meaning that 21 out of 24 failing runs were missed during testing [source: model_metrics.json].
- The fixed F2 threshold of 0.247 resulted in a recall of 0.000 in the test period, suggesting significant drift in the model's performance [source: model_metrics.json].
- The model generated 37 false alarms, which could lead to unnecessary scrap or rework [source: model_metrics.json].
- The model relies on a limited number of important sensors (f_103, f_205, f_460, f_130, f_153, f_033, f_468, f_028), which may not capture the full complexity of the system [source: model_metrics.json].

## Ethical considerations
- The high rate of missed failures (21 out of 24) poses a risk of failing runs reaching customers, potentially leading to safety issues or product failures [source: model_metrics.json].
- The presence of false alarms may lead to automation bias, where operators may overly rely on the model's predictions, potentially ignoring critical manual checks [source: model_metrics.json].
- The wide confidence intervals associated with the model's performance metrics indicate uncertainty, which could mislead stakeholders about the reliability of the model [source: model_metrics.json].
- The model's performance may be affected by drift, raising concerns about its long-term applicability and the need for continuous monitoring and retraining [source: model_metrics.json].
- The anonymization of sensor data limits the ability to understand the physical implications of the model's predictions, which could hinder accountability and transparency in decision-making [source: model_metrics.json].

## Intended use
The rf_regularized model is intended for use by engineers and analysts in identifying potentially failing runs within a system. It is designed to assist in prioritizing cases for further investigation, but users should be aware of its limitations, particularly regarding recall and precision. Continuous monitoring and potential retraining are recommended to maintain its effectiveness over time [source: model_metrics.json].
