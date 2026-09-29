import numpy as np, pandas as pd
from math import sqrt, erf
# --- measured (Aug 3 - Sep 28, 2026, 40 sessions, SIP 1-min bars, regular hours) mean |return| in bps
M={'SPY':{1:1.54,5:3.46,15:5.97,30:8.62,60:11.39},'QQQ':{1:2.43,5:5.34,15:9.26,30:13.44,60:16.86}}
SD={'SPY':{1:2.19,5:4.81,15:8.38,30:12.04,60:15.57},'QQQ':{1:3.51,5:7.50,15:13.05,30:18.88,60:22.74}}
price={'SPY':766.4,'QQQ':716.6}
sec_fee_bps=20.60/1e6*1e4   # 0.206 bps on the sale
taf_bps={s:0.000195/price[s]*1e4 for s in price}
print('SEC fee bps',round(sec_fee_bps,3),' TAF bps',{s:round(v,4) for s,v in taf_bps.items()})
print('\nBREAK-EVEN round trip (bps and $/share), long trade, buy at ask / sell at bid')
rows=[]
for s in ['SPY','QQQ']:
    for cents in [1,2,3,4]:
        spr=cents/100/price[s]*1e4
        tot=spr+sec_fee_bps+taf_bps[s]
        rows.append((s,cents,round(spr,3),round(tot,3),round(tot/1e4*price[s],4)))
print(pd.DataFrame(rows,columns=['sym','spread_c','spread_bps','round_trip_bps_incl_SEC','dollars_per_share']).to_string(index=False))
print('\nHit rate needed to break even p = 0.5 + C/(2*M)  [M = mean |move| over holding period]')
out=[]
for s in ['SPY','QQQ']:
    for h in [1,5,15,30,60]:
        r={'sym':s,'horizon_min':h,'mean_abs_move_bps':M[s][h]}
        for C in [0.47,1.0,3.0]:
            p=0.5+C/(2*M[s][h])
            r[f'C={C}']= f'{p*100:.0f}%' if p<=1 else 'impossible'
        out.append(r)
print(pd.DataFrame(out).to_string(index=False))
print('\nCost as % of the mean move: C=0.47,1.0 ; mean |move|')
for s in ['SPY','QQQ']:
    print(s,{h:(round(0.47/M[s][h]*100),round(1.0/M[s][h]*100)) for h in M[s]})
# --- power: N needed to detect net mean mu with per-trade sd sigma
z_a=1.96; z_b=0.84; z_strict=3.12
print('\nTrades needed to detect a true NET edge mu (80% power): lenient (p<.05) / strict (p<.0018)')
res=[]
for s in ['SPY']:
    for h in [1,5,30]:
        sg=SD[s][h]
        for mu in [0.25,0.5,1.0]:
            n1=((z_a+z_b)*sg/mu)**2; n2=((z_strict+z_b)*sg/mu)**2
            res.append((s,h,sg,mu,round(n1),round(n2),round(n1/250,1),round(n2/250,1)))
print(pd.DataFrame(res,columns=['sym','horizon','sd_bps','edge_bps','N_lenient','N_strict','years_at_250/yr_lenient','years_strict']).to_string(index=False))
print('\nMinimum detectable mean (80% power, 5%) for N trades at 30-min sd 12.0:')
for N in [60,100,250,500,2300]:
    print(N, round((z_a+z_b)*12.04/sqrt(N),2),'bps')
# --- effect size to bps
print('\nPublished effect R2 -> rho -> hit rate -> gross bps/trade using SPY last-30 sd 10.4')
for r2 in [0.017,0.026,0.029]:
    rho=sqrt(r2); hit=0.5+np.arcsin(rho)/np.pi; g=sqrt(2/np.pi)*rho*10.4
    print(f'R2={r2:.3f} rho={rho:.3f} hit={hit*100:.1f}% gross={g:.2f} bps/trade')
# bid-ask mid vs. autocorr edge
for lab,ac,sd in [('1-min lag1 autocorr -0.016 SPY',0.016,2.19),('5-min lag1 autocorr -0.05 SPY',0.05,4.81)]:
    print(lab,'-> max gross edge/trade',round(sqrt(2/np.pi)*ac*sd,3),'bps')
