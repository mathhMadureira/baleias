import json,datetime as dt
U=dt.timezone.utc
H=json.load(open('/tmp/treinador_hist.json')); ab={(a[0],a[1]):a[2] for a in H['ab']}
d=json.load(open('/tmp/treinador_cacador.json')); M=json.load(open('/tmp/treinador_velas/min.json'))
X=[o for o in d['fechadas'] if ab[(o['moeda'],o['entrada_t'])]-o['entrada_t']<=1800]
rows=[]
for o in X:
    k=M[f"{o['moeda']}|{o['entrada_t']}"]; s=o['entrada_t']*1000; v=o['lado']=='venda'; E=o['entrada']
    arm=None; mae=0
    for x in k:
        if x[0]<s: continue
        fav=(E-x[3])/E if v else (x[2]-E)/E
        adv=(x[2]-E)/E if v else (E-x[3])/E
        if arm is None: mae=max(mae,adv)
        if fav>=0.005 and arm is None: arm=(x[0]-s)/60000+1
    rows.append((o,arm,mae,k))
print('| moeda | lado | motivo | min até armar | pior contra antes de armar | segurou h | US$ |')
for o,arm,mae,k in sorted(rows,key=lambda r:(r[1] is None, r[1] or 0)):
    print(f"| {o['moeda']} | {o['lado']} | {o['motivo'][:22]} | {arm if arm else '—'} | {mae*100:.2f}% | {(o['saida_t']-o['entrada_t'])/3600:.1f} | {o['resultado_usd']:+.3f} |")
def cf(T):
    tot=0;mud=[]
    for o,arm,mae,k in rows:
        s=o['entrada_t']*1000; fim=s+T*60000
        if o['saida_t']*1000<=fim or (arm is not None and arm<=T):
            tot+=o['resultado_usd'];continue
        c=[x for x in k if x[0]<fim]
        px=c[-1][4]; noc=o.get('nocional',25.0); sg=-1 if o['lado']=='venda' else 1
        r=noc*sg*(px/o['entrada']-1)-0.0012*noc
        tot+=r; mud.append((o['moeda'],round(o['resultado_usd'],3),round(r,3)))
    return tot,mud
for T in (30,60,120):
    t,m=cf(T); print(T,'min: soma',round(t,3),'mudadas',len(m),m)
