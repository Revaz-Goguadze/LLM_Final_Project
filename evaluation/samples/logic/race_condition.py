balance = 0


def withdraw(amount):
    global balance
    # BUG: Race condition - check-then-act not atomic
    if balance >= amount:
        balance -= amount
        return True
    return False


def increment_counter():
    global counter
    # BUG: Not thread-safe
    counter = counter + 1
