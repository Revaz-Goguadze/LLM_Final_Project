def process_orders(orders):
    results = []
    for order in orders:
        # BUG: N+1 Query - db_fetch inside loop
        details = db_fetch_details(order.id)
        results.append(details)
    return results

def slow_check(items):
    # BUG: O(n^2) nested loop for finding duplicates
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                if items[i] not in duplicates:
                    duplicates.append(items[i])
    return duplicates
