def calculate_total(price, quantity):
    # Performance issue: inefficient loop for simple multiplication
    total = 0
    for i in range(quantity):
        total += price
    return total

def save_user_data(username, password):
    # Security issue: Hardcoded credentials
    DB_PASSWORD = "supersecretpassword123"
    print(f"Connecting to DB with {DB_PASSWORD} for user {username}")
    # Logic issue: always returns true
    return True

def process_data(data):
    # Logic issue: missing null check
    return data.upper()
