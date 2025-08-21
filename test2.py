import requests

# ===== PROXIES =====
proxies = [ ] #add your proxies here

def test_proxy(proxy):
    try:
        response = requests.get("http://httpbin.org/ip", proxies={"http": proxy, "https": proxy}, timeout=10)
        if response.status_code == 200:
            print(f"[WORKING] {proxy} → {response.json()}")
        else:
            print(f"[FAIL] {proxy} → Status: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] {proxy} → {e}")

# Test all proxies
for proxy in proxies:
    test_proxy(proxy)
