# Python Best Practices (RAG Docs)

## Code Style and Readability
- Keep functions small and focused on a single task.
- Prefer explicit over implicit; avoid clever one-liners for complex logic.
- Use descriptive variable and function names.
- Add docstrings for public functions and modules.

## Error Handling
- Catch specific exceptions instead of bare `except`.
- Use `finally` for cleanup tasks.
- Avoid swallowing exceptions; log or re-raise with context.

## Security
- Never hardcode secrets; load from environment or secret managers.
- Validate and sanitize external input.
- Avoid `eval`/`exec` on untrusted data.

## Performance
- Prefer list comprehensions for simple transforms, but avoid nesting deeply.
- Use generators for large datasets to avoid high memory usage.
- Cache expensive computations when input repeats.

## Testing
- Write unit tests for edge cases and failure paths.
- Use fixtures to isolate state and speed up tests.
- Keep tests deterministic and fast.

## Common Pitfalls
- Mutable default arguments (`def f(x=[]):`) cause shared state bugs.
- Using `is` for string/int equality is incorrect; use `==`.
- Modifying a list while iterating can skip items.
