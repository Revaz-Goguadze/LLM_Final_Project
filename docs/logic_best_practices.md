# Python Logic & Code Quality Best Practices

## 1. Null/None Checking
```python
# ❌ BAD - No null check
def get_name(user):
    return user.name.upper()

# ✅ GOOD - Defensive coding
def get_name(user):
    if user is None or user.name is None:
        return "Unknown"
    return user.name.upper()
```

## 2. Off-by-One Errors
```python
# ❌ BAD - Off-by-one (misses last element)
for i in range(len(items) - 1):
    process(items[i])

# ✅ GOOD - Correct range
for i in range(len(items)):
    process(items[i])

# ✅ BETTER - Pythonic iteration
for item in items:
    process(item)
```

## 3. Exception Handling
```python
# ❌ BAD - Bare except
try:
    result = risky_operation()
except:
    pass

# ✅ GOOD - Specific exceptions
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except ConnectionError as e:
    logger.warning(f"Connection failed: {e}")
    result = fallback_value
```

## 4. Boolean Logic
```python
# ❌ BAD - Redundant comparison
if is_valid == True:
    process()

# ✅ GOOD - Direct boolean
if is_valid:
    process()

# ❌ BAD - Confusing negation
if not (a and b):
    skip()

# ✅ GOOD - De Morgan's law
if not a or not b:
    skip()
```

## 5. Early Returns (Guard Clauses)
```python
# ❌ BAD - Deep nesting
def process(user, order):
    if user is not None:
        if order is not None:
            if order.is_valid:
                # actual logic here
                return result
    return None

# ✅ GOOD - Guard clauses
def process(user, order):
    if user is None:
        return None
    if order is None:
        return None
    if not order.is_valid:
        return None
    
    # actual logic here
    return result
```

## 6. Immutability
```python
# ❌ BAD - Mutable default argument
def add_item(item, items=[]):
    items.append(item)
    return items

# ✅ GOOD - None as default
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

## 7. Type Hints
```python
# ❌ BAD - No type information
def calculate(a, b, c):
    return a + b * c

# ✅ GOOD - Clear types
def calculate(a: float, b: float, c: float) -> float:
    return a + b * c
```
