# Evaluation Plan

## Dataset
- Labeled test cases with known bugs and expected detections.
- Split into train/dev/test for tuning prompts and retrieval settings.

## Metrics
- Precision = true_positive / (true_positive + false_positive)
- Recall = true_positive / (true_positive + false_negative)
- Fix Rate = fixed / attempted

## Procedure
1. Run each model on the same inputs.
2. Compare output issues to labeled ground truth.
3. Score per model and per category (severity, language, bug type).
4. Track cost, latency, and token usage.

## Outputs
- Per-model scorecard (precision/recall/fix rate).
- Failure analysis (missed bugs, hallucinations).
- Recommendation for default model or ensemble.

