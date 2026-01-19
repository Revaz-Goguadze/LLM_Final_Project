# Python Security Best Practices

## 1. Never Hardcode Secrets
```python
# ❌ BAD
SECRET_KEY = "my-secret-key-123"
DB_PASSWORD = "admin123"

# ✅ GOOD
import os
SECRET_KEY = os.getenv("SECRET_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")
```

## 2. SQL Injection Prevention
```python
# ❌ BAD - SQL Injection vulnerable
query = f"SELECT * FROM users WHERE username = '{username}'"

# ✅ GOOD - Parameterized query
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

## 3. XSS Prevention
```python
# ❌ BAD - XSS vulnerable
return f"<div>{user_input}</div>"

# ✅ GOOD - Escape user input
from markupsafe import escape
return f"<div>{escape(user_input)}</div>"
```

## 4. Password Hashing
```python
# ❌ BAD - Plain text or weak hash
password_hash = hashlib.md5(password).hexdigest()

# ✅ GOOD - Use bcrypt or argon2
import bcrypt
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

## 5. Input Validation
```python
# ❌ BAD - No validation
def process_age(age):
    return int(age)

# ✅ GOOD - Validate and sanitize
def process_age(age):
    if not isinstance(age, (int, str)):
        raise ValueError("Invalid age type")
    age_int = int(age)
    if age_int < 0 or age_int > 150:
        raise ValueError("Age out of valid range")
    return age_int
```

## 6. HTTPS and Secure Cookies
```python
# ✅ Always use secure cookies in production
response.set_cookie('session', token, secure=True, httponly=True, samesite='Strict')
```
