#!/usr/bin/env python3
"""测试 Hermes Web Panel"""
import sys, os, traceback
sys.path.insert(0, '/home/ubuntu/hermes-web')

# Don't import main.py directly (it has uvicorn.run at bottom)
# Instead, test the functions directly
import subprocess, re, json, urllib.request

def get_market_data():
    try:
        url = "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000300,sh000688"
        result = subprocess.run(["curl", "-s", "-m", "5", url], capture_output=True)
        raw = result.stdout.decode('gbk', errors='ignore')
        indices = []
        for line in raw.strip().split(';'):
            if '~' in line:
                parts = line.split('~')
                name = parts[1] if len(parts) > 1 else ""
                price = parts[3] if len(parts) > 3 else ""
                match = re.search(r'~(\d{14})~([\d.-]+)~([\d.-]+)~', line)
                if match:
                    change = match.group(2)
                    change_pct = match.group(3)
                    indices.append({"name": name, "price": price, "change": change, "change_pct": change_pct})
        return indices
    except Exception as e:
        print(f"市场数据错误: {e}")
        traceback.print_exc()
        return []

def get_fund_data():
    codes = {"019828": "鹏华石油天然气ETF联接C"}
    accounts = {
        "A": {"name": "武鸣主账户", "funds": [
            {"code": "019828", "amount": 127, "return_amount": None},
        ]}
    }
    for acc_name, acc in accounts.items():
        for f in acc["funds"]:
            try:
                url = f"https://fundgz.1234567.com.cn/js/{f['code']}.js"
                req = urllib.request.Request(url, headers={'Referer': 'https://fund.eastmoney.com'})
                resp = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                data = json.loads(resp[8:-2])
                f["nav"] = float(data.get("gsz", 0))
                f["change_pct"] = float(data.get("gszzl", 0))
                f["name"] = data.get("name", codes.get(f["code"], f["code"]))
                today_pnl = f["amount"] * f["change_pct"] / 100
                f["today_pnl"] = round(today_pnl, 2)
            except Exception as e:
                print(f"基金 {f['code']} 错误: {e}")
                f["nav"] = 0
                f["change_pct"] = 0
                f["today_pnl"] = 0
                f["name"] = codes.get(f["code"], f["code"])
    return accounts

# 测试
m = get_market_data()
print(f"市场数据: {len(m)}条")
for x in m:
    print(f"  {x['name']}: {x['price']} ({x['change']}, {x['change_pct']}%)")

print()
a = get_fund_data()
print(f"基金数据: OK")
