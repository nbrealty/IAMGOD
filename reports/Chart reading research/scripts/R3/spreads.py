import json, pandas as pd, numpy as np
base='/home/user/IAMGOD/trading/state/scalp/quote_cache/'
for sym in ['SPY','QQQ']:
    d=json.load(open(base+f'{sym}_2026-09-28.json'))
    rows=[]
    for k,v in d.items():
        rows.append((pd.Timestamp(k),v[0],v[1],v[2],v[3]))
    df=pd.DataFrame(rows,columns=['ts','bid','ask','bsz','asz']).sort_values('ts')
    df=df[(df.ask>df.bid)&(df.bid>0)]
    df['spr']=(df.ask-df.bid)
    df['mid']=(df.ask+df.bid)/2
    df['bps']=df.spr/df.mid*1e4
    df['bucket']=df.ts.dt.floor('30min').dt.strftime('%H:%M')
    print(sym,'quotes',len(df),'first',df.ts.min(),'last',df.ts.max())
    print(' overall spread cents: median %.1f mean %.2f p90 %.1f p99 %.1f max %.1f ; share at 1c: %.0f%%, 2c: %.0f%%, >=3c: %.0f%%'%(
        df.spr.median()*100,df.spr.mean()*100,df.spr.quantile(.9)*100,df.spr.quantile(.99)*100,df.spr.max()*100,
        (df.spr.round(2)==0.01).mean()*100,(df.spr.round(2)==0.02).mean()*100,(df.spr.round(2)>=0.03).mean()*100))
    print(' overall spread bps: median %.3f mean %.3f'%(df.bps.median(),df.bps.mean()))
    g=df.groupby('bucket').agg(n=('spr','size'),med_c=('spr',lambda s:s.median()*100),mean_c=('spr',lambda s:s.mean()*100),mean_bps=('bps','mean'))
    print(g.round(2).to_string())
