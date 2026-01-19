# Evaluation Dataset Schema

You can provide a JSON array or JSONL file. Each case looks like:

```json
{
  "id": "case-001",
  "diff": "git diff text",
  "query": "optional user query",
  "expected_issues": [
    {
      "type": "logic",
      "file": "path/to/file.py",
      "line": 42,
      "keyword": "off-by-one"
    }
  ]
}
```

Matching rules:
- `type` and `file` must match if provided.
- `line` matches within +/- 3 lines.
- `keyword` must appear in the predicted description/evidence.

Outputs include:
- Overall precision/recall/fix_rate
- Per-case scoring
- Per-model scoring (security/logic/performance)
