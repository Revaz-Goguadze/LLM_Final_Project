import requests

# BUG: Hardcoded API key
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "admin123"


def fetch_data():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.get("https://api.example.com/data", headers=headers)


def connect_db():
    # BUG: Hardcoded credentials
    return f"postgresql://admin:{DATABASE_PASSWORD}@localhost/mydb"
