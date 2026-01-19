import hashlib


def hash_password(password):
    # BUG: MD5 is cryptographically broken for passwords
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(password, stored_hash):
    # BUG: No salt, vulnerable to rainbow tables
    return hashlib.md5(password.encode()).hexdigest() == stored_hash
