import requests
import time


def fetch_all_urls(urls):
    results = []
    for url in urls:
        # BUG: Sequential blocking I/O - should use async/threading
        response = requests.get(url)
        results.append(response.text)
    return results


def poll_status(endpoint):
    while True:
        # BUG: Busy waiting with no backoff
        status = requests.get(endpoint).json()
        if status["done"]:
            return status
        time.sleep(0.1)
