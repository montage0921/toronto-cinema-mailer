import requests, re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

url = "https://www.google.com/search?q=Beau+Travail+%E8%B1%86%E7%93%A3&hl=zh-CN&gl=cn"
resp = requests.get(url, headers=HEADERS, timeout=10)
print(f"Status: {resp.status_code}, Size: {len(resp.text)}")

# Look for rating
m = re.search(r"评分[：:]\s*(\d+\.?\d*)", resp.text)
print(f"Rating: {m.group() if m else 'NOT FOUND'}")

# Look for douban URL
m2 = re.search(r"douban\.com/subject/(\d+)", resp.text)
print(f"Douban ID: {m2.group(1) if m2 else 'NOT FOUND'}")

# Print snippet around 评分
idx = resp.text.find("评分")
if idx >= 0:
    print(f"\nText around 评分: {repr(resp.text[max(0,idx-50):idx+100])}")
else:
    print(f"\n评分 not found. First 500 chars: {resp.text[:500]}")
