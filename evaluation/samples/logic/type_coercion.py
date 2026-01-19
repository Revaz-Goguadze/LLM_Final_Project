def compare_ids(id1, id2):
    # BUG: String "123" != int 123 comparison fails silently
    return id1 == id2


def calculate_total(price, quantity):
    # BUG: If price is string "10", result is "101010..." not 30
    return price * quantity


def is_valid_age(age):
    # BUG: "25" > 18 works but "9" > "18" is True (string comparison)
    return age > 18 and age < 120
