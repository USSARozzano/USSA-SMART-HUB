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
H={"User-Agent":"Mozilla/5.0 (USSA SMART HUB; +https://www.ussarozzano.it)","Accept-Language":"it-IT,it;q=0.9"}
CACHE={}

def fetch(u):
 r=requests.get(u,headers=H,timeout=25); r.raise_for_status(); return r.text
def sp(u): return BeautifulSoup(fetch(u),"html.parser")
def cl(x): return re.sub(r"\s+"," ",x or "").strip()
def baseurl(u): return u.split("?")[0]

def resolve(t):
 if t.get("url"): return baseurl(t["url"])
 if t["key"] in CACHE: return CACHE[t["key"]]
 seed=t.get("seed")
 if not seed: raise HTTPException(404,"Scheda Primaverile CSI non identificata con certezza")
 s=sp(seed); wanted=cl(t.get("match_text","USSA ROZZANO")).upper()
 candidates=[]
 for a in s.find_all("a",href=True):
  href=urljoin(BASE,a["href"]); text=cl(a.get_text(" ",strip=True)).upper()
  if "/albo/squadre/" in href and "USSA ROZZANO" in text:
   candidates.append((text,baseurl(href)))
 # Exact descriptive link first; otherwise verify candidate page title contains PRIMAV.
 for text,u in candidates:
  if wanted==text:
   CACHE[t["key"]]=u; return u
 for text,u in candidates:
  try:
   title=cl(sp(u).get_text(" ",strip=True)).upper()
   if "PRIMAV" in title:
    CACHE[t["key"]]=u; return u
  except: pass
 raise HTTPException(404,"Scheda Primaverile CSI non identificata con certezza")

def view(t,v): return resolve(t)+"?v="+v

@app.get("/")
def home(): return FileResponse(ROOT/"index.html")

def stat(u):
 s=sp(u); body=cl(s.get_text(" ",strip=True)); d={}
 pats={"position":r"POSIZIONE ATTUALE\s*(\d+)","wins":r"VITTORIE\s*(\d+)",
       "draws":r"PAREGGI\s*(\d+)","losses":r"SCONFITTE\s*(\d+)"}
 for k,p in pats.items():
  m=re.search(p,body,re.I)
  if m:d[k]=int(m.group(1))
 if "wins" in d and "losses" in d:
  d["played"]=d["wins"]+d.get("draws",0)+d["losses"]
  d["points"]=d["wins"]*3+d.get("draws",0)
 # crest: image near main team heading; return through proxy
 for img in s.find_all("img",src=True):
  src=urljoin(BASE,img["src"]); alt=cl(img.get("alt","")).upper()
  if "USSA" in alt or "/squadre/" in src or "logo" in src.lower():
   d["logo"]=src; break
 return d

@app.get("/api/logo")
def logo(url:str):
 if not url.startswith(BASE): raise HTTPException(400)
 r=requests.get(url,headers=H,timeout=20); r.raise_for_status()
 return Response(r.content,media_type=r.headers.get("content-type","image/png"))

def match_rows(t):
 s=sp(view(t,"partite")); out=[]
 for tr in s.find_all("tr"):
  cells=[cl(x.get_text(" ",strip=True)) for x in tr.find_all("td")]
  if "USSA ROZZANO" not in " ".join(cells).upper(): continue
  md=re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b"," ".join(cells))
  mt=re.search(r"\b[0-2]?\d:[0-5]\d\b"," ".join(cells))
  score=re.search(r"\b\d+\s*-\s*\d+(?:\s*(?:DTR|DTS|V\.D\.|\*))?"," ".join(cells),re.I)
  links=[]
  for a in tr.find_all("a",href=True):
   if "/albo/squadre/" in a["href"]:
    nm=cl(a.get_text(" ",strip=True))
    if nm and nm not in [x[0] for x in links]: links.append((nm,urljoin(BASE,a["href"])))
  home=links[0][0] if len(links)>0 else ""
  away=links[1][0] if len(links)>1 else ""
  field=""
  for c in cells:
   if any(z in c.upper() for z in ["VIA ","COMUNALE","ORATORIO","PALESTRA","SCUOLA ","CENTRO "]):
    field=c; break
  info=""
  for a in tr.find_all("a",href=True):
   if "/albo/partite/" in a["href"]: info=urljoin(BASE,a["href"]); break
  out.append({"date":md.group(0) if md else "","time":mt.group(0) if mt else "",
              "home":home,"away":away,"result":score.group(0) if score else "",
              "field":field,"info":info})
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
 today=datetime.now().date(); a=[]
 for m in match_rows(t):
  try:d=datetime.strptime(m["date"],"%d/%m/%Y").date()
  except:continue
  if d>=today and not m["result"]:a.append(m)
 return {"team":t["label"],"matches":a}

@app.get("/api/team/{key}/standings")
def standings(key:str):
 t=TEAMS.get(key)
 if not t: raise HTTPException(404)
 if not t.get("classifica"):return {"available":False,"standings":[]}
 # Every opponent in the team's official CSI fixture list belongs to the group.
 s=sp(view(t,"partite")); links={}
 for a in s.find_all("a",href=True):
  if "/albo/squadre/" in a["href"]:
   nm=cl(a.get_text(" ",strip=True)); u=baseurl(urljoin(BASE,a["href"]))
   if nm:links[u]=nm
 links[resolve(t)]=("USSA ROZZANO "+t["label"]).strip()
 rows=[]
 for u,nm in links.items():
  try:
   d=stat(u+"?v=squadra")
   if "position" in d:
    d["team"]=nm; rows.append(d)
  except:pass
 rows.sort(key=lambda x:x.get("position",999))
 return {"available":True,"standings":rows,"source":view(t,"squadra")}

@app.get("/api/team/{key}/players")
def players(key:str):
 t=TEAMS.get(key)
 if not t: raise HTTPException(404)
 if not t.get("marcatori"):return {"available":False,"players":[]}
 # CSI player pages expose cumulative Goals; this is more reliable than summing match reports.
 s=sp(view(t,"giocatori")); urls={}
 for a in s.find_all("a",href=True):
  if "/albo/giocatori/" in a["href"]: urls[urljoin(BASE,a["href"])]=cl(a.get_text(" ",strip=True))
 arr=[]
 for u,fallback in urls.items():
  try:
   ps=sp(u); body=cl(ps.get_text(" ",strip=True))
   m=re.search(r"Goals\s*:?\s*(\d+)",body,re.I)
   if not m:continue
   g=int(m.group(1))
   if g<=0:continue
   h=ps.find("h1"); name=cl(h.get_text(" ",strip=True)) if h else fallback
   arr.append({"name":name,"goals":g})
  except:pass
 arr.sort(key=lambda x:(-x["goals"],x["name"]))
 return {"available":True,"players":arr,"source":view(t,"giocatori")}

@app.get("/api/upcoming")
def upcoming():
 a=date.today(); b=a+timedelta(days=30)
 u=f"{BASE}/partite-del-giorno.html?societa=USSA+ROZZANO&sport=&data={a.isoformat()}&data_a={b.isoformat()}&filtro_sub=Filtra"
 s=sp(u); rows=[]
 for tr in s.find_all("tr"):
  cells=[cl(x.get_text(" ",strip=True)) for x in tr.find_all("td")]
  if "USSA ROZZANO" not in " ".join(cells).upper():continue
  rows.append({"cells":cells})
 return {"source":u,"games":rows}

@app.get("/api/status")
def status():
 out={}
 for k,t in TEAMS.items():
  try: out[k]={"ok":True,"url":resolve(t)}
  except Exception as e: out[k]={"ok":False,"error":"non identificata"}
 return out
