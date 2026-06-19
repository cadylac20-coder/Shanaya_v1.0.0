import os, re, requests
from datetime import datetime, timedelta

SERPAPI_KEY = os.getenv("SERPAPI_KEY","")
SERPAPI_URL = "https://serpapi.com/search.json"

CITY_TO_IATA = {
    "delhi":"DEL","new delhi":"DEL","mumbai":"BOM","bombay":"BOM",
    "bangalore":"BLR","bengaluru":"BLR","hyderabad":"HYD","chennai":"MAA",
    "madras":"MAA","kolkata":"CCU","calcutta":"CCU","goa":"GOI","pune":"PNQ",
    "ahmedabad":"AMD","jaipur":"JAI","kochi":"COK","cochin":"COK",
    "lucknow":"LKO","chandigarh":"IXC","amritsar":"ATQ","varanasi":"VNS",
    "srinagar":"SXR","leh":"IXL","ladakh":"IXL","port blair":"IXZ","andaman":"IXZ",
    "guwahati":"GAU","coimbatore":"CJB","madurai":"IXM","trivandrum":"TRV",
    "thiruvananthapuram":"TRV","mangalore":"IXE","visakhapatnam":"VTZ","vizag":"VTZ",
    "bhopal":"BHO","indore":"IDR","jodhpur":"JDH","udaipur":"UDR","dehradun":"DED",
    "ranchi":"IXR","jammu":"IXJ","nagpur":"NAG","patna":"PAT","raipur":"RPR",
    "dubai":"DXB","abu dhabi":"AUH","doha":"DOH","riyadh":"RUH","jeddah":"JED",
    "kuwait":"KWI","muscat":"MCT","bangkok":"BKK","phuket":"HKT","singapore":"SIN",
    "kuala lumpur":"KUL","bali":"DPS","denpasar":"DPS","jakarta":"CGK",
    "colombo":"CMB","kathmandu":"KTM","paro":"PBH","male":"MLE","maldives":"MLE",
    "london":"LHR","paris":"CDG","amsterdam":"AMS","frankfurt":"FRA","zurich":"ZRH",
    "rome":"FCO","milan":"MXP","barcelona":"BCN","madrid":"MAD","istanbul":"IST",
    "new york":"JFK","los angeles":"LAX","toronto":"YYZ","sydney":"SYD",
    "melbourne":"MEL","tokyo":"NRT","seoul":"ICN","beijing":"PEK","hong kong":"HKG",
    "mauritius":"MRU","nairobi":"NBO","johannesburg":"JNB",
}

def city_to_code(city):
    c=city.lower().strip()
    if re.match(r'^[A-Za-z]{3}$',c): return c.upper()
    return CITY_TO_IATA.get(c, city.upper()[:3])

def normalise_date(d):
    if not d: return (datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d")
    dl=d.lower().strip()
    if dl=="tomorrow": return (datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d")
    if dl=="today": return datetime.now().strftime("%Y-%m-%d")
    for fmt in ["%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%d %b %Y","%d %B %Y","%d %b","%d %B","%B %d","%b %d","%B %d %Y","%b %d %Y"]:
        try:
            dt=datetime.strptime(d.strip(),fmt)
            if dt.year==1900:
                dt=dt.replace(year=datetime.now().year)
                if dt<datetime.now(): dt=dt.replace(year=datetime.now().year+1)
            return dt.strftime("%Y-%m-%d")
        except: pass
    return d

def search_google_flights(origin,destination,date=None,return_date=None,adults=1,currency="INR"):
    if not SERPAPI_KEY:
        return{"success":False,"flights":[],"cheapest":None,"message":"Google Flights not configured. Add SERPAPI_KEY to Render env vars.","source":"none"}
    oc=city_to_code(origin); dc=city_to_code(destination); dd=normalise_date(date)
    params={"engine":"google_flights","departure_id":oc,"arrival_id":dc,"outbound_date":dd,"currency":currency,"hl":"en","gl":"in","adults":adults,"type":"1" if not return_date else "2","api_key":SERPAPI_KEY}
    if return_date: params["return_date"]=normalise_date(return_date)
    try:
        resp=requests.get(SERPAPI_URL,params=params,timeout=20); resp.raise_for_status(); data=resp.json()
    except requests.exceptions.Timeout:
        return{"success":False,"flights":[],"cheapest":None,"message":"Search timed out. Please try again.","source":"google_flights"}
    except Exception as e:
        return{"success":False,"flights":[],"cheapest":None,"message":f"Could not reach Google Flights: {e}","source":"google_flights"}
    flights=[]
    for result in (data.get("best_flights",[])+data.get("other_flights",[]))[:8]:
        try:
            its=result.get("flights",[])
            if not its: continue
            fl=its[0]; ll=its[-1]
            flights.append({
                "airline":fl.get("airline","Unknown"),"flight_number":fl.get("flight_number",""),
                "departure":fl.get("departure_airport",{}).get("time","—"),
                "arrival":ll.get("arrival_airport",{}).get("time","—"),
                "from":fl.get("departure_airport",{}).get("name",oc),
                "to":ll.get("arrival_airport",{}).get("name",dc),
                "duration_str":_mts(result.get("total_duration",0)),
                "stops":len(its)-1,"stops_str":"Non-stop" if len(its)==1 else f"{len(its)-1} stop{'s' if len(its)>2 else ''}",
                "price":result.get("price",0),
                "price_str":f"₹{result.get('price',0):,}" if result.get("price") else "Contact for price",
                "date":dd,"is_best":result in data.get("best_flights",[]),
            })
        except: pass
    if not flights:
        return{"success":True,"flights":[],"cheapest":None,"message":f"No flights found for {origin}→{destination} on {dd}. Try different dates or contact MKOV team.","source":"google_flights"}
    flights.sort(key=lambda x:x["price"] if x["price"] else 999999)
    return{"success":True,"flights":flights[:6],"cheapest":flights[0],"message":f"Found {len(flights)} flight(s) from {origin} to {destination} on {dd}.","source":"google_flights","origin":oc,"dest":dc,"date":dd}

def _mts(m):
    if not m: return "—"
    return f"{m//60}h {m%60}m" if m%60 else f"{m//60}h"

def format_for_shanaya(result,origin,destination,date):
    if not result["success"]: return f"[GOOGLE FLIGHTS DATA]\n❌ {result['message']}"
    if not result["flights"]: return f"[GOOGLE FLIGHTS DATA]\n{result['message']}\nSuggest connecting to MKOV team."
    c=result["cheapest"]
    lines=[
        f"[GOOGLE FLIGHTS DATA] {result['message']}",
        f"Route: {origin.title()} ({result.get('origin','')}) → {destination.title()} ({result.get('dest','')})",
        f"Date: {result.get('date',date)}","",
        f"💰 CHEAPEST: {c['airline']} {c['flight_number']}",
        f"   Dep: {c['departure']} → Arr: {c['arrival']}",
        f"   Duration: {c['duration_str']} | {c['stops_str']}",
        f"   Price: {c['price_str']} per person","",
        "OTHER OPTIONS:"
    ]
    for i,f in enumerate(result["flights"][1:5],2):
        lines.append(f"   {i}. {f['airline']} {f['flight_number']} | {f['departure']}→{f['arrival']} | {f['duration_str']} | {f['stops_str']} | {f['price_str']}")
    lines+=["","NOTE: Prices from Google Flights, may change. To book: connect to MKOV team +91 8010700700","[Source: Google Flights via SerpApi]"]
    return "\n".join(lines)

def detect_flight_query(message):
    msg=message.lower()
    if not any(k in msg for k in ["flight","fly","flying","airline","plane","ticket","air ticket","cheapest flight","fare","airfare","how to reach","travel from"]):
        return{"is_flight":False}
    found=[]
    for city in sorted(CITY_TO_IATA.keys(),key=len,reverse=True):
        if city in msg and city not in [c[0] for c in found]:
            found.append((city,CITY_TO_IATA[city]))
            if len(found)==2: break
    origin=found[0][0] if found else None; dest=found[1][0] if len(found)>1 else None
    date=None
    for pat in [r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?)\b',r'\b(\d{4}-\d{2}-\d{2})\b',r'\b(tomorrow|today|next\s+\w+)\b']:
        m=re.search(pat,msg,re.I)
        if m: date=m.group(1); break
    adults=1
    m=re.search(r'(\d+)\s*(?:people|persons?|passengers?|adults?|pax|tickets?)',msg)
    if m: adults=min(int(m.group(1)),9)
    return_date=None
    if any(k in msg for k in ["return","round trip","coming back"]):
        rm=re.search(r'return(?:ing)?\s+(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+\w+(?:\s+\d{4})?)',msg,re.I)
        if rm: return_date=rm.group(1)
    return{"is_flight":True,"origin":origin,"destination":dest,"date":date,"return_date":return_date,"adults":adults}
