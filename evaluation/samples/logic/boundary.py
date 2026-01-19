def get_page_items(items, page, page_size=10):
    # BUG: Off-by-one - skips first item on page > 1
    start = page * page_size
    end = start + page_size
    return items[start:end]


def binary_search(arr, target):
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid  # BUG: Should be mid + 1, causes infinite loop
        else:
            right = mid
    return -1
