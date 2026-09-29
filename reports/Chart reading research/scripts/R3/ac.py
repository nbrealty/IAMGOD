import pandas as pd, numpy as np
for sym in ['SPY','QQQ']:
    df=pd.read_pickle(f'{sym}_df.pkl')
    # 1-min autocorr within day
    r=df.groupby('date')['close'].apply(lambda s: np.log(s).diff()).dropna()*1e4
    r1=df.assign(r=df.groupby('date')['close'].transform(lambda s: np.log(s).diff())*1e4).dropna(subset=['r'])
    x=r1.groupby('date')['r'].apply(lambda s: pd.Series({'a1':s.autocorr(1),'a2':s.autocorr(2),'a3':s.autocorr(3)})).unstack()
    print(sym,'1-min return autocorr (mean over days) lag1 %.3f lag2 %.3f lag3 %.3f ; SE approx %.3f'%(x.a1.mean(),x.a2.mean(),x.a3.mean(), 1/np.sqrt(len(r1))))
    # 5-min non-overlapping returns
    out=[]
    for d,g in df.groupby('date'):
        c=g.set_index('ts')['close']
        c5=c.resample('5min',label='right',closed='right').last().dropna()
        rr=np.log(c5).diff().dropna()*1e4
        out.append(rr)
    a=[s.autocorr(1) for s in out]; n=sum(len(s) for s in out)
    print('   5-min autocorr lag1 mean over days %.3f (n=%d, SE~%.3f)'%(np.mean(a),n,1/np.sqrt(n)))
    # last 30 min return sd (15:30 close->16:00 close), first-30 (open->10:00 close)
    piv=df.pivot_table(index='date',columns='t',values='close')
    o=df.groupby('date')['open'].first()
    c1000=piv['09:59']; c1530=piv['15:29']; cl=piv['15:59']
    first30=np.log(c1000/o)*1e4
    last30=np.log(cl/c1530)*1e4
    print('   first30 sd %.1f bps ; last30 sd %.1f bps ; mean|last30| %.1f ; corr(first30,last30) over %d days = %.2f'%(first30.std(),last30.std(),last30.abs().mean(),len(last30),np.corrcoef(first30,last30)[0,1]))
    rod=np.log(c1530/o)*1e4
    print('   corr(rest-of-day(open->15:30), last30) = %.2f'%np.corrcoef(rod,last30)[0,1])
    print('   expected gross per trade if rho=0.13: %.2f bps ; rho=0.16: %.2f bps'%(0.798*0.13*last30.std(),0.798*0.16*last30.std()))
