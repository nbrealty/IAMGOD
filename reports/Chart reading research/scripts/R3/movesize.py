import pandas as pd, numpy as np, glob, gzip
base='/home/user/IAMGOD/trading/state/scalp_cache/'
out=[]
for sym in ['SPY','QQQ']:
    dfs=[pd.read_csv(f,parse_dates=['ts']) for f in sorted(glob.glob(base+f'{sym}_2026*.csv.gz'))]
    df=pd.concat(dfs).drop_duplicates('ts').sort_values('ts')
    df['ts']=df['ts'].dt.tz_convert('America/New_York')
    df['date']=df['ts'].dt.date
    df['t']=df['ts'].dt.strftime('%H:%M')
    # regular hours
    df=df[(df.t>='09:30')&(df.t<'16:00')].copy()
    print(sym,'rows',len(df),'days',df.date.nunique(),'first',df.date.min(),'last',df.date.max(), 'price median',df.close.median())
    # 1-min close-to-close return within day (bps)
    df['ret1']=df.groupby('date')['close'].transform(lambda s: np.log(s).diff())*1e4
    a=df['ret1'].dropna().abs()
    print(' 1-min |ret| bps: median %.2f mean %.2f p75 %.2f p90 %.2f p99 %.2f ; sd %.2f'%(a.median(),a.mean(),a.quantile(.75),a.quantile(.9),a.quantile(.99),df['ret1'].std()))
    # 1-min bar range
    df['rng']=(df.high-df.low)/df.close*1e4
    print(' 1-min high-low range bps: median %.2f mean %.2f p90 %.2f'%(df.rng.median(),df.rng.mean(),df.rng.quantile(.9)))
    # 5-min returns
    d5=[]
    for d,g in df.groupby('date'):
        c=g.set_index('ts')['close'].resample('5min',label='right',closed='right').last().dropna()
        r=np.log(c).diff().dropna()*1e4
        d5.append(r)
    r5=pd.concat(d5)
    print(' 5-min |ret| bps: median %.2f mean %.2f p90 %.2f sd %.2f'%(r5.abs().median(),r5.abs().mean(),r5.abs().quantile(.9),r5.std()))
    # 15 and 30-min
    for m in [15,30,60]:
        dd=[]
        for d,g in df.groupby('date'):
            c=g.set_index('ts')['close'].resample(f'{m}min',label='right',closed='right').last().dropna()
            r=np.log(c).diff().dropna()*1e4
            dd.append(r)
        rr=pd.concat(dd)
        print(f' {m}-min |ret| bps: median %.2f mean %.2f sd %.2f'%(rr.abs().median(),rr.abs().mean(),rr.std()))
    # daily
    daily=df.groupby('date').agg(o=('open','first'),c=('close','last'),h=('high','max'),l=('low','min'))
    daily['oc']=np.log(daily.c/daily.o)*1e4
    daily['hl']=np.log(daily.h/daily.l)*1e4
    print(' daily open-close |bps|: median %.1f mean %.1f ; daily H-L range bps median %.1f mean %.1f'%(daily.oc.abs().median(),daily.oc.abs().mean(),daily.hl.median(),daily.hl.mean()))
    # by time-of-day mean abs 1-min ret
    tod=df.groupby('t')['ret1'].apply(lambda s: s.abs().mean())
    for t in ['09:31','09:35','10:00','11:00','12:00','13:00','14:00','15:00','15:30','15:45','15:59']:
        print('  ',t,'mean|ret1| %.2f'%tod.get(t,np.nan))
    print(' realized vol ann (from 1-min): %.1f%%'%(df['ret1'].std()/1e4*np.sqrt(252*390)*100))
    df.to_pickle(f'{sym}_df.pkl')
