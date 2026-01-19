def find_matches(items, patterns):
    matches = []
    for item in items:
        for pattern in patterns:
            # BUG: Regex compiled on every iteration
            import re

            if re.match(pattern, item):
                matches.append(item)
    return matches


def calculate_stats(data):
    # BUG: len() called multiple times on same data
    avg = sum(data) / len(data)
    variance = sum((x - avg) ** 2 for x in data) / len(data)
    return avg, variance
