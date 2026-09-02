
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import date, timedelta
import requests, re, json
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
app = FastAPI(title="USSA SMART HUB")
TEAMS = {x["key"]: x for x in json.loads((ROOT/"teams.json").read_text(encoding="utf-8"))}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (USSA SMART HUB; browser kiosk)",
    "Accept-Language": "it-IT,it;q=0.9",
}

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def txt(el):
    return " ".join(el.stripped_strings) if el else ""

@app.get("/")
def home():
    return FileResponse(ROOT/"index.html")

@app.get("/api/upcoming")
def upcoming():
    today = date.today()
    end = today + timedelta(days=30)
    url = (
        "https://www.csi.milano.it/partite-del-giorno.html"
        f"?societa=USSA+ROZZANO&sport=&data={today.isoformat()}&data_a={end.isoformat()}&filtro_sub=Filtra"
    )
    soup = BeautifulSoup(get(url), "html.parser")
    rows = []
    # Parser volutamente tollerante: il CSI può modificare classi CSS.
    for tr in soup.find_all("tr"):
        cells = [txt(td) for td in tr.find_all(["td","th"])]
        line = " | ".join(cells)
        if "USSA ROZZANO" not in line.upper():
            continue
        # conserva i dati grezzi se la struttura cambia
        rows.append({"raw": cells})
    # Normalizzazione euristica sulle tabelle CSI
    out=[]
    for item in rows:
        c=item["raw"]
        if len(c) < 4: 
            continue
        whole=" ".join(c)
        mdate=re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", whole)
        mtime=re.search(r"\b([0-2]?\d:[0-5]\d)\b", whole)
        teams=[x for x in c if "USSA ROZZANO" in x.upper()]
        out.append({
            "day_label": mdate.group(1) if mdate else "",
            "time": mtime.group(1) if mtime else "",
            "category": c[0] if c else "GARA CSI",
            "home": c[-3] if len(c)>=3 else "",
            "away": c[-2] if len(c)>=2 else "",
            "venue": next((x for x in c if "VIA " in x.upper() or "STADIUM" in x.upper() or "PALESTRA" in x.upper()), "")
        })
    return out

def team_url(team, view):
    base = team.get("url")
    if not base:
        raise HTTPException(503, "URL CSI della competizione non ancora registrato")
    sep = "&" if "?" in base else "?"
    return base.split("?")[0] + f"?v={view}"

@app.get("/api/team/{key}/summary")
def team_summary(key: str):
    team = TEAMS.get(key)
    if not team: raise HTTPException(404, "Squadra non trovata")
    soup = BeautifulSoup(get(team_url(team,"squadra")), "html.parser")
    page = txt(soup)
    # Estrae le statistiche pubbliche dal testo CSI.
    labels = ["POSIZIONE ATTUALE","VITTORIE","PAREGGI","SCONFITTE","Goal fatti","Goal subiti"]
    result={"team":team["label"],"sport":team["sport"],"source":"CSI Milano"}
    for lab in labels:
        m=re.search(re.escape(lab)+r"\s*[:|]?\s*(\d+)", page, re.I)
        if m: result[lab]=int(m.group(1))
    return result

@app.get("/api/team/{key}/matches")
def team_matches(key: str):
    team = TEAMS.get(key)
    if not team: raise HTTPException(404, "Squadra non trovata")
    soup = BeautifulSoup(get(team_url(team,"partite")), "html.parser")
    out=[]
    for tr in soup.find_all("tr"):
        cells=[txt(td) for td in tr.find_all("td")]
        joined=" ".join(cells)
        if "USSA ROZZANO" not in joined.upper(): 
            continue
        out.append({"cells":cells})
    return {"team":team["label"],"matches":out,"source":"CSI Milano"}

@app.get("/api/team/{key}/players")
def team_players(key: str):
    team = TEAMS.get(key)
    if not team: raise HTTPException(404, "Squadra non trovata")
    if not team.get("marcatori"):
        return {"team":team["label"],"players":[],"available":False,"source":"CSI Milano"}
    soup = BeautifulSoup(get(team_url(team,"giocatori")), "html.parser")
    players=[]
    # Raccoglie i link atleta presenti nella rosa e apre le pagine individuali
    # per leggere il campo "Goals", evitando di inventare graduatorie.
    links=[]
    for a in soup.find_all("a", href=True):
        href=a["href"]
        if "/albo/giocatori/" in href:
            if href.startswith("/"): href="https://www.csi.milano.it"+href
            links.append((txt(a),href))
    seen=set()
    for name,href in links:
        if href in seen: continue
        seen.add(href)
        try:
            p=BeautifulSoup(get(href),"html.parser")
            body=txt(p)
            mg=re.search(r"Goals\s*:\s*(\d+)", body, re.I)
            if mg:
                goals=int(mg.group(1))
                if goals>0:
                    h1=p.find("h1")
                    pname=txt(h1) or name
                    players.append({"name":pname,"goals":goals})
        except Exception:
            pass
    players.sort(key=lambda x:(-x["goals"],x["name"]))
    return {"team":team["label"],"players":players,"available":True,"source":"CSI Milano"}
