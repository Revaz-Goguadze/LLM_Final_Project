# Python Performance Best Practices

## 1. Avoid N+1 Queries
```python
# ❌ BAD - N+1 query problem
for user in users:
    orders = db.query(Order).filter(Order.user_id == user.id).all()

# ✅ GOOD - Eager loading
users = db.query(User).options(joinedload(User.orders)).all()
```

## 2. Use List Comprehensions
```python
# ❌ BAD - Slow loop
result = []
for x in data:
    if x > 0:
        result.append(x * 2)

# ✅ GOOD - List comprehension (faster)
result = [x * 2 for x in data if x > 0]
```

## 3. Avoid Nested Loops When Possible
```python
# ❌ BAD - O(n²) complexity
for i in items1:
    for j in items2:
        if i.id == j.id:
            process(i, j)

# ✅ GOOD - O(n) with dictionary
items2_dict = {j.id: j for j in items2}
for i in items1:
    if i.id in items2_dict:
        process(i, items2_dict[i.id])
```

## 4. Use Generators for Large Data
```python
# ❌ BAD - Loads all into memory
def get_all_lines(filename):
    return open(filename).readlines()

# ✅ GOOD - Generator (memory efficient)
def get_all_lines(filename):
    with open(filename) as f:
        for line in f:
            yield line
```

## 5. Cache Expensive Operations
```python
from functools import lru_cache

# ✅ GOOD - Memoization
@lru_cache(maxsize=128)
def expensive_calculation(n):
    # Complex computation
    return result
```

## 6. Use Built-in Functions
```python
# ❌ BAD - Manual implementation
total = 0
for x in numbers:
    total += x

# ✅ GOOD - Built-in (optimized C code)
total = sum(numbers)
```

## 7. String Concatenation
```python
# ❌ BAD - Creates new string each time
result = ""
for s in strings:
    result += s

# ✅ GOOD - Join is optimized
result = "".join(strings)
```
