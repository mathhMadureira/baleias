import json,urllib.request,time,os
H=json.load(open('/tmp/treinador_hist.json'))
ab={(a[0],a[1]):a[2] for a in H['ab']}
d=json.load(open('/tmp/treinador_cacador.json'))
out={}
for o in d['fechadas']:
    if ab[(o['moeda'],o['entrada_t'])]-o['entrada_t']>1800: continue
    s=int(o['entrada_t']*1000); e=int(o['saida_t']*1000)+60000
    ks=[];t=s
    while t<e:
        u=f"https://api.binance.com/api/v3/klines?symbol={o['moeda']}&interval=1m&startTime={t}&endTime={e}&limit=1000"
        try:
            with urllib.request.urlopen(u,timeout=20) as r: k=json.load(r)
        except Exception as x:
            print('erro',o['moeda'],x);k=[]
        if not k: break
        ks+= [[x[0],float(x[1]),float(x[2]),float(x[3]),float(x[4])] for x in k]; t=k[-1][0]+60000
        time.sleep(0.1)
    out[f"{o['moeda']}|{o['entrada_t']}"]=ks
json.dump(out,open('/tmp/treinador_velas/min.json','w'))
print(len(out),sum(1 for v in out.values() if v))
