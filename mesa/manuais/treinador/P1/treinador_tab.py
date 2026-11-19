import json,datetime as dt,collections as C,sys
U=dt.timezone.utc
H=json.load(open('/tmp/treinador_hist.json'))
ab={(a[0],a[1]):a[2] for a in H['ab']}
d=json.load(open('/tmp/treinador_cacador.json'))
F=d['fechadas']
for o in F:
    o['atraso']=(ab[(o['moeda'],o['entrada_t'])]-o['entrada_t'])/3600
    o['c']=abs(o['prob']-.5)
    o['h']=(o['saida_t']-o['entrada_t'])/3600
    o['pct']=o['resultado_usd']/o.get('nocional',25.0)*100
    m=o['motivo']
    o['mot']='stop móvel' if 'móvel' in m else 'stop 2%' if 'segurança' in m else 'tendência virou' if 'tendência' in m else 'guarda do dia' if 'guarda' in m else '24 h' if 'máximo' in m else m
def tab(nome,grupos):
    print(f'\n| {nome} | n | ganhos | soma US$ | média %/op | fator |')
    print('|---|---|---|---|---|---|')
    for g,L in grupos:
        if not L: continue
        w=sum(o['resultado_usd'] for o in L if o['resultado_usd']>0); l=-sum(o['resultado_usd'] for o in L if o['resultado_usd']<0)
        print(f"| {g} | {len(L)} | {sum(o['resultado_usd']>0 for o in L)} | {sum(o['resultado_usd'] for o in L):+.3f} | {sum(o['pct'] for o in L)/len(L):+.3f} | {w/l if l else float('inf'):.2f} |")
vel=[o for o in F if o['atraso']>0.5]; ok=[o for o in F if o['atraso']<=0.5]
tab('conjunto',[('todas',F),('sinal velho (atraso > 30 min)',vel),('limpas (atraso ≤ 30 min)',ok)])
X=ok
def grp(key,order=None):
    g=C.defaultdict(list)
    for o in X: g[key(o)].append(o)
    return [(k,g[k]) for k in (order or sorted(g))]
tab('motivo de saída (limpas)',grp(lambda o:o['mot']))
tab('lado (limpas)',grp(lambda o:o['lado']))
tab('confiança (limpas)',grp(lambda o:'<0,12' if o['c']<.12 else '0,12–0,15' if o['c']<.15 else '≥0,15'))
tab('hora UTC da entrada (limpas)',grp(lambda o:'%02d–%02d'%(dt.datetime.fromtimestamp(o['entrada_t'],U).hour//6*6,dt.datetime.fromtimestamp(o['entrada_t'],U).hour//6*6+6)))
tab('tempo segurando (limpas)',grp(lambda o:'<30 min' if o['h']<.5 else '30 min–2 h' if o['h']<2 else '≥2 h',['<30 min','30 min–2 h','≥2 h']))
tab('dia UTC da saída (limpas)',grp(lambda o:dt.datetime.fromtimestamp(o['saida_t'],U).strftime('%d/11')))
print('\npico das perdas (limpas):',[(o['moeda'],round(o['pico']*100,2),round(o['resultado_usd'],3),o['mot']) for o in X if o['resultado_usd']<0])
print('pico dos ganhos min/med:',min(o['pico'] for o in X if o['resultado_usd']>0), sorted(o['pico'] for o in X if o['resultado_usd']>0)[len([1 for o in X if o['resultado_usd']>0])//2])
print('custo/op US$ médio', sum(o.get('nocional',25.0)*0.0012 for o in X)/len(X))
