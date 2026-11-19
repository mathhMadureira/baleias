# Tabela das operações fechadas dos agentes (H61/H62) no ramo estado. Uso: python3 agentes_tab.py
import json, subprocess, collections, time
H62 = 1795034280  # 18/11 20:38 UTC
def load(f):
    return json.loads(subprocess.check_output(['git','-C','/home/servidor-de-producao/baleias','show','origin/estado:dados/%s.json'%f]))
rows=[]
for ag,f in [('claude','robo_claude'),('testnet','robo_openbot_testnet'),('treinador','agente_treinador'),('guardiao','agente_guardiao'),('laboratorio','agente_laboratorio')]:
    d=load(f)
    for o in d['fechadas']:
        o=dict(o); o['ag']=ag; rows.append(o)
def pf(xs):
    g=sum(x for x in xs if x>0); l=-sum(x for x in xs if x<0)
    return round(g/l,2) if l>0 else None
def tab(nome,key,rs):
    grp=collections.defaultdict(list)
    for o in rs: grp[key(o)].append(o['resultado_usd'])
    print('--',nome)
    for k,v in sorted(grp.items(),key=lambda kv:str(kv[0])):
        print('  %-40s n=%3d ganhos=%3d soma=%+.3f fator=%s'%(str(k)[:40],len(v),sum(1 for x in v if x>0),sum(v),pf(v)))
for rotulo,rs in [('desde H62 (sem testnet)',[o for o in rows if o['entrada_t']>=H62 and o['ag']!='testnet']),('desde H62 testnet',[o for o in rows if o['entrada_t']>=H62 and o['ag']=='testnet'])]:
    print('=====',rotulo,len(rs),'ops; ultima saida',time.strftime('%d/%m %H:%M',time.gmtime(max([o['saida_t'] for o in rs] or [0]))))
    tab('agente',lambda o:o['ag'],rs)
    tab('motivo saida',lambda o:(o.get('motivo_saida') or o.get('motivo','?')).split(' ')[0]+' '+(o.get('motivo_saida') or 'x ?').split(' ')[1],rs)
    tab('lado',lambda o:o['lado'],rs)
    tab('alvo_pct',lambda o:o.get('alvo_pct'),rs)
    tab('stop_pct',lambda o:o.get('stop_pct'),rs)
    tab('segurando',lambda o:'<30' if o['saida_t']-o['entrada_t']<1800 else ('30-120' if o['saida_t']-o['entrada_t']<7200 else '>=120'),rs)
    tab('hora UTC',lambda o:int(time.gmtime(o['entrada_t']).tm_hour//6*6),rs)
