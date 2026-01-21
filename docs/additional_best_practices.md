# Additional Best Practices

## Security
- Avoid hardcoded secrets in source; load from environment variables or a secrets manager.
- Validate and normalize file paths; reject `..` segments and absolute paths for user input.
- Prefer context managers for file access and close handles deterministically.

## Logic
- Validate inputs before arithmetic; handle zero and null cases explicitly.
- Keep units consistent (percent vs fraction) and document expected input ranges.

## Performance
- Avoid reading entire files into memory unless size is bounded and known.
- Prefer built-in sorting utilities over quadratic custom sorts.
