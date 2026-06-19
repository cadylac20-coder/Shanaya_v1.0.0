import os, re, requests
from bs4 import BeautifulSoup

PORTAL_BASE = os.getenv("FLIGHT_PORTAL_URL","https://1-sourcev2.uniglobemkov.com")
USERNAME    = os.getenv("FLIGHT_PORTAL_USERNAME","")
PASSWORD    = os.getenv("FLIGHT_PORTAL_PASSWORD","")
_session = None; _valid = False

def _get_session():
    global _session, _valid
    if _session and _valid: return _session
    if not USERNAME or not PASSWORD: raise RuntimeError("Flight portal credentials not set.")
    _session = requests.Session()
    _session.headers.update({"User-Agent":"Mozilla/5.0"})
    resp = _session.get(f"{PORTAL_BASE}/flight", timeout=15); resp.raise_for_status()
    soup = BeautifulSoup(resp.text,"html.parser")
    csrf = None
    for name in ["_token","csrf_token","csrfmiddlewaretoken"]:
        tag = soup.find("input",{"name":name})
        if tag: csrf=tag.get("value"); break
    form = soup.find("form")
    post_url = form.get("action",f"{PORTAL_BASE}/flight") if form else f"{PORTAL_BASE}/flight"
    if post_url.startswith("/"): post_url = PORTAL_BASE + post_url
    payload = {"username":USERNAME,"password":PASSWORD}
    if csrf: payload["_token"] = csrf
    r = _session.post(post_url, data=payload, timeout=15, allow_redirects=True)
    if "invalid" in r.text.lower(): _valid=False; raise RuntimeError("Portal login failed.")
    _valid = True; return _session

def is_flight_query(message):
    msg = message.lower()
    if not any(k in msg for k in ["flight","fly","ticket","airline","fare"]): return False,None,None,None
    from google_flights import CITY_TO_IATA, city_to_code
    found=[]
    for city in sorted(CITY_TO_IATA.keys(),key=len,reverse=True):
        if city in msg: found.append(city_to_code(city))
        if len(found)==2: break
    date=None
    m=re.search(r'\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\b',msg,re.I)
    if m: date=m.group(1)
    return True, found[0] if found else None, found[1] if len(found)>1 else None, date

def search_flights(origin,destination,date):
    try:
        sess=_get_session()
        resp=sess.get(f"{PORTAL_BASE}/flight/search",params={"from":origin,"to":destination,"date":date,"adults":1},timeout=20)
        if resp.status_code!=200: return{"success":False,"flights":[],"message":"Portal search failed.","raw_count":0}
        soup=BeautifulSoup(resp.text,"html.parser"); flights=[]
        for row in soup.find_all("tr")[1:]:
            cells=[td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells)>=4:
                times=[c for c in cells if re.match(r'\d{1,2}:\d{2}',c)]
                prices=[c for c in cells if re.search(r'[\d,]{3,}',c) and any(s in c for s in ['₹','Rs','INR'])]
                if times: flights.append({"airline":cells[0],"departure":times[0] if times else "—","arrival":times[1] if len(times)>1 else "—","from":origin,"to":destination,"date":date,"fare":prices[0] if prices else "Contact","duration":"—","stops":0,"stops_str":"—"})
        return{"success":True,"flights":flights[:6],"message":f"Found {len(flights)} flights.","raw_count":len(flights)}
    except Exception as e:
        return{"success":False,"flights":[],"message":str(e),"raw_count":0}

def format_flights_for_shanaya(result):
    if not result["success"] or not result["flights"]: return f"[FLIGHT DATA]\n{result['message']}\nConnect user to MKOV team."
    lines=[f"[FLIGHT DATA] {result['message']}"]
    for i,f in enumerate(result["flights"],1):
        lines.append(f"{i}. {f['airline']} | {f['from']}→{f['to']} | Dep:{f['departure']} Arr:{f['arrival']} | Fare:{f['fare']}")
    lines.append("[Source: Uniglobe MKOV internal flight system]")
    return "\n".join(lines)
