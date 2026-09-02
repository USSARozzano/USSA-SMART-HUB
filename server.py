from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path
from datetime import date,timedelta,datetime
from urllib.parse import urljoin
import requests,re,json
from bs4 import BeautifulSoup

ROOT=Path(__file__).parent
app=FastAPI(title="USSA SMART HUB")
TEAMS={x["key"]:x for x in json.loads((ROOT/"teams.json").read_text(encoding="utf-8"))}
BASE="https://www.csi.milano.it"
H={"User-Agent":"Mozilla/5.0 (USSA SMART HUB)","Accept-Language":"it-IT,it;q=0.9"}
CACHE={}

def fetch(u):
    r=requests.get(u,headers=H,timeout=25)
    r.raise_for_status()
    return r.text

def sp(u): return BeautifulSoup(fetch(u),"html.parser")
def cl(x): return re.sub(r"\s+"," ",x or "").strip()
def baseurl(u): return u.split("?")[0]

def page_title(u):
    s=sp(u)
    h1=s.find("h1")
    return cl(h1.get_text(" ",strip=True)) if h1 else cl(s.title.get_text(" ",strip=True) if s.title else "")

def resolve(t):
    if t.get("url"):
        return baseurl(t["url"])
    if t["key"] in CACHE:
        return CACHE[t["key"]]
    seed=t.get("seed")
    if not seed:
        raise HTTPException(404,"Scheda CSI non ancora identificata")
    s=sp(seed)
    wanted=cl(t.get("match_text","USSA ROZZANO")).upper()
    candidates=[]
    for a in s.find_all("a",href=True):
        href=urljoin(BASE,a["href"])
        text=cl(a.get_text(" ",strip=True))
        if "/albo/squadre/" in href and "USSA ROZZANO" in text.upper():
            candidates.append((text.upper(),baseurl(href)))
    for text,u in candidates:
        if wanted == text:
            CACHE[t["key"]]=u
            return u
    # Prefer a USSA candidate whose page is explicitly PRIMAV.
    for text,u in candidates:
        try:
            if "PRIMAV" in page_title(u).upper():
                CACHE[t["key"]]=u
                return u
        except:
            pass
    # For categories without standings (small children), a plain USSA team page is still
    # useful for Results/Next if the seed itself is known to be the correct Primaverile group.
    if candidates:
        CACHE[t["key"]]=candidates[0][1]
        return candidates[0][1]
    raise HTTPException(404,"Scheda CSI non identificata")

def view(t,v): return resolve(t)+"?v="+v

@app.get("/")
def home():
    return FileResponse(ROOT/"index.html")

def extract_stats(u):
    """
    CSI does NOT print the values immediately after 'POSIZIONE ATTUALE':
    it prints the whole header row first, then the values row.
    The previous parser therefore returned an empty object.
    This version reads the actual table structure.
    """
    s=sp(u)
    d={}
    for table in s.find_all("table"):
        rows=table.find_all("tr")
        if len(rows) < 2:
            continue
        headers=[cl(x.get_text(" ",strip=True)).upper() for x in rows[0].find_all(["th","td"])]
        if not any("POSIZIONE ATTUALE" in x for x in headers):
            continue
        vals=[cl(x.get_text(" ",strip=True)) for x in rows[1].find_all(["th","td"])]
        if len(vals) < 3:
            continue
        mapping={}
        for i,h in enumerate(headers):
            if i >= len(vals): break
            mapping[h]=vals[i]
        def num_for(keys):
            for h,v in mapping.items():
                if any(k in h for k in keys):
                    m=re.search(r"-?\d+",v)
                    if m: return int(m.group())
            return None
        pos=num_for(["POSIZIONE"])
        wins=num_for(["VITTORIE"])
        draws=num_for(["PAREGGI"])
        losses=num_for(["SCONFITTE"])
        gf=num_for(["GOAL FATTI","GOL FATTI","CANESTRI FATTI"])
        ga=num_for(["GOAL SUBITI","GOL SUBITI","CANESTRI SUBITI"])
        if pos is not None: d["position"]=pos
        if wins is not None: d["wins"]=wins
        if draws is not None: d["draws"]=draws
        if losses is not None: d["losses"]=losses
        if gf is not None: d["gf"]=gf
        if ga is not None: d["ga"]=ga
        break

    # Fallback for pages rendered without a semantic <table>.
    if "position" not in d:
        body=cl(s.get_text(" ",strip=True))
        m=re.search(
            r"POSIZIONE ATTUALE\s+VITTORIE(?:\s+PAREGGI)?\s+SCONFITTE(?:\s+Goal fatti\s+Goal subiti)?\s+"
            r"(\d+)\s+(\d+)(?:\s+(\d+))?\s+(\d+)(?:\s+(\d+)\s+(\d+))?",
            body,re.I
        )
        if m:
            d["position"]=int(m.group(1))
            d["wins"]=int(m.group(2))
            if m.group(3) is not None: d["draws"]=int(m.group(3))
            d["losses"]=int(m.group(4))
            if m.group(5) is not None: d["gf"]=int(m.group(5))
            if m.group(6) is not None: d["ga"]=int(m.group(6))

    if "wins" in d and "losses" in d:
        d["played"]=d["wins"]+d.get("draws",0)+d["losses"]

    # Team crest/photo actually exposed by CSI with the team name as alt.
    h1=s.find("h1")
    team_name=cl(h1.get_text(" ",strip=True)).split(" (")[0] if h1 else ""
    imgs=[]
    for img in s.find_all("img",src=True):
        src=urljoin(BASE,img["src"])
        alt=cl(img.get("alt",""))
        if team_name and team_name.upper() in alt.upper():
            d["logo"]=src
            break
        if "apple" not in src.lower() and "google" not in src.lower() and "csi" not in alt.lower():
            imgs.append(src)
    if "logo" not in d and imgs:
        # Best-effort fallback; if CSI has no crest/photo, UI simply leaves logo blank.
        d["logo"]=imgs[0]
    return d

def parse_score(text):
    m=re.search(r"\b(\d+)\s*-\s*(\d+)\b",text or "")
    return (int(m.group(1)),int(m.group(2))) if m else None

def team_points(team_url,sport,stats):
    # Soccer CSI: 3 for win, 1 for draw.
    if sport.startswith("CALCIO"):
        return stats.get("wins",0)*3 + stats.get("draws",0)
    # Basketball: 2 points for a win in the standings.
    if sport=="BASKET":
        return stats.get("wins",0)*2
    # Volleyball: calculate official match points from set scores.
    if sport=="VOLLEY":
        try:
            s=sp(team_url+"?v=partite")
            total=0
            own_name=page_title(team_url).split(" (")[0].upper()
            for tr in s.find_all("tr"):
                links=[]
                for a in tr.find_all("a",href=True):
                    if "/albo/squadre/" in a["href"]:
                        nm=cl(a.get_text(" ",strip=True))
                        if nm and nm not in links:
                            links.append(nm)
                if len(links)<2:
                    continue
                cells=" ".join(cl(td.get_text(" ",strip=True)) for td in tr.find_all("td"))
                sc=parse_score(cells)
                if not sc: continue
                home,away=links[0],links[1]
                hs,as_=sc
                if own_name not in (home.upper(),away.upper()):
                    continue
                own=hs if own_name==home.upper() else as_
                opp=as_ if own_name==home.upper() else hs
                if own>opp:
                    total += 2 if (own,opp)==(3,2) else 3
                else:
                    total += 1 if (own,opp)==(2,3) else 0
            return total
        except:
            return None
    return None

@app.get("/api/logo")
def logo(url:str):
    if not url.startswith(BASE):
        raise HTTPException(400)
    r=requests.get(url,headers=H,timeout=20)
    r.raise_for_status()
    return Response(r.content,media_type=r.headers.get("content-type","image/png"))

def match_rows(t):
    s=sp(view(t,"partite"))
    out=[]
    for tr in s.find_all("tr"):
        cells=[cl(x.get_text(" ",strip=True)) for x in tr.find_all("td")]
        line=" ".join(cells)
        if "USSA ROZZANO" not in line.upper():
            continue
        md=re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b",line)
        mt=re.search(r"\b[0-2]?\d:[0-5]\d\b",line)
        score=re.search(r"\b\d+\s*-\s*\d+(?:\s*(?:V\.D\.|DTR|DTS|\*))?",line,re.I)
        links=[]
        for a in tr.find_all("a",href=True):
            if "/albo/squadre/" in a["href"]:
                nm=cl(a.get_text(" ",strip=True))
                if nm and nm not in [x[0] for x in links]:
                    links.append((nm,urljoin(BASE,a["href"])))
        home=links[0][0] if len(links)>0 else ""
        away=links[1][0] if len(links)>1 else ""
        field=""
        for c in cells:
            if any(z in c.upper() for z in ["VIA ","COMUNALE","ORATORIO","PALESTRA","SCUOLA ","CENTRO "]):
                field=c
                break
        out.append({
            "date":md.group(0) if md else "",
            "time":mt.group(0) if mt else "",
            "home":home,
            "away":away,
            "result":score.group(0) if score else "",
            "field":field
        })
    return out

@app.get("/api/team/{key}/matches")
def matches(key:str):
    t=TEAMS.get(key)
    if not t: raise HTTPException(404)
    return {"team":t["label"],"source":view(t,"partite"),"matches":match_rows(t)}

@app.get("/api/team/{key}/next")
def nxt(key:str):
    t=TEAMS.get(key)
    if not t: raise HTTPException(404)
    today=datetime.now().date()
    arr=[]
    for m in match_rows(t):
        try: d=datetime.strptime(m["date"],"%d/%m/%Y").date()
        except: continue
        if d>=today and not m["result"]:
            arr.append(m)
    return {"team":t["label"],"matches":arr}

@app.get("/api/team/{key}/standings")
def standings(key:str):
    t=TEAMS.get(key)
    if not t: raise HTTPException(404)
    if not t.get("classifica"):
        return {"available":False,"standings":[]}
    own=resolve(t)
    s=sp(view(t,"partite"))

    # Every team link in the official fixture list belongs to the same CSI group.
    links={}
    for a in s.find_all("a",href=True):
        if "/albo/squadre/" in a["href"]:
            nm=cl(a.get_text(" ",strip=True))
            u=baseurl(urljoin(BASE,a["href"]))
            if nm:
                links[u]=nm
    links[own]="USSA ROZZANO"

    rows=[]
    for u,nm in links.items():
        try:
            d=extract_stats(u+"?v=squadra")
            if "position" not in d:
                continue
            d["team"]=nm
            pts=team_points(u,t["sport"],d)
            if pts is not None:
                d["points"]=pts
            rows.append(d)
        except:
            pass

    rows.sort(key=lambda x:x.get("position",999))
    return {
        "available":True,
        "standings":rows,
        "source":view(t,"squadra")
    }

@app.get("/api/team/{key}/players")
def players(key:str):
    t=TEAMS.get(key)
    if not t: raise HTTPException(404)
    if not t.get("marcatori"):
        return {"available":False,"players":[]}
    s=sp(view(t,"giocatori"))
    urls={}
    for a in s.find_all("a",href=True):
        if "/albo/giocatori/" in a["href"]:
            urls[urljoin(BASE,a["href"])]=cl(a.get_text(" ",strip=True))
    arr=[]
    for u,fallback in urls.items():
        try:
            ps=sp(u)
            body=cl(ps.get_text(" ",strip=True))
            m=re.search(r"Goals\s*:?\s*(\d+)",body,re.I)
            if not m: continue
            g=int(m.group(1))
            if g<=0: continue
            h1=ps.find("h1")
            name=cl(h1.get_text(" ",strip=True)) if h1 else fallback
            arr.append({"name":name,"goals":g})
        except:
            pass
    arr.sort(key=lambda x:(-x["goals"],x["name"]))
    return {"available":True,"players":arr,"source":view(t,"giocatori")}

@app.get("/api/upcoming")
def upcoming():
    a=date.today()
    b=a+timedelta(days=30)
    u=f"{BASE}/partite-del-giorno.html?societa=USSA+ROZZANO&sport=&data={a.isoformat()}&data_a={b.isoformat()}&filtro_sub=Filtra"
    s=sp(u)
    rows=[]
    for tr in s.find_all("tr"):
        cells=[cl(x.get_text(" ",strip=True)) for x in tr.find_all("td")]
        if "USSA ROZZANO" not in " ".join(cells).upper():
            continue
        rows.append({"cells":cells})
    return {"source":u,"games":rows}

@app.get("/api/status")
def status():
    out={}
    for k,t in TEAMS.items():
        try:
            out[k]={"ok":True,"url":resolve(t)}
        except:
            out[k]={"ok":False}
    return out
