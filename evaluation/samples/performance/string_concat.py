def build_report(items):
    result = ""
    for item in items:
        # BUG: O(n^2) string concatenation in loop
        result += f"Item: {item}\n"
    return result


def format_csv(rows):
    output = ""
    for row in rows:
        # BUG: String concat in loop, should use join
        output = output + ",".join(row) + "\n"
    return output
