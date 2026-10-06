import math
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, PlainTextResponse
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, quote, urlparse
import requests, re, json, io, sqlite3, hashlib, os, threading
from bs4 import BeautifulSoup
import qrcode
import qrcode.image.svg
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT=Path(__file__).parent
app=FastAPI(title="USSA SMART HUB V2")
CSI_OLD="https://www.csi.milano.it"
CSI_LIVE="https://live.centrosportivoitaliano.it"
HEADERS={"User-Agent":"USSA-SMART-HUB/2.1","Accept-Language":"it-IT,it;q=0.9"}
CSI_CACHE_PATH=Path(os.getenv('CSI_CACHE_PATH') or ROOT/'csi_cache.json')
CSI_LOGO_DIR=ROOT/'assets'/'csi-clubs'
CSI_SYNC_HOUR=12
CSI_RETRY_MINUTES=30
CSI_SYNC_LOCK=threading.Lock()
CSI_SCHEDULER_STARTED=False
GEOCODE_CACHE={}
ROUTE_RUNTIME_CACHE={}
FIGC_SOURCE_URL='https://www.tuttocampo.it/Lombardia/GiovanissimiProvincialiU14/GironeEMilano/Risultati'
FIGC_PRIMARY_SOURCE_URL='https://www.sprintesport.it/sezioni/119/classifiche#!/categoria/26/campionato/174/girone/5'
FIGC_API_BASE='https://www.sprintesport.it/webservices/sprintsport'
FIGC_API_PARAMS={'idsport':1,'idcomitato':26,'idcategoria':174,'idgirone':5}
FIGC_CACHE_PATH=Path(os.getenv('FIGC_CACHE_PATH') or ROOT/'figc_cache.json')
FIGC_SYNC_HOUR=12
FIGC_RETRY_MINUTES=30
FIGC_SYNC_LOCK=threading.Lock()
FIGC_SCHEDULER_STARTED=False
TUTTOCAMPO_HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36',
    'Accept-Language':'it-IT,it;q=0.9,en;q=0.7',
    'Referer':FIGC_SOURCE_URL,
}
TC_TEAM_ALIASES={
    'USSA ROZZANO':'USSA Rozzano',
    'FROG MILANO':'FROG MILANO',
    'SANGIULIANO CVS':'SANGIULIANO CVS',
    'SIZIANO LANTERNA':'SIZIANO LANTERNA',
    'TRIAL ROZZANO':'TRIAL ROZZANO',
    'VIGE MILANO':'VIGE MILANO',
    'REAL BASIGLIO MILANO 3':'REAL BASIGLIO',
    'FIVE TO SEVEN':'FIVE TO SEVEN',
    'AL 2 SPORT':'AL 2 SPORT',
    'FC MILANESE 1902':'FOOTBALL C. MILANESE',
    'ZIBIDO SAN GIACOMO':'ZIBIDO S. GIACOMO',
    'FORZA E CORAGGIO':'FORZA E CORAGGIO',
    'FATIMATRACCIA':'FATIMATRACCIA',
    'MILANO FOOTBALL ACADEMY':'MILANO F. ACADEMY',
}

U13_TEST_STANDINGS=[
 {"position":1,"team":"S.Giuliano Cologno Osgd","points":18,"played":8,"wins":6,"draws":0,"losses":2,"gf":18,"gs":8},
 {"position":2,"team":"Ussa Rozzano","points":17,"played":8,"wins":5,"draws":2,"losses":1,"gf":24,"gs":13},
 {"position":3,"team":"Polisportiva Omr","points":15,"played":8,"wins":5,"draws":0,"losses":3,"gf":21,"gs":17},
 {"position":4,"team":"Usom Calcio","points":15,"played":8,"wins":4,"draws":3,"losses":1,"gf":25,"gs":11},
 {"position":5,"team":"S.Fermo","points":13,"played":8,"wins":4,"draws":1,"losses":3,"gf":13,"gs":14},
 {"position":6,"team":"Osm Assago","points":11,"played":8,"wins":3,"draws":2,"losses":3,"gf":17,"gs":7},
 {"position":7,"team":"Sporting C.B. Scb","points":9,"played":8,"wins":3,"draws":0,"losses":5,"gf":8,"gs":15},
 {"position":8,"team":"Osv Milano 2013 Orange","points":6,"played":8,"wins":2,"draws":0,"losses":6,"gf":7,"gs":22},
 {"position":9,"team":"Aso Cernusco 2013 Blu","points":0,"played":8,"wins":0,"draws":0,"losses":8,"gf":3,"gs":29}
]
U13_TEST_SCORERS=[
 {"name":"DI TOMA SAMUELE","goals":4},{"name":"LAURORA TOMMASO","goals":3},
 {"name":"LIVRIERI ALESSIO","goals":2},{"name":"BRAMBILLA SAMUELE WALTER","goals":2},
 {"name":"DE GREGORIO FRANCESCO","goals":2},{"name":"FALAPPA LEONARDO","goals":2},
 {"name":"PAGANELLO CHRISTIAN","goals":1}
]

U13_TEST_MATCHES=[
 {"date":"2026-03-28","time":"17:00","home":"Polisportiva Omr","away":"Ussa Rozzano","result":"7 - 4","field":"Centro Maria Rivetta","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0103/","team_key":"u13a11_test","competition":"CSI","round":1},
 {"date":"2026-04-11","time":"15:00","home":"Ussa Rozzano","away":"S.Giuliano Cologno Osgd","result":"4 - 2","field":"USSA Stadium","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0202/","team_key":"u13a11_test","competition":"CSI","round":2},
 {"date":"2026-04-18","time":"16:00","home":"Aso Cernusco 2013 Blu","away":"Ussa Rozzano","result":"0 - 5","field":"Oratorio Paolo VI","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0304/","team_key":"u13a11_test","competition":"CSI","round":3},
 {"date":"2026-04-25","time":"15:00","home":"Ussa Rozzano","away":"S.Fermo","result":"3 - 0","field":"USSA Stadium","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0401/","team_key":"u13a11_test","competition":"CSI","round":4},
 {"date":"2026-05-10","time":"15:00","home":"Usom Calcio","away":"Ussa Rozzano","result":"2 - 2","field":"Campo Comunale Sarmazzano","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0601/","team_key":"u13a11_test","competition":"CSI","round":6},
 {"date":"2026-05-16","time":"15:00","home":"Ussa Rozzano","away":"Sporting C.B. Scb","result":"3 - 0","field":"USSA Stadium","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0704/","team_key":"u13a11_test","competition":"CSI","round":7},
 {"date":"2026-05-24","time":"14:30","home":"Osv Milano 2013 Orange","away":"Ussa Rozzano","result":"1 - 2","field":"Iris 1914","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0802/","team_key":"u13a11_test","competition":"CSI","round":8},
 {"date":"2026-05-28","time":"18:30","home":"Ussa Rozzano","away":"Osm Assago","result":"1 - 1","field":"USSA Stadium","detail_url":"https://live.centrosportivoitaliano.it/25/Calcio-a-11/Lombardia/Milano/P2025235BA0903/","team_key":"u13a11_test","competition":"CSI","round":9}
]

# Dettaglio locale ricco per la gara CSI usata come test di riferimento.
# È un fallback: se CSI LIVE risponde, i dati live hanno priorità.
U13_DETAIL_FALLBACK = {
    '/25/Calcio-a-11/Lombardia/Milano/P2025235BA0202/': {
        'overview': {
            'home': {'team':'Ussa Rozzano','points':17,'position':2,'played':8,'wins':5,'draws':2,'losses':1,'gf':24,'gs':13},
            'away': {'team':'S.Giuliano Cologno Osgd','points':18,'position':1,'played':8,'wins':6,'draws':0,'losses':2,'gf':18,'gs':8},
            'mode':'snapshot_csi'
        },
        'events': [
            {'time':"24'",'type':'goal','text':'S.Giuliano Cologno Osgd segna: 0–1'},
            {'time':"30'",'type':'goal','text':'USSA Rozzano pareggia: 1–1'},
            {'time':"31'",'type':'card','text':'Cartellino giallo: Paganello C. (USSA Rozzano)'},
            {'time':'INTERVALLO','type':'phase','text':'Fine primo tempo · 1–1'},
            {'time':"1'",'type':'sub','text':'USSA: Paganello C. esce · Pennino L. entra'},
            {'time':"1'",'type':'sub','text':'S.Giuliano: Morandotti M. esce · Elbeltagi A. entra'},
            {'time':"3'",'type':'goal','text':'USSA Rozzano segna: 2–1'},
            {'time':"8'",'type':'sub','text':'S.Giuliano: Pagano R. esce · Sequino M. entra'},
            {'time':"12'",'type':'goal','text':'USSA Rozzano segna: 3–1'},
            {'time':"13'",'type':'goal','text':'S.Giuliano Cologno Osgd segna: 3–2'},
            {'time':"19'",'type':'sub','text':'S.Giuliano: Milani M. esce · Caso A. entra'},
            {'time':"19'",'type':'sub','text':'USSA: Livrieri A. esce · Maida L. entra'},
            {'time':"26'",'type':'sub','text':'S.Giuliano: Casarano E. esce · Di Mitri D. entra'},
            {'time':"28'",'type':'sub','text':'S.Giuliano: Sequino M. esce · Milito D. entra'},
            {'time':"32'",'type':'goal','text':'USSA Rozzano segna: 4–2'},
            {'time':'FINE','type':'phase','text':'Fine gara · 4–2'}
        ],
        'report':'USSA Rozzano ribalta una gara iniziata in svantaggio e supera S.Giuliano Cologno Osgd 4–2. Dopo l’1–1 del primo tempo, USSA allunga nella ripresa, resiste al ritorno degli ospiti e chiude la partita nel finale.'
    }
}

def load_json(name, default):
    try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
    except:return default

def teams_dict(): return {x['key']:x for x in load_json('teams.json',[])}
def csi_source_url(t): return t.get('csi_live_url') or t.get('csi_old_url') or ''
def csi_source_teams(): return [t for t in teams_dict().values() if csi_source_url(t) and not t.get('test_only')]
def base_fixtures(): return load_json('fixtures.json',[])

def load_figc_cache():
    try:
        data=json.loads(FIGC_CACHE_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {'fixtures':[],'standings':[],'scorers':[],'meta':{}}
    except:
        return {'fixtures':[],'standings':[],'scorers':[],'meta':{}}

def save_figc_cache(data):
    FIGC_CACHE_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=FIGC_CACHE_PATH.with_suffix(FIGC_CACHE_PATH.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,FIGC_CACHE_PATH)

def fixtures():
    local=base_fixtures();cache=load_figc_cache();live=cache.get('fixtures') or []
    live_by_id={x.get('id'):x for x in live if isinstance(x,dict) and x.get('id')} if isinstance(live,list) else {}
    csi_rows=[]
    for row in (load_csi_cache().get('teams') or {}).values():
        if not isinstance(row,dict):continue
        for match in row.get('schedule') or []:
            if not isinstance(match,dict):continue
            item=dict(match);item['id']=item.get('id') or csi_fixture_id(item);csi_rows.append(item)
    csi_by_id={x['id']:x for x in csi_rows if x.get('id')}
    merged=[];seen=set()
    for x in local:
        item=dict(x)
        if item.get('competition')=='FIGC':item.update(live_by_id.get(item.get('id'),{}))
        elif item.get('competition')=='CSI':item.update(csi_by_id.get(item.get('id'),{}))
        merged.append(item);seen.add(item.get('id'))
    merged.extend(x for x in csi_rows if x.get('id') not in seen)
    return sorted(merged,key=lambda x:(x.get('date',''),x.get('time',''),x.get('id','')))
def clean(s): return re.sub(r"\s+"," ",s or "").strip()
def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=20);r.raise_for_status();return r.text
def soup(url): return BeautifulSoup(fetch(url),'lxml')
def iso_dt(d,t='00:00'): return datetime.fromisoformat(f"{d}T{t or '00:00'}")
def parse_hm(v): h,m=map(int,v.split(':'));return h*60+m
def rome_now(): return datetime.now(ZoneInfo('Europe/Rome'))
def local_now(): return rome_now().replace(tzinfo=None)

def load_csi_cache():
    try:
        data=json.loads(CSI_CACHE_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {'teams':{},'meta':{}}
    except:
        return {'teams':{},'meta':{}}

def save_csi_cache(data):
    CSI_CACHE_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=CSI_CACHE_PATH.with_suffix(CSI_CACHE_PATH.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,CSI_CACHE_PATH)

def cached_csi_field(t,field):
    row=(load_csi_cache().get('teams') or {}).get(t.get('key'))
    if not isinstance(row,dict) or field not in row:return False,[]
    value=row.get(field)
    return True,value if isinstance(value,list) else []

def parse_cache_time(value):
    try:return datetime.fromisoformat(value)
    except:return None

def csi_cache_due(now=None):
    now=now or rome_now();cache=load_csi_cache();meta=cache.get('meta') or {}
    sources=csi_source_teams()
    if not sources:return False
    retry_status=meta.get('status') in {'error','partial'}
    last_attempt=parse_cache_time(meta.get('last_attempt_at'))
    if last_attempt:
        if last_attempt.tzinfo is None:last_attempt=last_attempt.replace(tzinfo=ZoneInfo('Europe/Rome'))
        if retry_status and now-last_attempt.astimezone(ZoneInfo('Europe/Rome'))<timedelta(minutes=CSI_RETRY_MINUTES):return False
    if retry_status:return True
    cached=cache.get('teams') or {}
    if any(not isinstance(cached.get(t['key']),dict) or cached[t['key']].get('source_url')!=csi_source_url(t) for t in sources):return True
    last=parse_cache_time(meta.get('last_success_at'))
    if not cache.get('teams'):return True
    if not last:return True
    if last.tzinfo is None:last=last.replace(tzinfo=ZoneInfo('Europe/Rome'))
    last=last.astimezone(ZoneInfo('Europe/Rome'))
    # Se il servizio Render era sospeso all'orario previsto, recupera subito
    # qualunque aggiornamento più vecchio di ieri. Per la giornata corrente
    # resta valido l'orario delle 12:00 Europe/Rome.
    if last.date()<(now.date()-timedelta(days=1)):return True
    return now.hour>=CSI_SYNC_HOUR and last.date()<now.date()

def next_csi_sync_at(now=None):
    now=now or rome_now()
    target=now.replace(hour=CSI_SYNC_HOUR,minute=0,second=0,microsecond=0)
    if target<=now:target+=timedelta(days=1)
    return target

def csi_fixture_id(match):
    """ID locale stabile per usare anche le gare CSI con QR, calendario e mappe."""
    path=urlparse((match or {}).get('detail_url','')).path.rstrip('/')
    code=Path(path).name if path else ''
    code=re.sub(r'[^A-Za-z0-9_-]','',code)
    if not code:
        raw='|'.join(str((match or {}).get(k,'') or '') for k in ('team_key','date','time','home','away'))
        code=hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]
    return f'csi_{code}'

def fixture_by_id(fid):
    local=next((x for x in fixtures() if x.get('id')==fid),None)
    if local:return local
    if not str(fid or '').startswith('csi_'):return None
    for row in (load_csi_cache().get('teams') or {}).values():
        for match in row.get('schedule') or []:
            if csi_fixture_id(match)==fid:
                out=dict(match);out['id']=fid
                return out
    return None

def local_fixture_matches(team_key, competition=None):
    a=[x for x in fixtures() if not x.get('cancelled') and x.get('team_key')==team_key and (not competition or x.get('competition')==competition)]
    return sorted(a,key=lambda x:(x.get('date',''),x.get('time','')))

@app.get('/')
def home(): return FileResponse(ROOT/'index.html')
@app.get('/assets/ussa-logo.png')
def logo(): return FileResponse(ROOT/'ussa-logo.png',media_type='image/png')

@app.get('/assets/spikey-info.png')
def spikey_info(): return FileResponse(ROOT/'spikey-info.png',media_type='image/png')

@app.get('/assets/partners/{filename}')
def partner_asset(filename: str):
    allowed = {
        'tempocasa-rozzano.jpg',
        'cerba-healthcare.png',
        'golee.svg',
        'raredreams.png',
        'parma-calcio.svg',
        'south-barber.png',
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail='Logo non disponibile')
    return FileResponse(ROOT/'assets'/'partners'/filename)

@app.get('/assets/spikey/{filename}')
def spikey_asset(filename: str):
    allowed = {
        'info-welcome.png',
        'info-secretariat.png',
        'info-social.png',
        'info-leadership.png',
        'info-partners.png',
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail='Illustrazione non disponibile')
    return FileResponse(ROOT/'assets'/'spikey'/filename, media_type='image/png')

@app.get('/assets/clubs/{filename}')
def club_asset(filename: str):
    allowed = {
        'al-2-sport.png','fatimatraccia.png','fc-milanese-1902.png','forza-e-coraggio.png',
        'frog-milano.png','milano-football-academy.png','real-basiglio-milano-3.png',
        'sangiuliano-cvs.png','siziano-lanterna.png','trial-rozzano.png','vige-milano.png',
        'zibido-san-giacomo.png',
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail='Stemma non disponibile')
    return FileResponse(ROOT/'assets'/'clubs'/filename,media_type='image/png')

@app.get('/assets/csi-clubs/{filename}')
def csi_club_asset(filename: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.jpg',filename):
        raise HTTPException(status_code=404,detail='Stemma non disponibile')
    path=CSI_LOGO_DIR/filename
    if not path.is_file():raise HTTPException(status_code=404,detail='Stemma non disponibile')
    # CSI restituisce quasi sempre JPEG, ma alcuni stemmi ufficiali sono SVG
    # pur mantenendo nell'URL lo stesso identificativo. Serviamo quindi il MIME
    # reale, evitando immagini rotte nei browser con content sniffing rigido.
    try:is_svg=path.read_bytes()[:256].lstrip().startswith(b'<svg')
    except:is_svg=False
    media_type='image/svg+xml' if is_svg else 'image/jpeg'
    return FileResponse(path,media_type=media_type,headers={'Cache-Control':'public, max-age=604800'})
@app.get('/api/teams')
def api_teams(): return load_json('teams.json',[])
@app.get('/api/hub')
def api_hub(): return load_json('hub.json',{})

@app.get('/api/home/now')
def home_now(weekday:int|None=None, time:str|None=None):
    td=teams_dict();now=local_now()
    # Preview tecnico nascosto: viene usato solo se URL client passa ENTRAMBI i parametri.
    # Senza parametri si torna sempre, automaticamente, a giorno/ora reali.
    if weekday is not None and time:
        wd=max(1,min(7,int(weekday)))
        try: minute=parse_hm(time)
        except: minute=now.hour*60+now.minute
    else:
        wd=now.isoweekday();minute=now.hour*60+now.minute
    items=[]
    for t in td.values():
        if t.get('visible') is False: continue
        for x in t.get('training',[]):
            try:
                if int(x.get('weekday',0))==wd and parse_hm(x['start'])<=minute<parse_hm(x['end']):
                    items.append({'kind':'ALLENAMENTO','team_key':t['key'],'title':t['label'],'meta':f"{x['start']}–{x['end']}",'place':x.get('place',''),'icon':t.get('icon','●'),'sport':t.get('sport','')})
            except: pass
    # Partite e amichevoli reali in corso vengono considerate soltanto in modalità reale,
    # non nella preview settimanale.
    if weekday is None or not time:
        for x in fixtures():
            try:
                dt=iso_dt(x['date'],x['time'])
                if 0 <= (now-dt).total_seconds() < 120*60:
                    t=td.get(x['team_key'],{})
                    items.append({'kind':'PARTITA','team_key':x['team_key'],'title':t.get('label','PARTITA'),'meta':f"{x['home']} – {x['away']}",'place':x.get('field',''),'icon':t.get('icon','●'),'sport':t.get('sport','')})
            except: pass
        for e in load_json('events.json',[]):
            try:
                dt=iso_dt(e['date'],e.get('time','00:00'))
                if 0 <= (now-dt).total_seconds() < 90*60:
                    t=td.get(e.get('team_key'),{})
                    end=(dt+timedelta(minutes=90)).strftime('%H:%M')
                    items.append({
                        'kind':e.get('kind','EVENTO'),
                        'team_key':None if e.get('no_detail') else e.get('team_key'),
                        'title':e.get('title') or t.get('label','EVENTO USSA'),
                        'meta':f"{e.get('time','')}–{end}",
                        'place':e.get('field',''),
                        'icon':t.get('icon','●'),
                        'sport':t.get('sport','')
                    })
            except: pass
    return {'items':items,'preview': bool(weekday is not None and time)}

def csi_name(value):
    return clean(value).casefold()

def csi_logo_filename(source, code=''):
    code=clean(code)
    if not code:
        code=Path(urlparse(source).path).stem
    code=re.sub(r'[^A-Za-z0-9_-]','',code)
    return f'{code}.jpg' if code else ''

def csi_logo_ref(source,code=''):
    filename=csi_logo_filename(source,code)
    return f'/assets/csi-clubs/{filename}' if filename else ''

def cache_csi_logo(source, code=''):
    """Scarica una sola volta lo stemma CSI e restituisce il percorso locale pubblico."""
    if not source or 'USSA' in clean(code).upper():return ''
    filename=csi_logo_filename(source,code)
    if not filename:return ''
    target=CSI_LOGO_DIR/filename
    try:
        if not target.exists() or target.stat().st_size<200:
            CSI_LOGO_DIR.mkdir(parents=True,exist_ok=True)
            r=requests.get(source,headers=HEADERS,timeout=10);r.raise_for_status()
            ctype=(r.headers.get('content-type') or '').lower()
            if len(r.content)<200 or ('image' not in ctype and not source.lower().endswith(('.jpg','.jpeg','.png','.webp'))):
                return ''
            tmp=target.with_suffix(target.suffix+'.tmp');tmp.write_bytes(r.content);os.replace(tmp,target)
        return f'/assets/csi-clubs/{filename}'
    except:return ''

def split_csi_venue(value):
    raw=clean(re.sub(r'\s*\([^()]+\)\s*$','',value or ''))
    if not raw:return 'Campo non indicato',''
    # CSI concatena denominazione del campo e indirizzo. La via/piazza segna
    # l'inizio dell'indirizzo senza affidarsi a una lunghezza fissa.
    m=re.search(r'\b(Via|Viale|Piazza|Piazzale|P\.?\s*Za|Corso|Largo|Strada|Vicolo|S\.P\.|SP\s*\d)\b',raw,re.I)
    if not m:return raw,''
    return clean(raw[:m.start()]),clean(raw[m.start():])

def csi_round_info(anchor):
    label=anchor.find_previous('div',class_='label-giornata')
    text=clean(label.get_text(' ',strip=True) if label else '')
    mr=re.search(r'giornata\s+(\d+)',text,re.I)
    return (int(mr.group(1)) if mr else None,
            'RITORNO' if 'RITORNO' in text.upper() else ('ANDATA' if 'ANDATA' in text.upper() else ''))

def parse_live_schedule(t,s,url):
    """Legge le card calendario CSI Live 26/27 e conserva il vecchio markup come fallback."""
    out=[];seen=set();wanted=csi_name(t.get('csi_team_name') or 'Ussa Rozzano')
    anchors=s.select('a.btn-gara[href]')
    for a in anchors:
        names=[clean(x.get_text(' ',strip=True)) for x in a.select('.nome-squadra')]
        if len(names)!=2 or wanted not in {csi_name(names[0]),csi_name(names[1])}:continue
        text=clean(a.get_text(' ',strip=True))
        md=re.search(r'\b(\d{2}/\d{2}/\d{2})\b',text);mt=re.search(r'\b([0-2]\d:[0-5]\d)\b',text)
        if not md:continue
        try:dt=datetime.strptime(md.group(1)+(mt.group(1) if mt else '00:00'),'%d/%m/%y%H:%M')
        except:continue
        href=urljoin(url,a.get('href',''));path=urlparse(href).path
        if path in seen:continue
        seen.add(path)
        direct=[x for x in a.find_all('div',recursive=False) if 'flex-column' in (x.get('class') or [])]
        score_values=[]
        if direct:
            score_values=[clean(x.get_text(' ',strip=True)) for x in direct[-1].find_all('span',recursive=False)]
        hg=int(score_values[0]) if len(score_values)>=2 and score_values[0].isdigit() else None
        ag=int(score_values[1]) if len(score_values)>=2 and score_values[1].isdigit() else None
        images=a.select('.logo-squadra img')
        logos=[];logo_sources=[];logo_codes=[]
        for image in images[:2]:
            src=urljoin(url,image.get('src',''));code=image.get('alt') or Path(urlparse(src).path).stem
            logo_sources.append(src);logo_codes.append(code)
            logos.append(csi_logo_ref(src,code) if 'USSA' not in names[len(logos)].upper() else '/assets/ussa-logo.png')
        while len(logos)<2:
            logo_sources.append('');logo_codes.append('')
            logos.append('/assets/ussa-logo.png' if 'USSA' in names[len(logos)].upper() else '')
        field,address=split_csi_venue(a.get('data-bs-title',''))
        round_no,leg=csi_round_info(a)
        result=f'{hg} - {ag}' if hg is not None and ag is not None else ''
        out.append({
            'date':dt.date().isoformat(),'time':mt.group(1) if mt else '',
            'home':names[0],'away':names[1],'names':names,'raw':text,
            'result':result,'result_home':hg,'result_away':ag,
            'detail_url':href,'team_key':t['key'],'team_label':t.get('label',t['key']),
            'competition':'CSI','competition_label':t.get('csi_competition_label',t.get('label','CSI')),
            'group':t.get('csi_group',''),'round':round_no,'leg':leg,
            'home_away':'CASA' if csi_name(names[0])==wanted else 'TRASFERTA',
            'field':field,'address':address,'route_address':clean(f'{field} {address}'),
            'home_logo':logos[0],'away_logo':logos[1],
            'home_logo_source':logo_sources[0],'away_logo_source':logo_sources[1],
            'home_logo_code':logo_codes[0],'away_logo_code':logo_codes[1],
            'status':'DISPUTATA' if result else 'PROGRAMMATA','source':'CSI LIVE'
        })
    if out:return sorted(out,key=lambda x:(x['date'],x.get('time','')))
    # Compatibilità con eventuali pagine CSI che usano ancora tabelle.
    for tr in s.find_all('tr'):
        txt=clean(tr.get_text(' ',strip=True))
        if (t.get('csi_team_name') or 'USSA ROZZANO').upper() not in txt.upper():continue
        md=re.search(r'\b(\d{2}/\d{2}/\d{2})\b',txt);mt=re.search(r'\b([0-2]\d:[0-5]\d)\b',txt)
        if not md:continue
        try:dt=datetime.strptime(md.group(1)+(mt.group(1) if mt else '00:00'),'%d/%m/%y%H:%M')
        except:continue
        game=next((urljoin(url,x['href']) for x in tr.find_all('a',href=True) if '/P20' in urlparse(urljoin(url,x['href'])).path),'')
        if game and urlparse(game).path in seen:continue
        seen.add(urlparse(game).path)
        out.append({'date':dt.date().isoformat(),'time':mt.group(1) if mt else '', 'raw':txt,'names':[],
                    'result':'','detail_url':game,'team_key':t['key'],'team_label':t.get('label',t['key']),
                    'competition':'CSI','competition_label':t.get('csi_competition_label',t.get('label','CSI'))})
    return sorted(out,key=lambda x:(x['date'],x.get('time','')))

def parse_old_csi_schedule(t,s,url):
    """Legge il calendario ufficiale CSI Milano, inclusi campi, codici gara e stemmi."""
    out=[];leg='';wanted=csi_name(t.get('csi_team_name') or 'USSA ROZZANO')
    for tr in s.select('table.matches tr'):
        if 'separator' in (tr.get('class') or []):
            label=clean(tr.get_text(' ',strip=True)).upper()
            leg='RITORNO' if 'RITORNO' in label else ('ANDATA' if 'ANDATA' in label else leg)
            continue
        cells=tr.find_all('td',recursive=False)
        if len(cells)<10:continue
        try:round_no=int(clean(cells[0].get_text(' ',strip=True)))
        except:continue
        date_text=clean(cells[1].get_text(' ',strip=True));time_text=clean(cells[2].get_text(' ',strip=True))
        try:date=datetime.strptime(date_text,'%d/%m/%Y').date().isoformat()
        except:continue
        teams=[clean(x.get_text(' ',strip=True)) for x in tr.select('td.squadra')[:2]]
        if len(teams)!=2 or wanted not in {csi_name(teams[0]),csi_name(teams[1])}:continue
        venue=clean(cells[3].get_text(' ',strip=True));field,address=split_csi_venue(venue)
        info=tr.select_one('a.button[href]');detail_url=urljoin(url,info.get('href','')) if info else ''
        code=Path(urlparse(detail_url).path).stem.rsplit('-',1)[-1] if detail_url else ''
        result_text=clean(cells[8].get_text(' ',strip=True));score=re.search(r'\b(\d+)\s*[-–]\s*(\d+)\b',result_text)
        hg=int(score.group(1)) if score else None;ag=int(score.group(2)) if score else None
        images=tr.select('td.logo-squadra img')[:2];logos=[];logo_sources=[];logo_codes=[]
        for i,image in enumerate(images):
            src=urljoin(url,image.get('src',''));logo_code=image.get('alt') or Path(urlparse(src).path).stem
            logo_sources.append(src);logo_codes.append(logo_code)
            logos.append('/assets/ussa-logo.png' if 'USSA' in teams[i].upper() else csi_logo_ref(src,logo_code))
        while len(logos)<2:
            i=len(logos);logo_sources.append('');logo_codes.append('')
            logos.append('/assets/ussa-logo.png' if 'USSA' in teams[i].upper() else '')
        item={
            'date':date,'time':time_text,'home':teams[0],'away':teams[1],'names':teams,
            'result':f'{hg} - {ag}' if score else '','result_home':hg,'result_away':ag,
            'detail_url':detail_url,'team_key':t['key'],'team_label':t.get('label',t['key']),
            'competition':'CSI','competition_label':t.get('csi_competition_label',t.get('label','CSI')),
            'group':t.get('csi_group',''),'round':round_no,'leg':leg,
            'home_away':'CASA' if csi_name(teams[0])==wanted else 'TRASFERTA',
            'field':field,'address':address,'route_address':clean(f'{field} {address}'),
            'home_logo':logos[0],'away_logo':logos[1],
            'home_logo_source':logo_sources[0],'away_logo_source':logo_sources[1],
            'home_logo_code':logo_codes[0],'away_logo_code':logo_codes[1],
            'status':'DISPUTATA' if score else 'PROGRAMMATA','source':'CSI MILANO'
        }
        item['id']=f'csi_{code}' if code else csi_fixture_id(item)
        out.append(item)
    return sorted(out,key=lambda x:(x['date'],x.get('time','')))

def live_schedule_for_team(t,fresh=False):
    url=csi_source_url(t)
    if not url:return []
    if not fresh:
        found,rows=cached_csi_field(t,'schedule')
        if found:return rows
    page=soup(url)
    return parse_live_schedule(t,page,url) if 'live.centrosportivoitaliano.it' in url else parse_old_csi_schedule(t,page,url)

def parse_live_standings(s):
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
                               'losses':int(vals[6]) if len(vals)>6 and vals[6].isdigit() else None,
                               'gf':int(vals[7]) if len(vals)>7 and vals[7].isdigit() else None,
                               'gs':int(vals[8]) if len(vals)>8 and vals[8].isdigit() else None,
                               'ga':int(vals[8]) if len(vals)>8 and vals[8].isdigit() else None,
                               'goal_difference':int(vals[9]) if len(vals)>9 and re.fullmatch(r'-?\d+',vals[9]) else None})
            except:continue
        if result:return result
    return []

def live_standings(t,fresh=False):
    if not csi_source_url(t):return []
    if not fresh:
        found,rows=cached_csi_field(t,'standings')
        if found:return rows
    if t.get('csi_live_url'):return parse_live_standings(soup(t['csi_live_url']))
    return old_csi_standings(t)

def old_csi_standings(t):
    camp=t.get('csi_championship_id');sport=t.get('csi_sport_code');group=t.get('csi_group','')
    if not camp or not sport:return []
    try:
        r=requests.post(f'{CSI_OLD}/public/ajax/filtri.php',headers=HEADERS,timeout=20,data={
            'albo':'ok','classifiche':'ok','campionato':str(camp),'squadra':'','sport':sport,'girone':group})
        r.raise_for_status();page=BeautifulSoup(r.text,'lxml')
    except:return []
    out=[]
    for tr in page.select('table tr'):
        vals=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'],recursive=False)]
        if len(vals)<8 or not vals[0].isdigit():continue
        try:
            # Il secondo campo è la colonna dello stemma e può essere vuoto.
            offset=2 if len(vals)>2 and not vals[1] else 1
            team=vals[offset];nums=vals[offset+1:]
            out.append({'position':int(vals[0]),'team':team,'points':int(nums[0]),'played':int(nums[1]),
                        'wins':int(nums[2]),'draws':0,'losses':int(nums[3]),
                        'gf':int(nums[-2]) if len(nums)>=2 else None,'gs':int(nums[-1]) if nums else None})
        except:continue
    return out

def parse_live_scorers(s):
    out=[]
    try:
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

def live_scorers(t,fresh=False):
    if not t.get('csi_live_url'):return []
    if not fresh:
        found,rows=cached_csi_field(t,'scorers')
        if found:return rows
    return parse_live_scorers(soup(t['csi_live_url']))

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

def csi_sync_status(cache=None):
    cache=cache or load_csi_cache();meta=cache.get('meta') or {}
    source_count=len(csi_source_teams())
    next_run=next_csi_sync_at()
    last_attempt=parse_cache_time(meta.get('last_attempt_at'))
    if meta.get('status') in {'error','partial'} and last_attempt:
        if last_attempt.tzinfo is None:last_attempt=last_attempt.replace(tzinfo=ZoneInfo('Europe/Rome'))
        retry_at=last_attempt.astimezone(ZoneInfo('Europe/Rome'))+timedelta(minutes=CSI_RETRY_MINUTES)
        if retry_at>rome_now() and retry_at<next_run:next_run=retry_at
    return {
        'status':meta.get('status','never'),
        'running':CSI_SYNC_LOCK.locked(),
        'last_attempt_at':meta.get('last_attempt_at'),
        'last_success_at':meta.get('last_success_at'),
        'next_run_at':next_run.isoformat(timespec='minutes'),
        'source_count':source_count,
        'updated_count':int(meta.get('updated_count') or 0),
        'error_count':int(meta.get('error_count') or 0),
        'errors':meta.get('errors') or [],
        'cached_teams':len(cache.get('teams') or {}),
        'logo_count':int(meta.get('logo_count') or 0)
    }

def refresh_csi_cache(trigger='scheduled'):
    if not CSI_SYNC_LOCK.acquire(blocking=False):return csi_sync_status()
    try:
        previous=load_csi_cache();cached=dict(previous.get('teams') or {})
        sources=csi_source_teams()
        attempted_at=rome_now().isoformat(timespec='seconds');updated=0;errors=[];pages={};page_errors={};logos_to_cache=set()
        urls=list(dict.fromkeys(csi_source_url(t) for t in sources))
        def load_page(source_url):
            last=None
            for _ in range(2):
                try:return source_url,soup(source_url)
                except Exception as exc:last=exc
            raise last or ValueError('pagina CSI Live non disponibile')
        with ThreadPoolExecutor(max_workers=min(2,len(urls) or 1)) as pool:
            pending={pool.submit(load_page,url):url for url in urls}
            for future in as_completed(pending):
                source_url=pending[future]
                try:url,page=future.result();pages[url]=page
                except Exception as exc:page_errors[source_url]=clean(str(exc))[:140]
        for t in sources:
            try:
                url=csi_source_url(t)
                if url not in pages:raise ValueError(page_errors.get(url) or 'pagina CSI Live non disponibile')
                page=pages[url]
                schedule=parse_live_schedule(t,page,url) if t.get('csi_live_url') else parse_old_csi_schedule(t,page,url)
                if not schedule:raise ValueError('calendario pubblicato ma nessuna gara USSA riconosciuta')
                for match in schedule:
                    for side in ('home','away'):
                        if 'USSA' in clean(match.get(side)).upper():continue
                        source=match.get(f'{side}_logo_source');code=match.get(f'{side}_logo_code')
                        if source:logos_to_cache.add((source,code or ''))
                standings=parse_live_standings(page) if t.get('csi_live_url') else old_csi_standings(t)
                if not standings:raise ValueError('classifica/girone non riconosciuti nella pagina CSI Live')
                scorers=parse_live_scorers(page)
                if not scorers and t.get('csi_old_url'):scorers=old_csi_scorers(t)
                cached[t['key']]={
                    'label':t.get('label',t['key']),
                    'team_name':t.get('csi_team_name','Ussa Rozzano'),
                    'competition_label':t.get('csi_competition_label',t.get('label','CSI')),
                    'group':t.get('csi_group',''),
                    'source_url':url,
                    'fetched_at':attempted_at,
                    'schedule':schedule,
                    'standings':standings,
                    'scorers':scorers
                }
                updated+=1
            except Exception as exc:
                errors.append({'team_key':t.get('key'),'label':t.get('label',t.get('key','')),'message':clean(str(exc))[:160]})
        if logos_to_cache:
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda item:cache_csi_logo(item[0],item[1]),logos_to_cache))
        old_meta=previous.get('meta') or {}
        status='waiting' if not sources else ('ok' if not errors else ('partial' if updated else 'error'))
        meta={
            'status':status,
            'trigger':trigger,
            'last_attempt_at':attempted_at,
            'last_success_at':attempted_at if updated==len(sources) else old_meta.get('last_success_at'),
            'source_count':len(sources),
            'updated_count':updated,
            'error_count':len(errors),
            'logo_count':len(list(CSI_LOGO_DIR.glob('*.jpg'))) if CSI_LOGO_DIR.exists() else 0,
            'errors':errors
        }
        data={'teams':cached,'meta':meta};save_csi_cache(data)
        result=csi_sync_status(data);result['running']=False
        return result
    finally:
        CSI_SYNC_LOCK.release()

def csi_scheduler_loop():
    try:
        if csi_cache_due():refresh_csi_cache('startup')
    except:pass
    while True:
        threading.Event().wait(60)
        try:
            if csi_cache_due():refresh_csi_cache('scheduled')
        except:pass

def ensure_csi_refresh_if_due():
    """Riattiva il recupero CSI quando una richiesta sveglia il servizio."""
    try:
        if csi_cache_due() and not CSI_SYNC_LOCK.locked():
            threading.Thread(target=refresh_csi_cache,args=('page-request',),name='csi-request-sync',daemon=True).start()
    except:pass

TC_MONTHS={
    'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,
    'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12,
}

def tc_team_name(value):
    value=clean(value)
    return TC_TEAM_ALIASES.get(value.upper(),value)

def figc_cache_due(now=None):
    now=now or rome_now();cache=load_figc_cache();meta=cache.get('meta') or {}
    last_attempt=parse_cache_time(meta.get('last_attempt_at'))
    if last_attempt:
        if last_attempt.tzinfo is None:last_attempt=last_attempt.replace(tzinfo=ZoneInfo('Europe/Rome'))
        if meta.get('status') in {'error','partial','waiting'} and now-last_attempt.astimezone(ZoneInfo('Europe/Rome'))<timedelta(minutes=FIGC_RETRY_MINUTES):return False
    if meta.get('status') in {'error','partial','waiting'}:return True
    if len(cache.get('fixtures') or [])!=26:return True
    last=parse_cache_time(meta.get('last_success_at'))
    if not last:return True
    if last.tzinfo is None:last=last.replace(tzinfo=ZoneInfo('Europe/Rome'))
    last=last.astimezone(ZoneInfo('Europe/Rome'))
    if last.date()<(now.date()-timedelta(days=1)):return True
    return now.hour>=FIGC_SYNC_HOUR and last.date()<now.date()

def next_figc_sync_at(now=None):
    now=now or rome_now()
    target=now.replace(hour=FIGC_SYNC_HOUR,minute=0,second=0,microsecond=0)
    if target<=now:target+=timedelta(days=1)
    return target

def tc_bootstrap(session):
    r=session.get(FIGC_SOURCE_URL,headers=TUTTOCAMPO_HEADERS,timeout=25);r.raise_for_status();html=r.text
    def grab(pattern,label):
        m=re.search(pattern,html,re.I)
        if not m:raise ValueError(f'{label} non trovato')
        return m.group(1)
    token=grab(r"var\s+tckk='([^']+)'",'token Tuttocampo')
    round_id=grab(r"var\s+roundID='([^']+)'",'girone Tuttocampo')
    count=int(grab(r"var\s+matchesNumber='(\d+)'",'numero giornate'))
    if round_id!='LO.GX.E.MI' or count!=26:raise ValueError('Il girone Tuttocampo non coincide con U14 Milano Girone E')
    return token,round_id,count,dict(session.cookies)

def tc_post_module(path,token,cookies,data):
    url=f'https://www.tuttocampo.it/{path}?tckk={quote(token)}'
    r=requests.post(url,headers=TUTTOCAMPO_HEADERS,cookies=cookies,data=data,timeout=25)
    r.raise_for_status()
    if len(r.text)<120 or 'Errore imprevisto' in r.text:raise ValueError('risposta Tuttocampo non valida')
    return r.text

def tc_date_from_row(label,header_dates):
    m=re.search(r'\b(\d{1,2})\s+([a-zà]+)',clean(label).lower())
    if not m:return ''
    day=int(m.group(1));month=TC_MONTHS.get(m.group(2))
    if not month:return ''
    for iso in header_dates:
        d=datetime.strptime(iso,'%Y-%m-%d')
        if d.day==day and d.month==month:return iso
    year=datetime.strptime(header_dates[0],'%Y-%m-%d').year if header_dates else rome_now().year
    return f'{year:04d}-{month:02d}-{day:02d}'

def parse_tc_day(html,day):
    page=BeautifulSoup(html,'html.parser')
    header=clean((page.select_one('#match_date') or page.new_tag('span')).get_text(' ',strip=True))
    header_dates=[]
    for d,m,y in re.findall(r'(\d{2})\|(\d{2})\|(\d{4})',header):header_dates.append(f'{y}-{m}-{d}')
    current_date=''
    selected=None
    for tr in page.select('table.table-results tbody tr'):
        classes=set(tr.get('class') or [])
        if 'date' in classes:
            current_date=tc_date_from_row(clean(tr.get_text(' ',strip=True)),header_dates)
            continue
        if 'match' not in classes:continue
        home=clean((tr.select_one('td.team.home a.team-name') or page.new_tag('a')).get_text(' ',strip=True))
        away=clean((tr.select_one('td.team.away a.team-name') or page.new_tag('a')).get_text(' ',strip=True))
        if 'USSA ROZZANO' not in {home.upper(),away.upper()}:continue
        hour=clean((tr.select_one('td.match-time span.hour') or page.new_tag('span')).get_text(' ',strip=True))
        hm=re.search(r'\b([0-2]\d:[0-5]\d)\b',hour)
        goals=[]
        for side in ('home','away'):
            goal=clean((tr.select_one(f'td.team.{side} span.goal') or page.new_tag('span')).get_text(' ',strip=True))
            goals.append(int(goal) if re.fullmatch(r'\d+',goal) else None)
        selected={
            'date':current_date or (header_dates[0] if header_dates else ''),
            'time':hm.group(1) if hm else '',
            'home':tc_team_name(home),'away':tc_team_name(away),
            'result_home':goals[0],'result_away':goals[1],
            'result':f'{goals[0]} - {goals[1]}' if None not in goals else '',
            'external_detail_url':tr.get('data-link') or '',
            'postponed':'rinviat' in clean(tr.get_text(' ',strip=True)).lower(),
        }
        break
    if not selected:
        # Dopo un ritiro Tuttocampo non restituisce piu una partita, ma una riga
        # "Riposa: Ussa Rozzano". E una giornata valida e non deve bloccare il girone.
        repose=' '.join(clean(x.get_text(' ',strip=True)) for x in page.select('tr.repose'))
        if 'USSA ROZZANO' in repose.upper():return {'bye':True}
        raise ValueError(f'USSA non trovata nella giornata {day}')
    return selected

def merge_tc_fixture(day,row):
    leg='ANDATA' if day<=13 else 'RITORNO';round_no=day if day<=13 else day-13
    fixture_id=f"u14-figc-{'a' if leg=='ANDATA' else 'r'}-{round_no:02d}"
    base=next((dict(x) for x in base_fixtures() if x.get('id')==fixture_id),None)
    if not base:raise ValueError(f'fixture locale {fixture_id} non trovata')
    if row.get('bye'):
        base['cancelled']=True;base['status']='RIPOSO'
        base.pop('result',None);base.pop('result_home',None);base.pop('result_away',None)
        base['source']='Tuttocampo · U14 Milano Girone E'
        base['source_url']=f"https://www.tuttocampo.it/Lombardia/GiovanissimiProvincialiU14/GironeEMilano/Giornata{day}"
        return base
    expected={clean(base.get('home')).upper(),clean(base.get('away')).upper()}
    received={clean(row.get('home')).upper(),clean(row.get('away')).upper()}
    if expected!=received:raise ValueError(f'squadre non coerenti per {fixture_id}')
    # Alcune giornate di ritorno pubblicate da Tuttocampo riportano ancora, nel
    # frammento dinamico, l'anno della stagione di andata. Giorno e mese sono
    # aggiornati, ma l'anno viene vincolato alla stagione 2026/27.
    if row.get('date'):
        try:
            parsed=datetime.strptime(row['date'],'%Y-%m-%d')
            row['date']=parsed.replace(year=2026 if leg=='ANDATA' else 2027).date().isoformat()
        except:row['date']=''
    for key in ('date','time','home','away','external_detail_url'):
        if row.get(key):base[key]=row[key]
    if row.get('result'):
        base['result']=row['result'];base['result_home']=row['result_home'];base['result_away']=row['result_away']
        base['status']='DISPUTATA';base.pop('postponed',None)
    else:
        base.pop('result',None);base.pop('result_home',None);base.pop('result_away',None)
        if row.get('postponed'):base['status']='RINVIATA';base['postponed']=True
        else:base['status']='PROGRAMMATA';base.pop('postponed',None)
    base.pop('cancelled',None)
    base['home_away']='CASA' if 'USSA' in base['home'].upper() else 'TRASFERTA'
    base['source']='Tuttocampo · U14 Milano Girone E'
    base['source_url']=f"https://www.tuttocampo.it/Lombardia/GiovanissimiProvincialiU14/GironeEMilano/Giornata{day}"
    return base

def parse_tc_standings(html):
    page=BeautifulSoup(html,'html.parser');rows=[]
    for tr in page.select('table.table_ranking tbody tr'):
        team=clean((tr.select_one('td.team') or page.new_tag('td')).get_text(' ',strip=True))
        nums=[]
        for td in tr.find_all('td'):
            value=clean(td.get_text(' ',strip=True))
            if re.fullmatch(r'-?\d+',value):nums.append(int(value))
        if not team or len(nums)<8:continue
        pt,g,v,n,p,gf,gs,dr=nums[-8:]
        rows.append({'position':len(rows)+1,'team':tc_team_name(team),'points':pt,'played':g,
                     'wins':v,'draws':n,'losses':p,'gf':gf,'gs':gs,'ga':gs,'goal_difference':dr})
    # Il numero di squadre puo diminuire durante la stagione (ritiri). Validiamo
    # struttura e presenza USSA, non un totale rigido destinato a cambiare.
    if len(rows)<8 or len({clean(x['team']).upper() for x in rows})!=len(rows):
        raise ValueError(f'classifica non valida: {len(rows)} squadre')
    if not any('USSA ROZZANO'==clean(x['team']).upper() for x in rows):
        raise ValueError('USSA Rozzano assente dalla classifica')
    return rows

def parse_tc_scorers(html):
    page=BeautifulSoup(html,'html.parser');out=[]
    for tr in page.select('table tbody tr'):
        cells=[clean(td.get_text(' ',strip=True)) for td in tr.find_all(['td','th'])]
        line=' | '.join(cells)
        if 'USSA ROZZANO' not in line.upper():continue
        goal=next((int(x) for x in reversed(cells) if re.fullmatch(r'\d+',x)),0)
        name=next((x for x in cells if re.search(r'[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]{2,}',x) and 'USSA' not in x.upper()),'')
        if name and goal:out.append({'name':name,'goals':goal})
    out.sort(key=lambda x:(-x['goals'],x['name']))
    return out

def ss_get(dataset):
    """Legge il feed JSON pubblico di Sprint e Sport per il girone FIGC U14."""
    url=f"{FIGC_API_BASE}/{dataset}.jsp"
    headers={**TUTTOCAMPO_HEADERS,'Referer':FIGC_PRIMARY_SOURCE_URL,'Accept':'application/json'}
    response=requests.get(url,headers=headers,params=FIGC_API_PARAMS,timeout=40)
    response.raise_for_status()
    data=response.json()
    if not isinstance(data,dict):raise ValueError(f'{dataset}: risposta JSON non valida')
    return data

def ss_team_name(value):
    aliases={
        'MILANO F.A.':'MILANO F. ACADEMY',
        'FC MILANESE':'FOOTBALL C. MILANESE',
        'SIZ.LANTERNA':'SIZIANO LANTERNA',
        'ZIBIDO':'ZIBIDO S. GIACOMO',
    }
    value=clean(value)
    return aliases.get(value.upper(),tc_team_name(value))

def parse_ss_fixtures(payload):
    rows=payload.get('risultati') or []
    ussa={}
    for row in rows:
        home=clean(row.get('squadraH'));away=clean(row.get('squadraV'))
        if 'USSA ROZZANO' not in {home.upper(),away.upper()}:continue
        try:day=int(row.get('giornata'))
        except:continue
        if not 1<=day<=26:continue
        ussa[day]=row
    if len(ussa)<18:raise ValueError(f'calendario FIGC incompleto: {len(ussa)} gare USSA riconosciute')
    out=[]
    withdrawn={'VIGE MILANO','REAL BASIGLIO'}
    for original in base_fixtures():
        if original.get('competition')!='FIGC':continue
        item=dict(original)
        match=re.search(r'-(a|r)-(\d{2})$',item.get('id') or '')
        if not match:continue
        day=int(match.group(2))+(13 if match.group(1)=='r' else 0)
        row=ussa.get(day)
        opponents={clean(item.get('home')).upper(),clean(item.get('away')).upper()}-{'USSA ROZZANO'}
        if not row:
            if opponents & withdrawn:
                item['cancelled']=True;item['status']='RIPOSO'
                for key in ('result','result_home','result_away'):item.pop(key,None)
            out.append(item);continue
        home=ss_team_name(row.get('squadraH'));away=ss_team_name(row.get('squadraV'))
        item.update({'home':home,'away':away,'home_away':'CASA' if home.upper()=='USSA ROZZANO' else 'TRASFERTA'})
        raw_dt=clean(row.get('dataorap'))
        try:
            parsed=datetime.fromisoformat(raw_dt)
            item['date']=parsed.date().isoformat();item['time']=parsed.strftime('%H:%M')
        except:
            if row.get('datag'):item['date']=str(row['datag'])[:10]
        score=clean(row.get('risultato')).replace('–','-')
        score_match=re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*',score)
        if score_match:
            item['result_home']=int(score_match.group(1));item['result_away']=int(score_match.group(2))
            item['result']=f"{item['result_home']} - {item['result_away']}";item['status']='DISPUTATA'
        else:
            for key in ('result','result_home','result_away'):item.pop(key,None)
            item['status']='PROGRAMMATA'
        item.pop('cancelled',None);item.pop('postponed',None)
        result_id=str(row.get('idrisultato') or '')
        if result_id:item['external_detail_url']=f'https://www.sprintesport.it/sezioni/479/partita#!/{result_id}'
        item['source']='Sprint e Sport · U14 Milano Girone E';item['source_url']=FIGC_PRIMARY_SOURCE_URL
        out.append(item)
    if len(out)!=26:raise ValueError(f'calendario locale FIGC non coerente: {len(out)} giornate')
    return out

def parse_ss_standings(payload):
    source=payload.get('classifica') or payload.get('classifica_v') or []
    out=[]
    for row in source:
        team=ss_team_name(row.get('squadra'))
        if not team:continue
        out.append({
            'position':int(row.get('pos') or len(out)+1),'team':team,
            'points':int(row.get('punti') or 0),'played':int(row.get('pg') or 0),
            'wins':int(row.get('pv') or 0),'draws':int(row.get('pn') or 0),'losses':int(row.get('pp') or 0),
            'gf':int(row.get('rf') or 0),'gs':int(row.get('rs') or 0),'ga':int(row.get('rs') or 0),
            'goal_difference':int(row.get('dr') or 0),
        })
    if len(out)<8 or not any(clean(x['team']).upper()=='USSA ROZZANO' for x in out):
        raise ValueError(f'classifica FIGC non valida: {len(out)} squadre')
    return out

def parse_ss_scorers(payload):
    blocks=payload.get('PlayerStatistics') or []
    goals=next((x.get('Data') or [] for x in blocks if clean(x.get('Label')).lower()=='gol'),[])
    out=[]
    for row in goals:
        if clean(row.get('squadra')).upper()!='USSA ROZZANO':continue
        value=row.get('valore_stat')
        try:value=int(value)
        except:continue
        if value>0:out.append({'name':clean(row.get('calciatore')),'goals':value})
    out.sort(key=lambda x:(-x['goals'],x['name']))
    return out

def figc_sync_status(cache=None):
    cache=cache or load_figc_cache();meta=cache.get('meta') or {};next_run=next_figc_sync_at()
    last_attempt=parse_cache_time(meta.get('last_attempt_at'))
    if meta.get('status') in {'error','partial','waiting'} and last_attempt:
        if last_attempt.tzinfo is None:last_attempt=last_attempt.replace(tzinfo=ZoneInfo('Europe/Rome'))
        retry_at=last_attempt.astimezone(ZoneInfo('Europe/Rome'))+timedelta(minutes=FIGC_RETRY_MINUTES)
        if retry_at>rome_now() and retry_at<next_run:next_run=retry_at
    return {
        'status':meta.get('status','never'),'running':FIGC_SYNC_LOCK.locked(),
        'last_attempt_at':meta.get('last_attempt_at'),'last_success_at':meta.get('last_success_at'),
        'next_run_at':next_run.isoformat(timespec='minutes'),'source_count':3,
        'updated_count':int(meta.get('updated_count') or 0),'error_count':int(meta.get('error_count') or 0),
        'errors':meta.get('errors') or [],'warnings':meta.get('warnings') or [],
        'cached_fixtures':len(cache.get('fixtures') or []),
        'source_url':FIGC_PRIMARY_SOURCE_URL,
    }

def refresh_figc_cache(trigger='scheduled'):
    if not FIGC_SYNC_LOCK.acquire(blocking=False):return figc_sync_status()
    try:
        previous=load_figc_cache();attempted_at=rome_now().isoformat(timespec='seconds');errors=[];warnings=[];updated=0
        fixtures_live=previous.get('fixtures') or [];standings=previous.get('standings') or [];scorers=previous.get('scorers') or []
        datasets={'getResults':'calendario','getRanking':'classifica','getStats':'marcatori'};payloads={}
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending={pool.submit(ss_get,name):name for name in datasets}
            for future in as_completed(pending):
                name=pending[future]
                try:payloads[name]=future.result()
                except Exception as exc:errors.append({'dataset':datasets[name],'message':clean(str(exc))[:180]})
        if 'getResults' in payloads:
            try:fixtures_live=parse_ss_fixtures(payloads['getResults']);updated+=1
            except Exception as exc:errors.append({'dataset':'calendario','message':clean(str(exc))[:180]})
        if 'getRanking' in payloads:
            try:standings=parse_ss_standings(payloads['getRanking']);updated+=1
            except Exception as exc:errors.append({'dataset':'classifica','message':clean(str(exc))[:180]})
        if 'getStats' in payloads:
            try:scorers=parse_ss_scorers(payloads['getStats']);updated+=1
            except Exception as exc:errors.append({'dataset':'marcatori','message':clean(str(exc))[:180]})
        # Coerenza automatica: se la classifica dichiara gare giocate che non sono
        # ancora presenti nei risultati, il job resta in attesa e riprova ogni 30'.
        ussa=next((x for x in standings if clean(x.get('team')).upper()=='USSA ROZZANO'),None)
        known_results=sum(1 for x in fixtures_live if not x.get('cancelled') and x.get('result') and
                          'USSA ROZZANO' in {clean(x.get('home')).upper(),clean(x.get('away')).upper()})
        if ussa and known_results<int(ussa.get('played') or 0):
            warnings.append({'dataset':'coerenza','message':f"classifica: {ussa.get('played')} gare USSA; risultati acquisiti: {known_results}"})
        now=local_now()
        overdue=[]
        for x in fixtures_live:
            if x.get('cancelled') or x.get('postponed') or x.get('result'):continue
            try:
                if iso_dt(x['date'],x.get('time') or '00:00')+timedelta(minutes=120)<now:overdue.append(x.get('id'))
            except:pass
        if overdue:warnings.append({'dataset':'risultati','message':f"in attesa del risultato: {', '.join(overdue[:4])}"})
        old_meta=previous.get('meta') or {}
        if errors:status='partial' if updated else 'error'
        elif warnings:status='waiting'
        else:status='ok' if updated==3 else ('partial' if updated else 'error')
        meta={'status':status,'trigger':trigger,'source':'Sprint e Sport JSON','last_attempt_at':attempted_at,
              'last_success_at':attempted_at if status=='ok' else old_meta.get('last_success_at'),
              'updated_count':updated,'error_count':len(errors),'errors':errors,'warnings':warnings}
        data={'fixtures':fixtures_live,'standings':standings,'scorers':scorers,'meta':meta}
        save_figc_cache(data);result=figc_sync_status(data);result['running']=False;return result
    finally:
        FIGC_SYNC_LOCK.release()

def figc_scheduler_loop():
    try:
        if figc_cache_due():refresh_figc_cache('startup')
    except:pass
    while True:
        threading.Event().wait(60)
        try:
            if figc_cache_due():refresh_figc_cache('scheduled')
        except:pass

def ensure_figc_refresh_if_due():
    """Fallback non bloccante: anche una normale apertura dell'Hub riattiva il sync."""
    try:
        if figc_cache_due() and not FIGC_SYNC_LOCK.locked():
            threading.Thread(target=refresh_figc_cache,args=('page-request',),name='figc-request-sync',daemon=True).start()
    except:pass

@app.on_event('startup')
def start_data_schedulers():
    global CSI_SCHEDULER_STARTED,FIGC_SCHEDULER_STARTED
    if not CSI_SCHEDULER_STARTED:
        CSI_SCHEDULER_STARTED=True
        threading.Thread(target=csi_scheduler_loop,name='csi-daily-sync',daemon=True).start()
    if not FIGC_SCHEDULER_STARTED:
        FIGC_SCHEDULER_STARTED=True
        threading.Thread(target=figc_scheduler_loop,name='figc-daily-sync',daemon=True).start()

def team_standings_data(t, competition):
    if competition=='FIGC' and t.get('key')=='u14':
        ensure_figc_refresh_if_due()
        return load_figc_cache().get('standings') or fixture_stats_rows('FIGC')
    if competition!='CSI': return []
    rows=[]
    try:rows=live_standings(t)
    except:pass
    if t.get('key')=='u13a11_test' and not rows:rows=U13_TEST_STANDINGS
    return rows

def team_scorers_data(t, competition):
    if competition=='FIGC' and t.get('key')=='u14':
        ensure_figc_refresh_if_due()
        return load_figc_cache().get('scorers') or []
    if competition!='CSI': return []
    found,rows=cached_csi_field(t,'scorers')
    if not found:rows=live_scorers(t,fresh=True) or old_csi_scorers(t)
    if t.get('key')=='u13a11_test' and not rows:rows=U13_TEST_SCORERS
    return rows

def team_matches_data(t, competition):
    now=local_now()
    if competition=='FIGC':
        ensure_figc_refresh_if_due()
        arr=local_fixture_matches(t['key'],'FIGC')
        played=[x for x in arr if iso_dt(x['date'],x['time'])<now]
        nexts=[x for x in arr if iso_dt(x['date'],x['time'])>=now]
        return played,nexts
    if competition=='CSI' and csi_source_url(t):
        # La U13 TEST deve offrire sempre l'esperienza completa anche se CSI LIVE
        # cambia markup o risponde lentamente: il calendario storico verificato resta
        # disponibile localmente, mentre i dettagli continuano ad aprire le pagine CSI.
        if t.get('key')=='u13a11_test':
            arr=[dict(x) for x in U13_TEST_MATCHES]
        else:
            try:arr=live_schedule_for_team(t)
            except:arr=[]
        if not arr:arr=local_fixture_matches(t['key'],'CSI')
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
    ensure_csi_refresh_if_due()
    ensure_figc_refresh_if_due()
    now=local_now();items=[]
    # Single local source for real FIGC fixtures.
    for x in fixtures():
        if x.get('cancelled'):continue
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

def cached_csi_match(path):
    teams=teams_dict();cache=load_csi_cache().get('teams') or {}
    for key,row in cache.items():
        if not isinstance(row,dict):continue
        for match in row.get('schedule') or []:
            if urlparse(match.get('detail_url','')).path==path:
                out=dict(match);out['id']=csi_fixture_id(match)
                return out,teams.get(key,{}),row
    return None,None,None

def standings_row(rows,name):
    wanted=csi_name(name)
    return next((dict(x) for x in rows or [] if csi_name(x.get('team'))==wanted),None)

def parse_live_game_detail(page,url,base=None):
    base=dict(base or {});hero=page.select_one('.hero-gara')
    if not hero:raise ValueError('dettaglio gara CSI non riconosciuto')
    text=clean(hero.get_text(' ',strip=True))
    md=re.search(r'\b(\d{2}/\d{2}/\d{4})\b',text);mt=re.search(r'\b([0-2]\d:[0-5]\d)\b',text)
    teams=[clean(x.get_text(' ',strip=True)) for x in hero.select('h5 a.link-s-to-p')[:2]]
    if len(teams)!=2:teams=[base.get('home','CASA'),base.get('away','OSPITI')]
    score='';hg=ag=None
    for h3 in hero.find_all('h3'):
        sm=re.search(r'\b(\d+)\s*[-–]\s*(\d+)\b',clean(h3.get_text(' ',strip=True)))
        if sm:hg,ag=int(sm.group(1)),int(sm.group(2));score=f'{hg} - {ag}';break
    field_text=''
    for b in hero.find_all(['b','strong']):
        if clean(b.get_text(' ',strip=True)).lower().startswith('campo'):
            parent=b.parent;link=parent.find('a') if parent else None
            field_text=clean(link.get_text(' ',strip=True) if link else parent.get_text(' ',strip=True).split(':',1)[-1])
            break
    field,address=split_csi_venue(field_text or clean(f"{base.get('field','')} {base.get('address','')}"))
    logos=[]
    for i,image in enumerate(hero.select('span[class*="logo-squadra"] img')[:2]):
        src=urljoin(url,image.get('src',''));code=image.get('alt') or Path(urlparse(src).path).stem
        logos.append('/assets/ussa-logo.png' if 'USSA' in teams[i].upper() else cache_csi_logo(src,code))
    while len(logos)<2:logos.append(base.get('home_logo' if len(logos)==0 else 'away_logo',''))
    if md:
        try:base['date']=datetime.strptime(md.group(1),'%d/%m/%Y').date().isoformat()
        except:pass
    if mt:base['time']=mt.group(1)
    base.update({'url':url,'home':teams[0],'away':teams[1],'score':score or base.get('result',''),
                 'result':score or base.get('result',''),'result_home':hg if hg is not None else base.get('result_home'),
                 'result_away':ag if ag is not None else base.get('result_away'),'field':field,'address':address,
                 'route_address':clean(f'{field} {address}'),'home_logo':logos[0] or base.get('home_logo',''),
                 'away_logo':logos[1] or base.get('away_logo',''),'competition':'CSI','source_live':True,
                 'source_snapshot':False,'events':base.get('events') or [],'report':base.get('report') or ''})
    return base

@app.get('/api/game-detail')
def game_detail(url:str):
    parsed_url=urlparse(url)
    if parsed_url.scheme!='https' or parsed_url.netloc!='live.centrosportivoitaliano.it':
        raise HTTPException(400,'Link gara non valido')
    path=parsed_url.path
    static=next((x for x in U13_TEST_MATCHES if urlparse(x.get('detail_url','')).path==path),None)
    snapshots=load_json('u13_match_details.json',{})
    snap=snapshots.get(path)
    # U13 TEST è un campionato storico: il dettaglio viene servito da snapshot
    # verificati su CSI LIVE, così la experience non dipende dalla raggiungibilità
    # del sito CSI durante l'uso del totem.
    if snap:
        out=dict(snap)
        out['url']=url
        out['source_live']=False
        out['source_snapshot']=True
        return out
    if static:
        def row_for(name):
            key=clean(name).lower()
            return next((dict(r) for r in U13_TEST_STANDINGS if clean(r.get('team')).lower()==key),None)
        return {
            'url':url,'home':static['home'],'away':static['away'],'score':static.get('result',''),
            'date':static['date'],'time':static['time'],'round':static.get('round'),'competition':'CSI',
            'field':static.get('field',''),'overview':{'home':row_for(static['home']),'away':row_for(static['away']),'mode':'girone_csi'},
            'events':[],'report':'','source_live':False,'source_snapshot':True,
            'source_url':static.get('detail_url','')
        }
    cached,t,cache_row=cached_csi_match(path)
    base=dict(cached or {})
    if t:
        base.update({'team_label':t.get('label',t.get('key','')),
                     'competition_label':t.get('csi_competition_label',t.get('label','CSI')),
                     'group':t.get('csi_group','')})
    if cache_row:
        base['overview']={'home':standings_row(cache_row.get('standings'),base.get('home')),
                          'away':standings_row(cache_row.get('standings'),base.get('away')),
                          'mode':'girone_csi'}
    if base:
        base.update({'url':url,'score':base.get('result',''),'competition':'CSI','source_live':False,
                     'source_snapshot':True,'events':base.get('events') or [],'report':base.get('report') or ''})
        return base
    try:return parse_live_game_detail(soup(url),url,base)
    except Exception:pass
    raise HTTPException(404,'Gara CSI non trovata')


def geocode(address):
    """Geocoding robusto: Nominatim con query progressive, poi Photon."""
    queries=[]
    raw=str(address or '').strip()
    if raw in GEOCODE_CACHE:return GEOCODE_CACHE[raw]
    if raw:
        queries += [raw, raw + ', Lombardia, Italia', raw.replace('USSA Stadium, ', '')]
    seen=set()
    for q in queries:
        if not q or q in seen: continue
        seen.add(q)
        try:
            r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'json','limit':1,'countrycodes':'it','accept-language':'it'},headers=HEADERS,timeout=8)
            r.raise_for_status();a=r.json()
            if a:
                point=(float(a[0]['lat']),float(a[0]['lon']));GEOCODE_CACHE[raw]=point
                return point
        except Exception: pass
    try:
        r=requests.get('https://photon.komoot.io/api/',params={'q':raw,'limit':1},headers=HEADERS,timeout=8)
        r.raise_for_status();features=r.json().get('features') or []
        if features:
            lon,lat=features[0]['geometry']['coordinates'];point=(float(lat),float(lon));GEOCODE_CACHE[raw]=point;return point
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
        if f.get('competition') != competition or f.get('cancelled'): continue
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
    if fixture_id in ROUTE_RUNTIME_CACHE:return ROUTE_RUNTIME_CACHE[fixture_id]
    routes=load_json('routes.json',{})
    opponent=x.get('home') if 'USSA' in str(x.get('away','')).upper() else x.get('away')
    r=routes.get(opponent) or routes.get(x.get('route_address',''))
    if r and len(r.get('geometry') or []) >= 2:return r
    # I calendari CSI possono aggiungere o cambiare campi dopo la pubblicazione.
    # Se il percorso non è ancora nella cache statica, lo calcoliamo al bisogno
    # usando lo stesso servizio e lo stesso fallback già adottati dal totem.
    address=x.get('address') or x.get('route_address') or clean(f"{x.get('field','')} {x.get('address','')}")
    if not address:raise HTTPException(404,'Indirizzo non disponibile')
    result=route(address);ROUTE_RUNTIME_CACHE[fixture_id]=result
    return result

@app.get('/api/geocode')
def geocode_api(address:str):
    p=geocode(address)
    if not p: raise HTTPException(404,'Indirizzo non localizzato')
    return {'lat':p[0],'lon':p[1],'address':address}

@app.get('/api/route')
def route(address:str):
    hub=load_json('hub.json',{});stadium=hub.get('stadium',{});origin=stadium.get('address') or stadium.get('route_address')
    try:a=(float(stadium['lat']),float(stadium['lon']))
    except:a=geocode(origin)
    b=geocode(address)
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
    category=x.get('team_label') or x.get('competition_label') or x.get('competition') or 'USSA ROZZANO'
    summary=f"{category} · {x['home']} - {x['away']}"
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


# ===== V2.4.19 · INFO / ATLETI / MIGLIORE IN CAMPO =====
VOTE_DB=Path(os.getenv('VOTES_DB_PATH', str(ROOT/'votes.db')))

def vote_db():
    VOTE_DB.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(VOTE_DB)
    con.row_factory=sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id TEXT NOT NULL,
        team_key TEXT NOT NULL,
        athlete_id TEXT NOT NULL,
        athlete_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(fixture_id,team_key)
    )""")
    con.commit(); return con

def verify_pin(team_key,pin,admin=False):
    cfg=load_json('vote_pins.json',{})
    item=cfg.get('_admin' if admin else team_key)
    if not item or not pin:return False
    try:
        calc=hashlib.pbkdf2_hmac('sha256',str(pin).encode(),bytes.fromhex(item['salt']),120000).hex()
        return calc==item['hash']
    except:return False

def vote_fixture(fixture_id):
    x=fixture_by_id(fixture_id)
    if x:return x
    if fixture_id.startswith('csi_'):
        code=fixture_id[4:]
        for m in U13_TEST_MATCHES:
            if code in (m.get('detail_url') or ''):
                z=dict(m);z['id']=fixture_id;return z
    return None

def vote_unlock_at(x):
    try:return iso_dt(x['date'],x.get('time') or '00:00')+timedelta(minutes=45)
    except:return datetime.max

@app.get('/api/info')
def api_info(): return load_json('info.json',{})

@app.get('/api/team/{key}/athletes')
def team_athletes(key:str):
    if key not in teams_dict(): raise HTTPException(404)
    return {'team_key':key,'athletes':load_json('athletes.json',{}).get(key,[])}

@app.get('/api/qr/url.svg')
def qr_url(url:str=Query(...,min_length=1)):
    if not (url.startswith('https://') or url.startswith('http://') or url.startswith('mailto:')): raise HTTPException(400)
    return Response(qr_svg(url),media_type='image/svg+xml')

@app.get('/api/vote/{fixture_id}/{team_key}/status')
def vote_status(fixture_id:str,team_key:str,test:int=0):
    x=vote_fixture(fixture_id)
    if not x or team_key not in teams_dict(): raise HTTPException(404)
    unlock=vote_unlock_at(x);now=local_now();eligible=bool(test) or now>=unlock
    con=vote_db();row=con.execute('SELECT athlete_id,athlete_name,created_at FROM votes WHERE fixture_id=? AND team_key=?',(fixture_id,team_key)).fetchone();con.close()
    return {'eligible':eligible,'unlock_at':unlock.isoformat(timespec='minutes'),'voted':bool(row),'vote':dict(row) if row else None,'test_mode':bool(test)}

@app.post('/api/vote/{fixture_id}/{team_key}/unlock')
async def unlock_vote(fixture_id:str,team_key:str,request:Request,test:int=0):
    x=vote_fixture(fixture_id)
    if not x or team_key not in teams_dict(): raise HTTPException(404)
    body=await request.json();pin=str(body.get('pin') or '')
    if not verify_pin(team_key,pin): raise HTTPException(403,'PIN non valido')
    if not test and local_now()<vote_unlock_at(x): raise HTTPException(409,'Votazione non ancora disponibile')
    return {'ok':True}

@app.post('/api/vote/{fixture_id}/{team_key}')
async def cast_vote(fixture_id:str,team_key:str,request:Request,test:int=0):
    x=vote_fixture(fixture_id)
    if not x or team_key not in teams_dict(): raise HTTPException(404)
    body=await request.json(); pin=str(body.get('pin') or ''); athlete_id=str(body.get('athlete_id') or '')
    if not verify_pin(team_key,pin): raise HTTPException(403,'PIN non valido')
    if not test and local_now()<vote_unlock_at(x): raise HTTPException(409,'Votazione non ancora disponibile')
    athletes=load_json('athletes.json',{}).get(team_key,[]);a=next((z for z in athletes if z.get('id')==athlete_id),None)
    if not a: raise HTTPException(400,'Atleta non valido')
    con=vote_db()
    try:
        con.execute('INSERT INTO votes(fixture_id,team_key,athlete_id,athlete_name,created_at) VALUES(?,?,?,?,?)',(fixture_id,team_key,athlete_id,a.get('name') or 'NOME E COGNOME',local_now().isoformat(timespec='seconds')));con.commit()
    except sqlite3.IntegrityError:
        con.close();raise HTTPException(409,'Voto già registrato per questa gara')
    con.close();return {'ok':True}

@app.get('/api/backoffice/votes')
def backoffice_votes(pin:str,month:str|None=None):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    month=month or local_now().strftime('%Y-%m')
    con=vote_db();rows=con.execute("SELECT * FROM votes WHERE substr(created_at,1,7)=? ORDER BY created_at DESC",(month,)).fetchall()
    ranking=con.execute("SELECT team_key,athlete_id,athlete_name,COUNT(*) votes FROM votes WHERE substr(created_at,1,7)=? GROUP BY team_key,athlete_id,athlete_name ORDER BY votes DESC,athlete_name",(month,)).fetchall();con.close()
    return {'month':month,'votes':[dict(r) for r in rows],'ranking':[dict(r) for r in ranking]}

@app.get('/api/backoffice/csi-sync')
def backoffice_csi_sync_status(pin:str):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    return csi_sync_status()

@app.post('/api/backoffice/csi-sync')
def backoffice_csi_sync_run(pin:str):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    return refresh_csi_cache('manual')

@app.get('/api/backoffice/figc-sync')
def backoffice_figc_sync_status(pin:str):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    return figc_sync_status()

@app.post('/api/backoffice/figc-sync')
def backoffice_figc_sync_run(pin:str):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    return refresh_figc_cache('manual')

@app.get('/api/data-sync-status')
def public_data_sync_status():
    """Stato tecnico consultabile senza esporre PIN o dati riservati."""
    ensure_csi_refresh_if_due()
    ensure_figc_refresh_if_due()
    csi=csi_sync_status()
    figc=figc_sync_status()
    csi_keys=('status','running','last_attempt_at','last_success_at','next_run_at','source_count','updated_count','error_count','cached_teams')
    figc_keys=('status','running','last_attempt_at','last_success_at','next_run_at','updated_count','error_count','cached_fixtures','source_url')
    return {'server_time':rome_now().isoformat(timespec='seconds'),
            'csi':{k:csi.get(k) for k in csi_keys},
            'figc':{k:figc.get(k) for k in figc_keys}}

@app.get('/api/cron/daily-sync')
def cron_daily_sync():
    """Endpoint idempotente usato dal risveglio GitHub: aggiorna solo dati scaduti."""
    result={'server_time':rome_now().isoformat(timespec='seconds')}
    result['csi']=refresh_csi_cache('external-cron') if csi_cache_due() else csi_sync_status()
    result['figc']=refresh_figc_cache('external-cron') if figc_cache_due() else figc_sync_status()
    return result

@app.delete('/api/backoffice/votes/{vote_id}')
def delete_vote(vote_id:int,pin:str):
    if not verify_pin('',pin,admin=True): raise HTTPException(403,'PIN non valido')
    con=vote_db();cur=con.execute('DELETE FROM votes WHERE id=?',(vote_id,));con.commit();con.close();return {'ok':bool(cur.rowcount)}

@app.get('/backoffice')
def backoffice_page(): return FileResponse(ROOT/'backoffice.html')
