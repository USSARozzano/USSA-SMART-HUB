import math
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, PlainTextResponse
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote, urlparse
import requests, re, json, io
from bs4 import BeautifulSoup
import qrcode
import qrcode.image.svg

ROOT=Path(__file__).parent
app=FastAPI(title="USSA SMART HUB V2")
CSI_OLD="https://www.csi.milano.it"
CSI_LIVE="https://live.centrosportivoitaliano.it"
HEADERS={"User-Agent":"USSA-SMART-HUB/2.1","Accept-Language":"it-IT,it;q=0.9"}

U13_TEST_STANDINGS=[
 {"position":1,"team":"S.Giuliano Cologno Osgd","points":18,"played":8,"wins":6,"draws":0,"losses":2},
 {"position":2,"team":"Ussa Rozzano","points":17,"played":8,"wins":5,"draws":2,"losses":1},
 {"position":3,"team":"Polisportiva Omr","points":15,"played":8,"wins":5,"draws":0,"losses":3},
 {"position":4,"team":"Usom Calcio","points":15,"played":8,"wins":4,"draws":3,"losses":1},
 {"position":5,"team":"S.Fermo","points":13,"played":8,"wins":4,"draws":1,"losses":3},
 {"position":6,"team":"Osm Assago","points":11,"played":8,"wins":3,"draws":2,"losses":3},
 {"position":7,"team":"Sporting C.B. Scb","points":9,"played":8,"wins":3,"draws":0,"losses":5},
 {"position":8,"team":"Osv Milano 2013 Orange","points":6,"played":8,"wins":2,"draws":0,"losses":6},
 {"position":9,"team":"Aso Cernusco 2013 Blu","points":0,"played":8,"wins":0,"draws":0,"losses":8}
]
U13_TEST_SCORERS=[
 {"name":"DI TOMA SAMUELE","goals":4},{"name":"LAURORA TOMMASO","goals":3},
 {"name":"LIVRIERI ALESSIO","goals":2},{"name":"BRAMBILLA SAMUELE WALTER","goals":2},
 {"name":"DE GREGORIO FRANCESCO","goals":2},{"name":"FALAPPA LEONARDO","goals":2},
 {"name":"PAGANELLO CHRISTIAN","goals":1}
]

def load_json(name, default):
    try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
    except:return default

def teams_dict(): return {x['key']:x for x in load_json('teams.json',[])}
def fixtures(): return load_json('fixtures.json',[])
def clean(s): return re.sub(r"\s+"," ",s or "").strip()
def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=20);r.raise_for_status();return r.text
def soup(url): return BeautifulSoup(fetch(url),'html.parser')
def iso_dt(d,t='00:00'): return datetime.fromisoformat(f"{d}T{t or '00:00'}")
def parse_hm(v): h,m=map(int,v.split(':'));return h*60+m

def fixture_by_id(fid):
    return next((x for x in fixtures() if x.get('id')==fid),None)

def local_fixture_matches(team_key, competition=None):
    a=[x for x in fixtures() if x.get('team_key')==team_key and (not competition or x.get('competition')==competition)]
    return sorted(a,key=lambda x:(x.get('date',''),x.get('time','')))

@app.get('/')
def home(): return FileResponse(ROOT/'index.html')
@app.get('/assets/ussa-logo.png')
def logo(): return FileResponse(ROOT/'ussa-logo.png',media_type='image/png')
@app.get('/api/teams')
def api_teams(): return load_json('teams.json',[])
@app.get('/api/hub')
def api_hub(): return load_json('hub.json',{})

@app.get('/api/home/now')
def home_now():
    td=teams_dict();now=datetime.now();wd=now.isoweekday();minute=now.hour*60+now.minute;items=[]
    for t in td.values():
        if t.get('visible') is False: continue
        for x in t.get('training',[]):
            try:
                if int(x.get('weekday',0))==wd and parse_hm(x['start'])<=minute<parse_hm(x['end']):
                    items.append({'kind':'ALLENAMENTO','team_key':t['key'],'title':t['label'],'meta':f"{x['start']}–{x['end']}",'place':x.get('place','')})
            except: pass
    for x in fixtures():
        try:
            dt=iso_dt(x['date'],x['time'])
            if 0 <= (now-dt).total_seconds() < 120*60:
                items.append({'kind':'PARTITA','team_key':x['team_key'],'title':teams_dict().get(x['team_key'],{}).get('label','PARTITA'),'meta':f"{x['home']} – {x['away']}",'place':x.get('field','')})
        except: pass
    return {'items':items}

def live_schedule_for_team(t):
    url=t.get('csi_live_url')
    if not url:return []
    s=soup(url);out=[];seen=set()
    for tr in s.find_all('tr'):
        txt=clean(tr.get_text(' ',strip=True))
        if 'USSA ROZZANO' not in txt.upper():continue
        md=re.search(r'\b(\d{2}/\d{2}/\d{2})\b',txt);mt=re.search(r'\b([0-2]\d:[0-5]\d)\b',txt)
        if not md:continue
        links=tr.find_all('a',href=True);game_url=''
        for a in links:
            href=urljoin(url,a['href'])
            if '/P20' in urlparse(href).path: game_url=href;break
        cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['td','th'])]
        names=[]
        for c in cells:
            if not c or re.fullmatch(r'\d{2}/\d{2}/\d{2}',c) or re.fullmatch(r'[0-2]\d:[0-5]\d',c):continue
            if c.upper() in {'ANDATA','RITORNO'}:continue
            if re.fullmatch(r'\d+',c):continue
            names.append(c)
        try:dt=datetime.strptime(md.group(1)+(mt.group(1) if mt else '00:00'),'%d/%m/%y%H:%M')
        except:continue
        # score is intentionally conservative: only a clear x-y token
        sm=re.search(r'\b(\d+)\s*[-–]\s*(\d+)\b',txt)
        key=(dt.isoformat(),txt)
        if key in seen:continue
        seen.add(key)
        out.append({'date':dt.date().isoformat(),'time':mt.group(1) if mt else '', 'raw':txt,'names':names,
                    'result':sm.group(0) if sm else '', 'detail_url':game_url,'team_key':t['key'],'competition':'CSI'})
    return out

def live_standings(t):
    if not t.get('csi_live_url'):return []
    s=soup(t['csi_live_url'])
    for table in s.find_all('table'):
        rows=table.find_all('tr')
        if not rows:continue
        hdr=[clean(x.get_text(' ',strip=True)).upper() for x in rows[0].find_all(['th','td'])]
        if not ('SQUADRA' in ' '.join(hdr) and 'PT' in hdr):continue
        result=[]
        for tr in rows[1:]:
            vals=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
            try:
                result.append({'position':int(vals[0]),'team':vals[1],'points':int(vals[2]),'played':int(vals[3]),
                               'wins':int(vals[4]) if len(vals)>4 and vals[4].isdigit() else None,
                               'draws':int(vals[5]) if len(vals)>5 and vals[5].isdigit() else None,
                               'losses':int(vals[6]) if len(vals)>6 and vals[6].isdigit() else None})
            except:continue
        if result:return result
    return []

def live_scorers(t):
    if not t.get('csi_live_url'):return []
    out=[]
    try:
        s=soup(t['csi_live_url'])
        for table in s.find_all('table'):
            rows=table.find_all('tr');
            if not rows:continue
            hdr=' '.join(clean(x.get_text(' ',strip=True)).upper() for x in rows[0].find_all(['th','td']))
            if not (('GOL' in hdr or 'RETI' in hdr) and ('GIOCAT' in hdr or 'ATLETA' in hdr)):continue
            for tr in rows[1:]:
                vals=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
                line=' | '.join(vals)
                if 'USSA' not in line.upper():continue
                goal=next((int(v) for v in reversed(vals) if re.fullmatch(r'\d+',v)),0)
                name=next((v for v in vals if re.search(r'[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]{2,}',v) and 'USSA' not in v.upper()),'')
                if name and goal:out.append({'name':name,'goals':goal})
            if out:break
    except:pass
    out.sort(key=lambda x:(-x['goals'],x['name']))
    return out

def old_csi_scorers(t):
    url=t.get('csi_old_url')
    if not url:return []
    out=[]
    try:
        s=soup(url.split('?')[0]+'?v=giocatori')
        for tr in s.find_all('tr'):
            vals=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['td','th'])]
            if len(vals)<2:continue
            m=re.search(r'\b(\d+)\s*$', ' '.join(vals))
            if not m or int(m.group(1))<=0:continue
            name=' '.join(vals[:-1]).strip()
            if name:out.append({'name':name,'goals':int(m.group(1))})
    except:pass
    out.sort(key=lambda x:(-x['goals'],x['name']))
    return out

def team_standings_data(t, competition):
    if competition!='CSI': return []
    rows=[]
    try:rows=live_standings(t)
    except:pass
    if t.get('key')=='u13a11_test' and not rows:rows=U13_TEST_STANDINGS
    return rows

def team_scorers_data(t, competition):
    if competition!='CSI': return []
    rows=live_scorers(t) or old_csi_scorers(t)
    if t.get('key')=='u13a11_test' and not rows:rows=U13_TEST_SCORERS
    return rows

def team_matches_data(t, competition):
    now=datetime.now()
    if competition=='FIGC':
        arr=local_fixture_matches(t['key'],'FIGC')
        played=[x for x in arr if iso_dt(x['date'],x['time'])<now]
        nexts=[x for x in arr if iso_dt(x['date'],x['time'])>=now]
        return played,nexts
    if competition=='CSI' and t.get('csi_live_url'):
        try:arr=live_schedule_for_team(t)
        except:arr=[]
        played=[];nexts=[]
        for x in arr:
            try:dt=iso_dt(x['date'],x.get('time','00:00'))
            except:continue
            if x.get('result') or dt<now:played.append(x)
            else:nexts.append(x)
        return played,nexts
    return [],[]

@app.get('/api/home/upcoming')
def home_upcoming():
    now=datetime.now();items=[]
    # Single local source for real FIGC fixtures.
    for x in fixtures():
        try:
            dt=iso_dt(x['date'],x['time'])
            if dt>=now:
                t=teams_dict().get(x['team_key'],{})
                items.append({**x,'kind':'PARTITA','title':f"{x['home']} – {x['away']}",'meta':t.get('label',''),'sport':t.get('sport',''),'icon':t.get('icon',''),'_sort':dt.isoformat(),'source':'USSA/FIGC'})
        except:pass
    # Manual USSA events only; no training.
    for e in load_json('events.json',[]):
        try:
            dt=iso_dt(e['date'],e.get('time','00:00'))
            if dt>=now:items.append({**e,'_sort':dt.isoformat(),'source':'USSA'})
        except:pass
    # Live CSI future fixtures automatically appear once mapped/published.
    for t in teams_dict().values():
        if t.get('visible') is False or not t.get('csi_live_url') or t.get('test_only'):continue
        try:
            for m in live_schedule_for_team(t):
                dt=iso_dt(m['date'],m.get('time','00:00'))
                if dt<now or m.get('result'):continue
                title=' – '.join(m.get('names',[])[-2:]) if m.get('names') else 'Partita USSA'
                items.append({**m,'kind':'PARTITA','title':title,'meta':t['label'],'sport':t.get('sport',''),'icon':t.get('icon',''),'_sort':dt.isoformat(),'source':'CSI LIVE'})
        except:pass
    items.sort(key=lambda x:x['_sort'])
    for x in items:x.pop('_sort',None)
    return {'items':items[:100]}

@app.get('/api/team/{key}/availability')
def availability(key:str, competition:str='CSI'):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    standings=team_standings_data(t,competition)
    scorers=team_scorers_data(t,competition)
    played,nexts=team_matches_data(t,competition)
    return {'staff':bool(t.get('staff')),'standings':bool(standings),'scorers':bool(scorers),'played':bool(played),'next':bool(nexts),
            'competition':competition}

@app.get('/api/team/{key}/standings')
def standings(key:str, competition:str='CSI'):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    rows=team_standings_data(t,competition)
    return {'available':bool(rows),'standings':rows,'source':'CSI LIVE' if competition=='CSI' else competition}

@app.get('/api/team/{key}/players')
def players(key:str, competition:str='CSI'):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    rows=team_scorers_data(t,competition)
    return {'available':bool(rows),'players':rows,'source':'CSI' if competition=='CSI' else competition}

@app.get('/api/team/{key}/matches')
def matches(key:str, competition:str='CSI'):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    played,_=team_matches_data(t,competition)
    return {'matches':played,'source':competition}

@app.get('/api/team/{key}/next')
def next_matches(key:str, competition:str='CSI'):
    t=teams_dict().get(key)
    if not t:raise HTTPException(404)
    _,nexts=team_matches_data(t,competition)
    return {'matches':nexts,'source':competition}

@app.get('/api/fixture/{fixture_id}')
def fixture_detail(fixture_id:str):
    x=fixture_by_id(fixture_id)
    if not x:raise HTTPException(404)
    return x

@app.get('/api/game-detail')
def game_detail(url:str):
    if not url.startswith(CSI_LIVE):raise HTTPException(400,'Link gara non valido')
    s=soup(url);body=clean(s.get_text(' ',strip=True));info={'url':url,'title':'','score':'','field':'','events':[]}
    hs=[clean(x.get_text(' ',strip=True)) for x in s.find_all(['h1','h2','h3','h4','h5'])]
    info['title']=' · '.join([x for x in hs[:4] if x][:2])
    m=re.search(r'\b(\d+)\s*[-–]\s*(\d+)\b',body)
    if m:info['score']=m.group(0)
    mf=re.search(r'Campo:\s*([^©]+?)(?:Codice gara:|2025/26|2026/27|Lombardia|$)',body,re.I)
    if mf:info['field']=clean(mf.group(1))
    seen=set()
    for el in s.find_all(['li','tr','div']):
        txt=clean(el.get_text(' ',strip=True))
        if len(txt)>180 or len(txt)<4:continue
        if re.search(r"\b\d{1,2}['’]\b|\bGol\b|\bAmmon|Sostit|Espuls|Timeout|Canestro",txt,re.I) and txt not in seen:
            seen.add(txt);info['events'].append(txt)
        if len(info['events'])>=30:break
    return info

def geocode(address):
    """Geocoding robusto: Nominatim con query progressive, poi Photon."""
    queries=[]
    raw=str(address or '').strip()
    if raw:
        queries += [raw, raw + ', Lombardia, Italia', raw.replace('USSA Stadium, ', '')]
    seen=set()
    for q in queries:
        if not q or q in seen: continue
        seen.add(q)
        try:
            r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'json','limit':1,'countrycodes':'it','accept-language':'it'},headers=HEADERS,timeout=8)
            r.raise_for_status();a=r.json()
            if a:return (float(a[0]['lat']),float(a[0]['lon']))
        except Exception: pass
    try:
        r=requests.get('https://photon.komoot.io/api/',params={'q':raw,'limit':1,'lang':'it'},headers=HEADERS,timeout=8)
        r.raise_for_status();features=r.json().get('features') or []
        if features:
            lon,lat=features[0]['geometry']['coordinates'];return (float(lat),float(lon))
    except Exception: pass
    return None

def haversine_km(a,b):
    lat1,lon1=a;lat2,lon2=b;R=6371.0
    p1,p2=math.radians(lat1),math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))




def fixture_stats_rows(competition='FIGC'):
    clubs={}
    for f in fixtures():
        if f.get('competition') != competition: continue
        for n in (f.get('home'), f.get('away')):
            if n and n not in clubs:
                clubs[n]={'team':n,'played':0,'wins':0,'draws':0,'losses':0,'gf':0,'ga':0,'points':0,'form':[]}
        # A result can later be stored as "3-1", "3 – 1" or result_home/result_away.
        hg=f.get('result_home'); ag=f.get('result_away')
        if hg is None or ag is None:
            rv=str(f.get('result') or '')
            m=re.search(r'(\d+)\s*[-–]\s*(\d+)',rv)
            if m: hg,ag=int(m.group(1)),int(m.group(2))
        try: hg=int(hg); ag=int(ag)
        except: continue
        h,a=f.get('home'),f.get('away')
        if not h or not a: continue
        H,A=clubs[h],clubs[a]
        H['played']+=1;A['played']+=1;H['gf']+=hg;H['ga']+=ag;A['gf']+=ag;A['ga']+=hg
        if hg>ag:
            H['wins']+=1;A['losses']+=1;H['points']+=3;H['form'].append('V');A['form'].append('P')
        elif hg<ag:
            A['wins']+=1;H['losses']+=1;A['points']+=3;H['form'].append('P');A['form'].append('V')
        else:
            H['draws']+=1;A['draws']+=1;H['points']+=1;A['points']+=1;H['form'].append('N');A['form'].append('N')
    rows=list(clubs.values())
    rows.sort(key=lambda r:(-r['points'],-(r['gf']-r['ga']),-r['gf'],r['team']))
    # Position is meaningful only once at least one result exists.
    any_played=any(r['played'] for r in rows)
    for i,r in enumerate(rows,1):
        r['position']=i if any_played else None
        r['form']=r['form'][-5:]
    return rows

@app.get('/api/fixture/{fixture_id}/stats')
def fixture_stats(fixture_id:str):
    x=fixture_by_id(fixture_id)
    if not x: raise HTTPException(404)
    rows=fixture_stats_rows(x.get('competition','FIGC'))
    d={r['team']:r for r in rows}
    blank=lambda n:{'team':n,'position':None,'played':0,'wins':0,'draws':0,'losses':0,'gf':0,'ga':0,'points':0,'form':[]}
    return {'home':d.get(x.get('home')) or blank(x.get('home')),'away':d.get(x.get('away')) or blank(x.get('away')),'competition':x.get('competition')}

@app.get('/api/static-route/{fixture_id}')
def static_route(fixture_id:str):
    x=fixture_by_id(fixture_id)
    if not x: raise HTTPException(404)
    if x.get('home_away')=='CASA': raise HTTPException(404,'Percorso non necessario')
    routes=load_json('routes.json',{})
    opponent=x.get('home') if 'USSA' in str(x.get('away','')).upper() else x.get('away')
    r=routes.get(opponent)
    if not r or r.get('mode') != 'static_osrm_road_route' or len(r.get('geometry') or []) < 3:
        raise HTTPException(404,'Percorso stradale non predisposto')
    return r

@app.get('/api/geocode')
def geocode_api(address:str):
    p=geocode(address)
    if not p: raise HTTPException(404,'Indirizzo non localizzato')
    return {'lat':p[0],'lon':p[1],'address':address}

@app.get('/api/route')
def route(address:str):
    hub=load_json('hub.json',{});origin=hub.get('stadium',{}).get('route_address') or hub.get('stadium',{}).get('address')
    a=geocode(origin);b=geocode(address)
    if not a or not b:raise HTTPException(404,'Indirizzo non localizzato')
    lat1,lon1=a;lat2,lon2=b
    try:
        u=f'https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}'
        r=requests.get(u,params={'overview':'full','geometries':'geojson'},headers=HEADERS,timeout=10);r.raise_for_status();data=r.json();routes=data.get('routes') or []
        if routes:
            rr=routes[0];km=round(rr.get('distance',0)/1000,1);minutes=max(1,round(rr.get('duration',0)/60))
            return {'origin':{'lat':lat1,'lon':lon1},'destination':{'lat':lat2,'lon':lon2},'km':km,'minutes':minutes,'address':address,'mode':'road','geometry':(rr.get('geometry') or {}).get('coordinates',[])}
    except Exception: pass
    # Fallback indicativo se il router pubblico non risponde: distanza geodetica corretta con fattore stradale.
    km=round(haversine_km(a,b)*1.28,1);minutes=max(1,round(km/32*60))
    return {'origin':{'lat':lat1,'lon':lon1},'destination':{'lat':lat2,'lon':lon2},'km':km,'minutes':minutes,'address':address,'mode':'estimate','geometry':[[lon1,lat1],[lon2,lat2]]}

@app.get('/api/tile/{z}/{x}/{y}.png')
def map_tile(z:int,x:int,y:int):
    if z < 0 or z > 19: raise HTTPException(404)
    try:
        r=requests.get(f'https://tile.openstreetmap.org/{z}/{x}/{y}.png',headers=HEADERS,timeout=8)
        r.raise_for_status()
        return Response(r.content,media_type='image/png',headers={'Cache-Control':'public, max-age=86400'})
    except Exception:
        raise HTTPException(502,'Tile non disponibile')

def ics_escape(s): return str(s or '').replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')

@app.get('/api/calendar/{fixture_id}.ics')
def calendar_ics(fixture_id:str):
    x=fixture_by_id(fixture_id)
    if not x:raise HTTPException(404)
    hub=load_json('hub.json',{});duration=int(hub.get('calendar_duration_minutes',120))
    start=iso_dt(x['date'],x['time']);end=start+timedelta(minutes=duration)
    stamp=datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    def fmt(d):return d.strftime('%Y%m%dT%H%M%S')
    summary=f"UNDER 14 FIGC · {x['home']} - {x['away']}"
    ics='\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//USSA Rozzano//Smart Hub//IT','CALSCALE:GREGORIAN','BEGIN:VEVENT',
        f"UID:{x['id']}@ussa-smart-hub",f'DTSTAMP:{stamp}',f'DTSTART:{fmt(start)}',f'DTEND:{fmt(end)}',f'SUMMARY:{ics_escape(summary)}',
        f"LOCATION:{ics_escape(x.get('field','')+' - '+x.get('address',''))}",f"DESCRIPTION:{ics_escape('Gara '+x.get('competition','')+' · '+x.get('home_away',''))}",'END:VEVENT','END:VCALENDAR',''])
    return Response(ics,media_type='text/calendar; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{fixture_id}.ics"'})

def qr_svg(data):
    img=qrcode.make(data,image_factory=qrcode.image.svg.SvgPathImage,box_size=10,border=2)
    b=io.BytesIO();img.save(b);return b.getvalue()

@app.get('/api/qr/calendar/{fixture_id}.svg')
def qr_calendar(fixture_id:str, request:Request):
    if not fixture_by_id(fixture_id):raise HTTPException(404)
    url=str(request.base_url).rstrip('/')+f'/api/calendar/{fixture_id}.ics'
    return Response(qr_svg(url),media_type='image/svg+xml')

@app.get('/api/qr/route/{fixture_id}.svg')
def qr_route(fixture_id:str):
    x=fixture_by_id(fixture_id)
    if not x:raise HTTPException(404)
    hub=load_json('hub.json',{});origin=hub['stadium']['route_address'];dest=x.get('route_address') or x.get('address','')
    url='https://www.google.com/maps/dir/?api=1&origin='+quote(origin)+'&destination='+quote(dest)+'&travelmode=driving'
    return Response(qr_svg(url),media_type='image/svg+xml')
