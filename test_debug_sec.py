import sys, os
sys.path.insert(0, "c:/2_Study/stock")
os.chdir("c:/2_Study/stock")
from src.fetcher.sec_edgar import _sec_get, _sec_get_text

# Berkshire 13F accession
acc_dashed = "0001193125-26-054580"
acc_clean = acc_dashed.replace("-", "")
cik = "1067983"

# Try index.json
url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/index.json"
print(f"Trying: {url}")
data = _sec_get(url)
print(f"Result: {data is not None}")

if data:
    items = data.get("directory", {}).get("item", [])
    for item in items:
        print(f"  {item.get('name','')}")
else:
    # Try without leading zeros in CIK
    print("Trying text listing...")
    listing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/"
    html = _sec_get_text(listing_url)
    if html:
        print(f"Got HTML, length={len(html)}")
        print(html[:500])
    else:
        print("No HTML either")

# Also debug: print a small Burry XML sample
print("\n--- Debug Burry XML values ---")
burry_data = _sec_get("https://data.sec.gov/submissions/CIK0001649339.json")
if burry_data:
    recent = burry_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    for i, f in enumerate(forms[:5]):
        if "13F" in f:
            b_acc = accs[i].replace("-", "")
            b_cik = "1649339"
            iurl = f"https://www.sec.gov/Archives/edgar/data/{b_cik}/{b_acc}/index.json"
            idx = _sec_get(iurl)
            if idx:
                for it in idx.get("directory", {}).get("item", []):
                    n = it.get("name", "")
                    if ".xml" in n.lower() and "infotable" in n.lower():
                        xml_url = f"https://www.sec.gov/Archives/edgar/data/{b_cik}/{b_acc}/{n}"
                        xml_text = _sec_get_text(xml_url)
                        if xml_text:
                            # Print first entry's value
                            import re
                            vals = re.findall(r"<(?:\w+:)?value[^>]*>(.*?)</", xml_text[:3000], re.I)
                            shares = re.findall(r"<(?:\w+:)?sshPrnamt[^>]*>(.*?)</", xml_text[:3000], re.I)
                            print(f"First values: {vals[:3]}")
                            print(f"First shares: {shares[:3]}")
                            print(f"XML snippet (first 800 chars): {xml_text[:800]}")
                        break
            break
