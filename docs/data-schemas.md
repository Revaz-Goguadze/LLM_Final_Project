# Data Schemas (Draft)

## Report JSON
```json
{
  "model": "string",
  "issues": [
    {
      "id": "string",
      "severity": "low|medium|high|critical",
      "file": "path",
      "line": 123,
      "message": "string",
      "evidence": "string",
      "confidence": 0.0
    }
  ],
  "summary": {
    "issue_count": 0,
    "high_count": 0
  }
}
```

## Fix Request
```json
{
  "issue_id": "string",
  "file": "path",
  "context": "string",
  "desired_change": "string"
}
```

## Fix Response
```json
{
  "issue_id": "string",
  "patch": "diff",
  "explanation": "string"
}
```

