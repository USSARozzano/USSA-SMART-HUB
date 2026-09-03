from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pathlib import Path
from datetime import datetime, date
from urllib.parse import urljoin, quote_plus, urlparse
import requests, re, json, math
from bs4 import BeautifulSoup

ROOT=Path(__file__).parent
app=FastAPI(title="USSA SMART HUB V2")
CSI_OLD="https://www.csi.milano.it"
CSI_LIVE="https://live.centrosportivoitaliano.it"
HEADERS={"User-Agent":"USSA-SMART-HUB/2.0 (+https://ussa-smart-hub-v2.onrender.com)","Accept-Language":"it-IT,it;q=0.9"}
CACHE={}

def clean(s): return re.sub(r"\s+"," ",s or "").strip()
def load_json(name,default):
    try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
    except:return default
def teams_dict(): return {x["key"]:x for x in load_json("teams.json",[])}
def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=25)
    r.raise_for_status()
    return r.text
def soup(url): return BeautifulSoup(fetch(url),"html.parser")
def iso_dt(d,t="00:00"):
    return datetime.fromisoformat(f"{d}T{t or '00:00'}")
def parse_hm(v):
    h,m=map(int,v.split(":"));return h*60+m

@app.get("/")
def home(): return FileResponse(ROOT/"index.html")
@app.get("/assets/ussa-logo.png")
def logo(): return FileResponse(ROOT/"ussa-logo.png",media_type="image/png")
@app.get("/api/teams")
def api_teams(): return load_json("teams.json",[])
@app.get("/api/hub")
def api_hub(): return load_json("hub.json",{})

# ---------- HOME ----------
@app.get("/api/home/now")
def home_now():
    td=teams_dict();now=datetime.now();wd=now.isoweekday();minute=now.hour*60+now.minute;items=[]
    for t in td.values():
        for x in t.get("training",[]):
            try:
                if int(x.get("weekday",0))==wd and parse_hm(x["start"])<=minute<parse_hm(x["end"]):
                    items.append({"kind":"ALLENAMENTO","team_key":t["key"],"title":t["label"],"meta":f"{x['start']}–{x['end']}","place":x.get("place","")})
            except:pass
    # Manual home games in progress are also "Ora in campo".
    for e in load_json("events.json",[]):
        try:
            dt=iso_dt(e["date"],e.get("time","00:00"))
            # demo/default duration 120 minutes for a match
            if e.get("kind")=="PARTITA" and 0 <= (now-dt).total_seconds() < 120*60:
                items.append({"kind":"PARTITA","title":e.get("meta","PARTITA"),"meta":e.get("title",""),"place":e.get("field","")})
        except:pass
    return {"items":items}

def live_schedule_for_team(t):
    """Best effort parser for CSI LIVE fixture rows. Returns only rows containing Ussa Rozzano."""
    url=t.get("csi_live_url")
    if not url:return []
    s=soup(url);out=[];seen=set()
    # Most CSI LIVE schedules are rendered as table rows.
    for tr in s.find_all("tr"):
        txt=clean(tr.get_text(" ",strip=True))
        if "USSA ROZZANO" not in txt.upper():continue
        md=re.search(r"\b(\d{2}/\d{2}/\d{2})\b",txt)
        mt=re.search(r"\b([0-2]\d:[0-5]\d)\b",txt)
        score=re.search(r"\b(\d+)\s+(\d+)\b\s*$",txt)
        links=[a for a in tr.find_all("a",href=True)]
        game_url=""
        for a in links:
            href=urljoin(url,a["href"])
            if re.search(r"/P20\d{6,}[A-Z0-9]+/?",urlparse(href).path,re.I):
                game_url=href;break
        cells=[clean(x.get_text(" ",strip=True)) for x in tr.find_all(["td","th"])]
        # try to identify team names by removing date/time/numbers
        names=[]
        for c in cells:
            if not c or re.fullmatch(r"\d{2}/\d{2}/\d{2}",c) or re.fullmatch(r"[0-2]\d:[0-5]\d",c) or re.fullmatch(r"\d+",c):continue
            if c.upper() in {"ANDATA","RITORNO"}:continue
            names.append(c)
        if not md:continue
        try:dt=datetime.strptime(md.group(1)+(mt.group(1) if mt else "00:00"),"%d/%m/%y%H:%M")
        except:continue
        key=(md.group(1),mt.group(1) if mt else "",txt)
        if key in seen:continue
        seen.add(key)
        out.append({"date":dt.date().isoformat(),"time":mt.group(1) if mt else "","raw":txt,"names":names,"result":score.group(0) if score else "","detail_url":game_url,"team_key":t["key"],"meta":t["label"]})
    return out

@app.get("/api/home/upcoming")
def home_upcoming():
    now=datetime.now();items=[]
    # manual events / preseason matches
    for e in load_json("events.json",[]):
        try:
            dt=iso_dt(e["date"],e.get("time","00:00"))
            if dt>=now:
                items.append({**e,"_sort":dt.isoformat(),"source":"USSA"})
        except:pass
    # CSI LIVE future games: once the 26/27 schedules are published these become primary.
    for t in teams_dict().values():
        if t.get("visible") is False or not t.get("csi_live_url"):continue
        try:
            for m in live_schedule_for_team(t):
                dt=iso_dt(m["date"],m.get("time","00:00"))
                if dt<now or m.get("result"):continue
                title="Partita USSA"
                if m.get("names"): title=" – ".join(m["names"][-2:])
                items.append({"kind":"PARTITA","date":m["date"],"time":m.get("time",""),"title":title,"meta":t["label"],"field":"","team_key":t["key"],"detail_url":m.get("detail_url",""),"_sort":dt.isoformat(),"source":"CSI LIVE"})
        except:pass
    dedup={}
    for x in items:
        key=(x.get("date"),x.get("time"),x.get("title"),x.get("meta"))
        dedup[key]=x
    out=sorted(dedup.values(),key=lambda x:x["_sort"])
    for x in out:x.pop("_sort",None)
    return {"items":out[:100]}

# ---------- CSI LIVE ----------
def live_standings(t):
    url=t.get("csi_live_url")
    if not url:raise HTTPException(404,"Competizione CSI LIVE non ancora collegata")
    s=soup(url)
    for table in s.find_all("table"):
        rows=table.find_all("tr")
        if not rows:continue
        hdr=[clean(x.get_text(" ",strip=True)).upper() for x in rows[0].find_all(["th","td"])]
        if not ("SQUADRA" in " ".join(hdr) and ("PT" in hdr or any(x=="PT" for x in hdr))):continue
        result=[]
        for tr in rows[1:]:
            vals=[clean(x.get_text(" ",strip=True)) for x in tr.find_all(["th","td"])]
            if len(vals)<4:continue
            # normalize expected CSI LIVE: #, squadra, pt, pg, v, n, p...
            nums=[]
            for v in vals:
                try: nums.append(int(v))
                except: pass
            teamname=next((v for v in vals if re.search(r"[A-Za-zÀ-ÿ]",v) and v.upper() not in {"PLAYOFF","PLAYOUT"}),"")
            if not teamname:continue
            pos=next((int(v) for v in vals if re.fullmatch(r"\d+",v)),len(result)+1)
            # positional extraction is more reliable for current CSI LIVE tables
            try:
                result.append({"position":int(vals[0]),"team":vals[1],"points":int(vals[2]),"played":int(vals[3]),"wins":int(vals[4]) if len(vals)>4 and vals[4].isdigit() else None,"draws":int(vals[5]) if len(vals)>5 and vals[5].isdigit() else None,"losses":int(vals[6]) if len(vals)>6 and vals[6].isdigit() else None})
            except:
                continue
        if result:return result
    return []

def live_matches(t):
    url=t.get("csi_live_url")
    if not url:raise HTTPException(404,"Competizione CSI LIVE non ancora collegata")
    # Parse every schedule row and return USSA only.
    return live_schedule_for_team(t)

def live_scorers(t):
    url=t.get("csi_live_url")
    if not url:return []
    s=soup(url)
    out=[]
    for table in s.find_all("table"):
        rows=table.find_all("tr")
        if not rows:continue
        hdr=[clean(x.get_text(" ",strip=True)).upper() for x in rows[0].find_all(["th","td"])]
        joined=" ".join(hdr)
        if not ("GOL" in joined or "RETI" in joined) or not ("GIOCAT" in joined or "ATLETA" in joined):continue
        for tr in rows[1:]:
            vals=[clean(x.get_text(" ",strip=True)) for x in tr.find_all(["th","td"])]
            line=" | ".join(vals)
            if "USSA" not in line.upper():continue
            goal=next((int(v) for v in reversed(vals) if re.fullmatch(r"\d+",v)),0)
            name=next((v for v in vals if re.search(r"[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]{2,}",v) and "USSA" not in v.upper()),"")
            if name and goal:out.append({"name":name,"goals":goal})
        if out:break
    out.sort(key=lambda x:(-x["goals"],x["name"]))
    return out

@app.get("/api/team/{key}/standings")
def standings(key:str):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    if not t.get("classifica"):return {"available":False,"standings":[]}
    rows=live_standings(t)
    return {"available":True,"standings":rows,"source":"CSI LIVE"}

@app.get("/api/team/{key}/matches")
def matches(key:str):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    arr=live_matches(t)
    return {"matches":[x for x in arr if x.get("result")],"source":"CSI LIVE"}

@app.get("/api/team/{key}/next")
def next_matches(key:str):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    today=datetime.now()
    arr=[]
    for x in live_matches(t):
        try:dt=iso_dt(x["date"],x.get("time","00:00"))
        except:continue
        if dt>=today and not x.get("result"):arr.append(x)
    return {"matches":arr,"source":"CSI LIVE"}

@app.get("/api/team/{key}/players")
def players(key:str):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    if not t.get("marcatori"):return {"available":False,"players":[]}
    arr=live_scorers(t)
    # Fallback: old CSI Milano "Giocatori" table, useful where LIVE scorer table is incomplete.
    if not arr and t.get("url"):
        try:
            s=soup(t["url"].split("?")[0]+"?v=giocatori")
            for tr in s.find_all("tr"):
                vals=[clean(x.get_text(" ",strip=True)) for x in tr.find_all(["td","th"])]
                if len(vals)<2:continue
                line=" ".join(vals)
                m=re.search(r"\b(\d+)\s*$",line)
                if not m:continue
                g=int(m.group(1))
                if g<=0:continue
                name=" ".join(vals[:-1]).strip()
                if name:arr.append({"name":name,"goals":g})
            arr.sort(key=lambda x:(-x["goals"],x["name"]))
        except:pass
    return {"available":True,"players":arr,"source":"CSI LIVE"}

# ---------- OLD CSI ROSTER / PHOTOS ----------
@app.get("/api/team/{key}/roster")
def roster(key:str):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    manual=t.get("roster") or []
    if manual:return {"players":manual,"source":"USSA"}
    if not t.get("url"):return {"players":[]}
    try:
        s=soup(t["url"].split("?")[0]+"?v=giocatori");out=[];seen=set()
        for tr in s.find_all("tr"):
            txt=clean(tr.get_text(" ",strip=True))
            if not txt or txt.upper().startswith("GIOCAT"):continue
            anchors=tr.find_all("a",href=True)
            name=""
            photo=""
            for a in anchors:
                if "/albo/giocatori/" in a["href"]:
                    name=clean(a.get_text(" ",strip=True))
                    img=a.find("img",src=True)
                    if img:photo=urljoin(CSI_OLD,img["src"])
                    break
            if name and name not in seen:
                seen.add(name);out.append({"name":name,"photo":photo})
        return {"players":out,"source":"CSI Milano"}
    except:return {"players":[]}

@app.get("/api/image")
def proxy_image(url:str=Query(...)):
    if not (url.startswith(CSI_OLD) or url.startswith(CSI_LIVE)):raise HTTPException(400)
    r=requests.get(url,headers=HEADERS,timeout=20);r.raise_for_status()
    return Response(r.content,media_type=r.headers.get("content-type","image/jpeg"))

# ---------- MATCH DETAIL ----------
@app.get("/api/game-detail")
def game_detail(url:str):
    if not url.startswith(CSI_LIVE):raise HTTPException(400,"Link gara non valido")
    s=soup(url);body=clean(s.get_text(" ",strip=True))
    info={"url":url,"title":"","score":"","field":"","events":[]}
    # heading / score
    hs=[clean(x.get_text(" ",strip=True)) for x in s.find_all(["h1","h2","h3","h4","h5"])]
    info["title"]=" · ".join([x for x in hs[:4] if x][:2])
    m=re.search(r"\b(\d+)\s*[-–]\s*(\d+)\b",body)
    if m:info["score"]=m.group(0)
    mf=re.search(r"Campo:\s*([^©]+?)(?:Codice gara:|2025/26|2026/27|Lombardia|$)",body,re.I)
    if mf:info["field"]=clean(mf.group(1))
    # chronology/event-like snippets
    seen=set()
    for el in s.find_all(["li","tr","div"]):
        txt=clean(el.get_text(" ",strip=True))
        if len(txt)>180 or len(txt)<4:continue
        if re.search(r"\b\d{1,2}['’]\b|\bGol\b|\bAmmon|Sostit|Espuls|Timeout|Canestro",txt,re.I):
            if txt not in seen:
                seen.add(txt);info["events"].append(txt)
        if len(info["events"])>=30:break
    return info

# ---------- EVENT DETAIL ----------
@app.get("/api/event/{event_id}")
def event_detail(event_id:str):
    for e in load_json("events.json",[]):
        if e.get("id")==event_id:return e
    raise HTTPException(404)

# ---------- ROUTING / MAP ----------
def geocode(address):
    r=requests.get("https://nominatim.openstreetmap.org/search",params={"q":address,"format":"json","limit":1},headers=HEADERS,timeout=15)
    r.raise_for_status();a=r.json()
    if not a:return None
    return float(a[0]["lat"]),float(a[0]["lon"])

@app.get("/api/route")
def route(address:str):
    hub=load_json("hub.json",{});origin=hub.get("stadium",{}).get("address","Via della Cooperazione, 20089 Rozzano MI")
    a=geocode(origin);b=geocode(address)
    if not a or not b:raise HTTPException(404,"Indirizzo non localizzato")
    lat1,lon1=a;lat2,lon2=b
    u=f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    r=requests.get(u,params={"overview":"false"},headers=HEADERS,timeout=15);r.raise_for_status();data=r.json()
    rr=data.get("routes",[{}])[0]
    return {"origin":{"lat":lat1,"lon":lon1},"destination":{"lat":lat2,"lon":lon2},"km":round(rr.get("distance",0)/1000,1),"minutes":round(rr.get("duration",0)/60),"address":address}
