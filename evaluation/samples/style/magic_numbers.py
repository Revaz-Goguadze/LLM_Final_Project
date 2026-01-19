def calculate_price(base):
    # BUG: Magic numbers without explanation
    return base * 1.0825 + 5.99


def is_valid_password(password):
    # BUG: Magic numbers for constraints
    return len(password) >= 8 and len(password) <= 128


def paginate(items, page):
    # BUG: Hardcoded page size
    return items[page * 20 : (page + 1) * 20]
