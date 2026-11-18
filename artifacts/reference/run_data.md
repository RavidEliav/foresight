# Run data
Numbers copied from this run's files (model_metrics.json, risk_summary.json, risk_scores.csv, anomaly_summary.json, similar_runs.json).

## Model test metrics
Selected model: rf_regularized. Random-guessing PR-AUC: 0.0612.
Test PR-AUC: 0.085 (95% CI 0.054 to 0.1508).
Test fail recall: 0.125 (95% CI 0.0 to 0.3126).
Test precision: 0.075 (95% CI 0.0 to 0.175).
Test balanced accuracy: 0.5122 (95% CI 0.4455 to 0.6102).
Test period: 3 failing runs caught, 21 missed, 37 false alarms, 331 passing runs correctly not flagged.

## Risk ranking
Recommended ranking: combined. Alarm budget: the riskiest 10% of test-period runs.
It finds 5 of 24 failing runs with 40 alarms (recall 0.2083, precision 0.125).

## Anomaly detection
Runs flagged as anomalous: 81 (flag limit 0.44159). Flag rate: failing runs 0.0865, passing runs 0.0492 (lift 1.758).
Sensors out of control limits per run: failing runs 14.058, passing runs 12.202.

## Similar past runs: method and overall result
Method: median imputation + standard scaling + PCA (30 components, 47% of variance), fitted on training runs; 5 nearest training runs (Euclidean), all earlier in time than the test runs.
For each high-risk or failing test run, the 5 most similar past runs were found. Distance is the Euclidean distance between sensor profiles after scaling and PCA: small means similar.
Share of similar past runs that failed: 0.0583 for failing test runs, 0.0473 for passing test runs (training fail rate 0.0681).
Typical (median) nearest distance: 8.117.

## Riskiest test-period runs
Ordered from the highest risk score down:
1. Run 1458 (passed): risk score 0.9962, model fail probability 0.23915, anomaly score 0.49519.
2. Run 1397 (passed): risk score 0.9949, model fail probability 0.27571, anomaly score 0.46126.
3. Run 1489 (passed): risk score 0.9923, model fail probability 0.2168, anomaly score 0.47849.
4. Run 1257 (passed): risk score 0.9847, model fail probability 0.20251, anomaly score 0.45679.
5. Run 1456 (passed): risk score 0.9707, model fail probability 0.20934, anomaly score 0.44577.
6. Run 1230 (passed): risk score 0.963, model fail probability 0.1724, anomaly score 0.46316.
7. Run 1307 (passed): risk score 0.9617, model fail probability 0.18344, anomaly score 0.4486.
8. Run 1427 (passed): risk score 0.9477, model fail probability 0.16444, anomaly score 0.45147.
9. Run 1254 (failed): risk score 0.9362, model fail probability 0.19631, anomaly score 0.4369.
10. Run 1289 (passed): risk score 0.9349, model fail probability 0.17839, anomaly score 0.43925.
11. Run 1333 (passed): risk score 0.9337, model fail probability 0.19746, anomaly score 0.4358.
12. Run 1374 (passed): risk score 0.9311, model fail probability 0.22916, anomaly score 0.4348.
13. Run 1539 (passed): risk score 0.9235, model fail probability 0.15732, anomaly score 0.44871.
14. Run 1503 (passed): risk score 0.9133, model fail probability 0.18572, anomaly score 0.43454.
15. Run 1190 (passed): risk score 0.9107, model fail probability 0.17519, anomaly score 0.43534.

## Most anomalous runs
Ordered from the highest anomaly score down:
1. Run 634 (failed): anomaly score 0.51788, 48 sensors out of control limits.
2. Run 457 (passed): anomaly score 0.50044, 40 sensors out of control limits.
3. Run 1458 (passed): anomaly score 0.49519, 34 sensors out of control limits.
4. Run 57 (failed): anomaly score 0.49083, 42 sensors out of control limits.
5. Run 1489 (passed): anomaly score 0.47849, 40 sensors out of control limits.
6. Run 275 (passed): anomaly score 0.47209, 40 sensors out of control limits.
7. Run 61 (passed): anomaly score 0.47059, 32 sensors out of control limits.
8. Run 99 (passed): anomaly score 0.46802, 32 sensors out of control limits.
9. Run 759 (passed): anomaly score 0.46781, 27 sensors out of control limits.
10. Run 856 (passed): anomaly score 0.46726, 30 sensors out of control limits.
11. Run 51 (passed): anomaly score 0.46601, 23 sensors out of control limits.
12. Run 385 (passed): anomaly score 0.46552, 28 sensors out of control limits.
13. Run 84 (passed): anomaly score 0.46459, 28 sensors out of control limits.
14. Run 10 (failed): anomaly score 0.46443, 23 sensors out of control limits.
15. Run 163 (passed): anomaly score 0.46319, 26 sensors out of control limits.

## Run 10
Run 10 (2008-07-19 21:57:00) failed. Anomaly score 0.46443. Sensors out of control limits: 23. Top signals (sensor: robust z-score): f_195:+101.2; f_164:+54.3; f_434:+50.9.
Run 10 is among the most anomalous runs.

## Run 51
Run 51 (2008-07-29 21:07:00) passed. Anomaly score 0.46601. Sensors out of control limits: 23. Top signals (sensor: robust z-score): f_164:+54.8; f_434:+51.3; f_165:+35.3.
Run 51 is among the most anomalous runs.

## Run 57
Run 57 (2008-07-30 12:29:00) failed. Anomaly score 0.49083. Sensors out of control limits: 42. Top signals (sensor: robust z-score): f_434:+103.3; f_430:+58.0; f_164:+54.0.
Run 57 is among the most anomalous runs.

## Run 61
Run 61 (2008-07-31 17:07:00) passed. Anomaly score 0.47059. Sensors out of control limits: 32. Top signals (sensor: robust z-score): f_164:+54.9; f_434:+51.6; f_165:+34.7.
Run 61 is among the most anomalous runs.

## Run 84
Run 84 (2008-08-04 03:49:00) passed. Anomaly score 0.46459. Sensors out of control limits: 28. Top signals (sensor: robust z-score): f_164:+54.6; f_116:-52.4; f_165:+34.8.
Run 84 is among the most anomalous runs.

## Run 99
Run 99 (2008-08-04 23:33:00) passed. Anomaly score 0.46802. Sensors out of control limits: 32. Top signals (sensor: robust z-score): f_434:+103.3; f_430:+58.0; f_164:+53.3.
Run 99 is among the most anomalous runs.

## Run 163
Run 163 (2008-08-08 22:25:00) passed. Anomaly score 0.46319. Sensors out of control limits: 26. Top signals (sensor: robust z-score): f_572:+225.0; f_195:+106.4; f_164:+54.3.
Run 163 is among the most anomalous runs.

## Run 275
Run 275 (2008-08-18 17:37:00) passed. Anomaly score 0.47209. Sensors out of control limits: 40. Top signals (sensor: robust z-score): f_204:+115468.4; f_067:+51273.0; f_572:+139.1.
Run 275 is among the most anomalous runs.

## Run 385
Run 385 (2008-08-21 23:08:00) passed. Anomaly score 0.46552. Sensors out of control limits: 28. Top signals (sensor: robust z-score): f_116:-59.8; f_041:+54.2; f_251:+36.2.
Run 385 is among the most anomalous runs.

## Run 457
Run 457 (2008-08-27 22:58:00) passed. Anomaly score 0.50044. Sensors out of control limits: 40. Top signals (sensor: robust z-score): f_204:+115464.8; f_067:+58599.5; f_251:+1871.5.
Run 457 is among the most anomalous runs.

## Run 634
Run 634 (2008-09-01 19:54:00) failed. Anomaly score 0.51788. Sensors out of control limits: 48. Top signals (sensor: robust z-score): f_204:+115466.8; f_067:+51274.1; f_196:+101.1.
Run 634 is among the most anomalous runs.

## Run 759
Run 759 (2008-09-08 07:41:00) passed. Anomaly score 0.46781. Sensors out of control limits: 27. Top signals (sensor: robust z-score): f_318:+15.1; f_456:+14.1; f_182:+13.2.
Run 759 is among the most anomalous runs.

## Run 856
Run 856 (2008-09-15 22:54:00) passed. Anomaly score 0.46726. Sensors out of control limits: 30. Top signals (sensor: robust z-score): f_035:+47.0; f_033:+45.8; f_034:+42.6.
Run 856 is among the most anomalous runs.

## Run 1185
Run 1185 (2008-09-29T21:48:00) failed. Risk score 0.14286, model fail probability 0.09806. Anomaly score 0.39474. Sensors out of control limits: 10. Top signals (sensor: robust z-score): f_425:+24.7; f_129:-4.1; f_483:+3.9.
Similar past runs of run 1185 (selected because: failed): 0 of 5 failed; nearest distance 6.061; most similar runs: 1109 (passed, distance 6.061), 1138 (passed, distance 6.788), 1096 (passed, distance 6.803), 1132 (passed, distance 6.942), 1087 (passed, distance 6.96).

## Run 1189
Run 1189 (2008-09-30T02:44:00) failed. Risk score 0.12883, model fail probability 0.07235. Anomaly score 0.40824. Sensors out of control limits: 16. Top signals (sensor: robust z-score): f_487:+6.3; f_569:+5.5; f_423:+5.1.
Similar past runs of run 1189 (selected because: failed): 0 of 5 failed; nearest distance 8.185; most similar runs: 1071 (passed, distance 8.185), 1110 (passed, distance 8.392), 1129 (passed, distance 8.714), 1032 (passed, distance 8.758), 1149 (passed, distance 8.783).

## Run 1190
Run 1190 (2008-09-30T04:01:00) passed. Risk score 0.9107, model fail probability 0.17519. Anomaly score 0.43534. Sensors out of control limits: 25. Top signals (sensor: robust z-score): f_040:-24.1; f_139:+6.5; f_485:+6.1.
Run 1190 is among the riskiest test-period runs.

## Run 1211
Run 1211 (2008-10-01T05:56:00) failed. Risk score 0.02679, model fail probability 0.04211. Anomaly score 0.39602. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_093:-5.0; f_087:-5.0; f_222:+4.8.
Similar past runs of run 1211 (selected because: failed): 0 of 5 failed; nearest distance 6.481; most similar runs: 1088 (passed, distance 6.481), 1135 (passed, distance 6.86), 1025 (passed, distance 6.978), 1018 (passed, distance 7.173), 1037 (passed, distance 7.645).

## Run 1227
Run 1227 (2008-10-02T03:17:00) failed. Risk score 0.66135, model fail probability 0.13112. Anomaly score 0.42379. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_040:-22.9; f_376:+8.3; f_238:+7.6.
Similar past runs of run 1227 (selected because: failed): 0 of 5 failed; nearest distance 8.429; most similar runs: 579 (passed, distance 8.429), 846 (passed, distance 8.809), 560 (passed, distance 8.998), 649 (passed, distance 9.086), 520 (passed, distance 9.336).

## Run 1230
Run 1230 (2008-10-02T04:23:00) passed. Risk score 0.963, model fail probability 0.1724. Anomaly score 0.46316. Sensors out of control limits: 33. Top signals (sensor: robust z-score): f_318:+15.9; f_224:+15.8; f_182:+13.5.
Run 1230 is among the riskiest test-period runs.

## Run 1238
Run 1238 (2008-10-02T09:10:00) failed. Risk score 0.60077, model fail probability 0.12428. Anomaly score 0.42246. Sensors out of control limits: 19. Top signals (sensor: robust z-score): f_116:-40.0; f_040:-22.9; f_162:+8.0.
Similar past runs of run 1238 (selected because: failed): 0 of 5 failed; nearest distance 7.219; most similar runs: 1149 (passed, distance 7.219), 1093 (passed, distance 8.53), 1163 (passed, distance 8.59), 1070 (passed, distance 8.66), 1071 (passed, distance 8.816).

## Run 1241
Run 1241 (2008-10-02T14:07:00) failed. Risk score 0.46556, model fail probability 0.16197. Anomaly score 0.39571. Sensors out of control limits: 9. Top signals (sensor: robust z-score): f_195:-4.3; f_162:+3.9; f_116:-3.8.
Similar past runs of run 1241 (selected because: failed): 0 of 5 failed; nearest distance 5.649; most similar runs: 1162 (passed, distance 5.649), 1156 (passed, distance 6.25), 1149 (passed, distance 6.528), 1166 (passed, distance 6.739), 1142 (passed, distance 6.742).

## Run 1242
Run 1242 (2008-10-02T14:10:00) failed. Risk score 0.7602, model fail probability 0.16222. Anomaly score 0.42282. Sensors out of control limits: 13. Top signals (sensor: robust z-score): f_210:+16.5; f_348:+12.8; f_162:+9.3.
Similar past runs of run 1242 (selected because: failed): 0 of 5 failed; nearest distance 10.128; most similar runs: 868 (passed, distance 10.128), 872 (passed, distance 10.133), 637 (passed, distance 10.315), 977 (passed, distance 10.516), 957 (passed, distance 10.531).

## Run 1254
Run 1254 (2008-10-02T21:32:00) failed. Risk score 0.9362, model fail probability 0.19631. Anomaly score 0.4369. Sensors out of control limits: 19. Top signals (sensor: robust z-score): f_116:-42.9; f_040:-22.7; f_251:+10.1.
Run 1254 is among the riskiest test-period runs.
Similar past runs of run 1254 (selected because: failed): 0 of 5 failed; nearest distance 8.89; most similar runs: 1133 (passed, distance 8.89), 1171 (passed, distance 8.913), 465 (passed, distance 8.972), 569 (passed, distance 9.927), 560 (passed, distance 9.969).

## Run 1257
Run 1257 (2008-10-02T22:33:00) passed. Risk score 0.9847, model fail probability 0.20251. Anomaly score 0.45679. Sensors out of control limits: 27. Top signals (sensor: robust z-score): f_135:+14.8; f_171:+8.8; f_139:+8.3.
Run 1257 is among the riskiest test-period runs.
Similar past runs of run 1257 (selected because: high risk): 0 of 5 failed; nearest distance 10.905; most similar runs: 1164 (passed, distance 10.905), 865 (passed, distance 10.957), 1166 (passed, distance 11.048), 1155 (passed, distance 11.363), 1162 (passed, distance 11.401).

## Run 1289
Run 1289 (2008-10-04T04:12:00) passed. Risk score 0.9349, model fail probability 0.17839. Anomaly score 0.43925. Sensors out of control limits: 25. Top signals (sensor: robust z-score): f_224:+8.8; f_496:+8.2; f_159:+6.0.
Run 1289 is among the riskiest test-period runs.

## Run 1302
Run 1302 (2008-10-04T23:18:00) failed. Risk score 0.24235, model fail probability 0.07633. Anomaly score 0.41531. Sensors out of control limits: 14. Top signals (sensor: robust z-score): f_471:+8.2; f_199:+7.7; f_335:+7.2.
Similar past runs of run 1302 (selected because: failed): 0 of 5 failed; nearest distance 5.559; most similar runs: 560 (passed, distance 5.559), 567 (passed, distance 8.665), 579 (passed, distance 8.672), 845 (passed, distance 8.821), 1171 (passed, distance 9.27).

## Run 1303
Run 1303 (2008-10-05T00:33:00) failed. Risk score 0.84311, model fail probability 0.1543. Anomaly score 0.43199. Sensors out of control limits: 20. Top signals (sensor: robust z-score): f_251:+85.7; f_116:-49.0; f_473:+8.7.
Similar past runs of run 1303 (selected because: failed): 0 of 5 failed; nearest distance 8.09; most similar runs: 560 (passed, distance 8.09), 845 (passed, distance 8.897), 678 (passed, distance 9.0), 1131 (passed, distance 9.046), 1133 (passed, distance 9.444).

## Run 1307
Run 1307 (2008-10-05T04:20:00) passed. Risk score 0.9617, model fail probability 0.18344. Anomaly score 0.4486. Sensors out of control limits: 22. Top signals (sensor: robust z-score): f_155:+75.3; f_290:+64.1; f_019:-45.8.
Run 1307 is among the riskiest test-period runs.

## Run 1324
Run 1324 (2008-10-05T15:30:00) failed. Risk score 0.44898, model fail probability 0.11985. Anomaly score 0.41435. Sensors out of control limits: 18. Top signals (sensor: robust z-score): f_153:+7.6; f_162:+7.4; f_211:+5.9.
Similar past runs of run 1324 (selected because: failed): 2 of 5 failed; nearest distance 8.268; most similar runs: 904 (passed, distance 8.268), 929 (failed, distance 8.476), 914 (failed, distance 8.739), 1027 (passed, distance 8.754), 411 (passed, distance 9.293).

## Run 1325
Run 1325 (2008-10-05T15:35:00) failed. Risk score 0.64605, model fail probability 0.1273. Anomaly score 0.42452. Sensors out of control limits: 14. Top signals (sensor: robust z-score): f_224:+10.0; f_496:+8.7; f_485:+6.9.
Similar past runs of run 1325 (selected because: failed): 0 of 5 failed; nearest distance 7.252; most similar runs: 1153 (passed, distance 7.252), 1066 (passed, distance 7.563), 1125 (passed, distance 8.228), 1146 (passed, distance 8.33), 1051 (passed, distance 8.696).

## Run 1327
Run 1327 (2008-10-05T16:37:00) failed. Risk score 0.7398, model fail probability 0.13542. Anomaly score 0.42806. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_558:+10.1; f_485:+7.6; f_560:+5.8.
Similar past runs of run 1327 (selected because: failed): 0 of 5 failed; nearest distance 7.724; most similar runs: 803 (passed, distance 7.724), 1057 (passed, distance 8.019), 748 (passed, distance 8.033), 995 (passed, distance 8.124), 1118 (passed, distance 8.609).

## Run 1328
Run 1328 (2008-10-05T16:49:00) failed. Risk score 0.44515, model fail probability 0.15006. Anomaly score 0.39776. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_572:+221.8; f_487:+7.6; f_161:+6.6.
Similar past runs of run 1328 (selected because: failed): 0 of 5 failed; nearest distance 6.989; most similar runs: 995 (passed, distance 6.989), 343 (passed, distance 7.264), 1101 (passed, distance 7.714), 894 (passed, distance 7.748), 1061 (passed, distance 7.769).

## Run 1329
Run 1329 (2008-10-05T18:46:00) failed. Risk score 0.44133, model fail probability 0.09432. Anomaly score 0.42447. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_139:+8.3; f_412:+6.4; f_161:+5.0.
Similar past runs of run 1329 (selected because: failed): 1 of 5 failed; nearest distance 8.117; most similar runs: 1153 (passed, distance 8.117), 1066 (passed, distance 8.435), 1062 (failed, distance 8.641), 1051 (passed, distance 8.656), 485 (passed, distance 8.946).

## Run 1333
Run 1333 (2008-10-05T20:30:00) passed. Risk score 0.9337, model fail probability 0.19746. Anomaly score 0.4358. Sensors out of control limits: 25. Top signals (sensor: robust z-score): f_367:+14.2; f_227:+14.2; f_365:+11.5.
Run 1333 is among the riskiest test-period runs.

## Run 1342
Run 1342 (2008-10-06T03:50:00) failed. Risk score 0.11352, model fail probability 0.0811. Anomaly score 0.40217. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_357:+5.4; f_081:-5.4; f_558:+5.3.
Similar past runs of run 1342 (selected because: failed): 1 of 5 failed; nearest distance 7.346; most similar runs: 502 (passed, distance 7.346), 511 (passed, distance 7.648), 601 (failed, distance 8.155), 560 (passed, distance 8.688), 957 (passed, distance 8.758).

## Run 1343
Run 1343 (2008-10-06T03:57:00) failed. Risk score 0.54719, model fail probability 0.1195. Anomaly score 0.42127. Sensors out of control limits: 14. Top signals (sensor: robust z-score): f_040:-22.6; f_139:+7.5; f_210:+5.6.
Similar past runs of run 1343 (selected because: failed): 0 of 5 failed; nearest distance 9.233; most similar runs: 846 (passed, distance 9.233), 827 (passed, distance 9.979), 865 (passed, distance 10.064), 447 (passed, distance 10.722), 852 (passed, distance 10.963).

## Run 1363
Run 1363 (2008-10-06T13:38:00) failed. Risk score 0.82781, model fail probability 0.16267. Anomaly score 0.4278. Sensors out of control limits: 14. Top signals (sensor: robust z-score): f_162:+4.9; f_197:+4.6; f_316:+4.1.
Similar past runs of run 1363 (selected because: failed): 0 of 5 failed; nearest distance 7.721; most similar runs: 507 (passed, distance 7.721), 468 (passed, distance 8.08), 558 (passed, distance 8.654), 502 (passed, distance 8.68), 447 (passed, distance 8.77).

## Run 1364
Run 1364 (2008-10-06T13:55:00) failed. Risk score 0.35587, model fail probability 0.12438. Anomaly score 0.40245. Sensors out of control limits: 11. Top signals (sensor: robust z-score): f_139:+8.3; f_487:+7.3; f_412:+6.4.
Similar past runs of run 1364 (selected because: failed): 1 of 5 failed; nearest distance 6.619; most similar runs: 1132 (passed, distance 6.619), 1169 (passed, distance 6.803), 1062 (failed, distance 6.961), 1030 (passed, distance 6.975), 1101 (passed, distance 7.015).

## Run 1365
Run 1365 (2008-10-06T15:00:00) failed. Risk score 0.80357, model fail probability 0.16304. Anomaly score 0.42586. Sensors out of control limits: 23. Top signals (sensor: robust z-score): f_251:+72.2; f_116:-62.1; f_569:+9.2.
Similar past runs of run 1365 (selected because: failed): 1 of 5 failed; nearest distance 8.424; most similar runs: 350 (passed, distance 8.424), 564 (passed, distance 9.104), 1066 (passed, distance 9.165), 277 (failed, distance 9.577), 1085 (passed, distance 9.844).

## Run 1374
Run 1374 (2008-10-06T18:55:00) passed. Risk score 0.9311, model fail probability 0.22916. Anomaly score 0.4348. Sensors out of control limits: 14. Top signals (sensor: robust z-score): f_155:+75.3; f_290:+64.1; f_019:-45.8.
Run 1374 is among the riskiest test-period runs.

## Run 1397
Run 1397 (2008-10-07T11:16:00) passed. Risk score 0.9949, model fail probability 0.27571. Anomaly score 0.46126. Sensors out of control limits: 26. Top signals (sensor: robust z-score): f_198:+38.5; f_338:+38.3; f_205:+35.0.
Run 1397 is among the riskiest test-period runs.
Similar past runs of run 1397 (selected because: high risk): 2 of 5 failed; nearest distance 20.914; most similar runs: 709 (failed, distance 20.914), 797 (failed, distance 22.932), 778 (passed, distance 23.263), 870 (passed, distance 23.684), 683 (passed, distance 23.721).

## Run 1400
Run 1400 (2008-10-07T13:10:00) failed. Risk score 0.47066, model fail probability 0.12846. Anomaly score 0.4119. Sensors out of control limits: 12. Top signals (sensor: robust z-score): f_348:+26.1; f_210:+15.5; f_075:+11.5.
Similar past runs of run 1400 (selected because: failed): 0 of 5 failed; nearest distance 9.227; most similar runs: 331 (passed, distance 9.227), 542 (passed, distance 9.398), 872 (passed, distance 9.856), 254 (passed, distance 9.858), 1052 (passed, distance 10.111).

## Run 1427
Run 1427 (2008-10-08T17:14:00) passed. Risk score 0.9477, model fail probability 0.16444. Anomaly score 0.45147. Sensors out of control limits: 25. Top signals (sensor: robust z-score): f_205:+24.1; f_200:+17.3; f_207:+16.2.
Run 1427 is among the riskiest test-period runs.

## Run 1438
Run 1438 (2008-10-09T04:34:00) failed. Risk score 0.57079, model fail probability 0.11214. Anomaly score 0.42723. Sensors out of control limits: 16. Top signals (sensor: robust z-score): f_026:-35.5; f_025:-14.9; f_031:-10.2.
Similar past runs of run 1438 (selected because: failed): 0 of 5 failed; nearest distance 7.661; most similar runs: 782 (passed, distance 7.661), 1109 (passed, distance 8.012), 1057 (passed, distance 8.07), 883 (passed, distance 8.243), 1132 (passed, distance 8.383).

## Run 1443
Run 1443 (2008-10-09T15:55:00) failed. Risk score 0.71173, model fail probability 0.14978. Anomaly score 0.42171. Sensors out of control limits: 18. Top signals (sensor: robust z-score): f_040:-24.6; f_144:+8.4; f_487:+6.9.
Similar past runs of run 1443 (selected because: failed): 1 of 5 failed; nearest distance 7.423; most similar runs: 1062 (failed, distance 7.423), 1010 (passed, distance 7.46), 1170 (passed, distance 7.916), 822 (passed, distance 7.926), 1101 (passed, distance 7.996).

## Run 1456
Run 1456 (2008-10-11T06:56:00) passed. Risk score 0.9707, model fail probability 0.20934. Anomaly score 0.44577. Sensors out of control limits: 27. Top signals (sensor: robust z-score): f_275:+54954.8; f_140:+51008.9; f_004:+3422.3.
Run 1456 is among the riskiest test-period runs.
Similar past runs of run 1456 (selected because: high risk): 0 of 5 failed; nearest distance 25102.003; most similar runs: 938 (passed, distance 25102.003), 935 (passed, distance 25102.173), 950 (passed, distance 25102.457), 946 (passed, distance 25102.536), 943 (passed, distance 25102.992).
Run 1456's nearest distance (25102.003) is far above the typical 8.117: no past run has a similar sensor profile, so its similar past runs say little about it. Its top signals show the sensors with the most extreme values.

## Run 1458
Run 1458 (2008-10-11T07:39:00) passed. Risk score 0.9962, model fail probability 0.23915. Anomaly score 0.49519. Sensors out of control limits: 34. Top signals (sensor: robust z-score): f_204:+115475.1; f_067:+7324.4; f_338:+220.5.
Run 1458 is among the riskiest test-period runs.
Run 1458 is among the most anomalous runs.
Similar past runs of run 1458 (selected because: high risk): 2 of 5 failed; nearest distance 39.608; most similar runs: 634 (failed, distance 39.608), 275 (passed, distance 41.127), 457 (passed, distance 69.163), 466 (passed, distance 69.37), 709 (failed, distance 78.625).

## Run 1489
Run 1489 (2008-10-13T20:53:00) passed. Risk score 0.9923, model fail probability 0.2168. Anomaly score 0.47849. Sensors out of control limits: 40. Top signals (sensor: robust z-score): f_338:+36.8; f_202:+31.6; f_332:+25.1.
Run 1489 is among the riskiest test-period runs.
Run 1489 is among the most anomalous runs.
Similar past runs of run 1489 (selected because: high risk): 2 of 5 failed; nearest distance 17.655; most similar runs: 778 (passed, distance 17.655), 798 (passed, distance 17.746), 709 (failed, distance 17.898), 795 (failed, distance 17.995), 810 (passed, distance 18.589).

## Run 1503
Run 1503 (2008-10-14T14:43:00) passed. Risk score 0.9133, model fail probability 0.18572. Anomaly score 0.43454. Sensors out of control limits: 24. Top signals (sensor: robust z-score): f_026:-37.0; f_025:-17.2; f_558:+14.3.
Run 1503 is among the riskiest test-period runs.

## Run 1519
Run 1519 (2008-10-15T02:42:00) failed. Risk score 0.85204, model fail probability 0.15407. Anomaly score 0.4327. Sensors out of control limits: 24. Top signals (sensor: robust z-score): f_251:+75.3; f_116:-67.9; f_099:+20.0.
Similar past runs of run 1519 (selected because: failed): 0 of 5 failed; nearest distance 9.675; most similar runs: 208 (passed, distance 9.675), 221 (passed, distance 9.757), 317 (passed, distance 9.808), 465 (passed, distance 10.005), 1059 (passed, distance 10.012).

## Run 1539
Run 1539 (2008-10-15T19:24:00) passed. Risk score 0.9235, model fail probability 0.15732. Anomaly score 0.44871. Sensors out of control limits: 27. Top signals (sensor: robust z-score): f_572:+226.5; f_040:-22.5; f_570:+13.6.
Run 1539 is among the riskiest test-period runs.
