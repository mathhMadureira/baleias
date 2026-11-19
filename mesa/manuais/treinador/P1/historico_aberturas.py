import json,subprocess,datetime as dt
U=dt.timezone.utc
revs=subprocess.run(['git','log','--reverse','--format=%H %ct','--since=2026-11-16 18:00','origin/estado','--','dados/robo_v4_cacador.json'],capture_output=True,text=True).stdout.split('\n')
vistos={};abertas_vistas={}
for l in revs:
    if not l: continue
    h,t=l.split();t=int(t)
    try: e=json.loads(subprocess.run(['git','show',f'{h}:dados/robo_v4_cacador.json'],capture_output=True,text=True).stdout)
    except Exception: continue
    for p,o in e.get('abertas',{}).items():
        k=(o['moeda'],o['entrada_t'])
        abertas_vistas.setdefault(k,t)
    for o in e.get('fechadas',[]):
        k=(o['moeda'],o['entrada_t'],o['saida_t'])
        vistos.setdefault(k,(t,e.get('inicio'),len(e['fechadas'])))
json.dump({'fech':[[*k,*v] for k,v in vistos.items()],'ab':[[*k,v] for k,v in abertas_vistas.items()]},open('/tmp/treinador_hist_robo_v4_cacador.json','w'))
print(len(revs),len(vistos),len(abertas_vistas))
