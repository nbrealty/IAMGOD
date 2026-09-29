import pandas as pd, numpy as np
for sym in ['SPY','QQQ']:
    df=pd.read_pickle(f'{sym}_df.pkl')
    df['bucket']=df['ts'].dt.floor('30min').dt.strftime('%H:%M')
    df['ret1']=df.groupby('date')['close'].transform(lambda s: np.log(s).diff())*1e4
    df['rng']=(df.high-df.low)/df.close*1e4
    tot=df.groupby('date')['volume'].transform('sum')
    df['vshare']=df.volume/tot
    g=df.groupby('bucket').agg(vol_share_pct=('vshare',lambda s:s.sum()/df.date.nunique()*100),mean_abs_ret1=('ret1',lambda s:s.abs().mean()),mean_bar_range=('rng','mean'))
    print(sym); print(g.round(2).to_string())
    # first and last minute volume shares
    f=df[df.t=='09:30'].vshare.mean()*100; l=df[df.t=='15:59'].vshare.mean()*100
    print('  share of day volume: 09:30 bar %.1f%%, 15:59 bar %.1f%%'%(f,l))
