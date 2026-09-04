from pathlib import Path
import json, time, requests

ROOT=Path(__file__).resolve().parent
ROUTES=ROOT/'routes.json'
API='https://router.project-osrm.org/route/v1/driving/{a};{b}?overview=full&geometries=geojson'

def main():
    data=json.loads(ROUTES.read_text())
    ok=0; fail=[]
    for name,r in data.items():
        o=r.get('origin',{}); d=r.get('destination',{})
        if not all(k in o for k in ('lon','lat')) or not all(k in d for k in ('lon','lat')):
            fail.append(name); continue
        url=API.format(a=f"{o['lon']},{o['lat']}",b=f"{d['lon']},{d['lat']}")
        try:
            res=requests.get(url,timeout=20,headers={'User-Agent':'USSA-Smart-Hub/2.4.5'})
            res.raise_for_status(); js=res.json(); route=js['routes'][0]
            geom=route['geometry']['coordinates']
            if len(geom)<3: raise RuntimeError('geometry too short')
            r['geometry']=geom
            r['km']=round(route['distance']/1000,1)
            r['minutes']=max(1,round(route['duration']/60))
            r['mode']='static_osrm_road_route'
            r['note']='Percorso stradale indicativo pre-generato al deploy; non considera traffico o chiusure temporanee.'
            ok+=1
        except Exception as e:
            # Never write an invented straight line. Keep map unavailable rather than misleading.
            r['geometry']=[]
            r['mode']='route_build_failed'
            r['note']='Percorso stradale non generato in fase di deploy.'
            fail.append(name)
        time.sleep(.15)
    ROUTES.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(f'Route stradali generate: {ok}/{len(data)}')
    if fail: print('Non generate:', ', '.join(fail))

if __name__=='__main__': main()
