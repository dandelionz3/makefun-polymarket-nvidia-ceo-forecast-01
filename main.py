# Robust random-walk quantiles use recent minute moves, with empirical tails and a shrunk drift.
# Cross-market medians are recentered to preserve the checkpoint's total probability mass.
# The program reads every .in file in MAKEFUN_INPUT_DIR (or /input) and writes matching .out files.
# It uses only Python's standard library and produces deterministic, compact JSON.
# Run locally with: MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
# The development-only practice comparison is: python3 score.py
# Each market forecast uses at most 360 recent increments and a 240-minute horizon.
# Outputs contain five ordered quantiles for each forecast minute, rounded to six decimals.
import json, math, os
INPUT_DIR=os.environ.get('MAKEFUN_INPUT_DIR','/input'); OUTPUT_DIR=os.environ.get('MAKEFUN_OUTPUT_DIR','/output')
def median(v):
 s=sorted(v); n=len(s)
 if not n:return 0.0
 k=n//2; return s[k] if n%2 else (s[k-1]+s[k])*0.5
def empirical(v,p):
 s=sorted(v)
 if len(s)==1:return s[0]
 pos=(len(s)-1)*p; k=int(pos); f=pos-k
 return s[k]*(1-f)+s[min(k+1,len(s)-1)]*f
def price6(v):return round(min(1.0,max(0.0,v))*1_000_000)/1_000_000+0.0
def market_forecast(m,H):
 p=m['prices']; x=p[-1]; d=[p[i+1]-p[i] for i in range(len(p)-1)]; r=d[-360:] or [0.0]
 center=median(r); robust=1.4826*median([abs(v-center) for v in r]); rms=math.sqrt(sum(v*v for v in r)/len(r))
 sigma=max(0.0005,min(0.02,0.6*rms+0.4*robust)); e05,e25,e75,e95=[empirical(r,t) for t in (0.05,0.25,0.75,0.95)]
 out=[]
 for h in range(1,H+1):
  root=math.sqrt(h)
  def lo(e,z):return -min(2*sigma*root,max(abs(e)*root,z*sigma*root))
  def hi(e,z):return min(2*sigma*root,max(abs(e)*root,z*sigma*root))
  row=[x+lo(e05,1.644854),x+lo(e25,0.67449),x,x+hi(e75,0.67449),x+hi(e95,1.644854)]; row.sort(); out.append(row)
 return out
def main():
 os.makedirs(OUTPUT_DIR,exist_ok=True)
 for fn in sorted(n for n in os.listdir(INPUT_DIR) if n.endswith('.in')):
  with open(os.path.join(INPUT_DIR,fn),encoding='utf-8') as f:c=json.load(f)
  ms=c['markets']; H=c['horizon_minutes']; qs=[market_forecast(m,H) for m in ms]; total=sum(m['prices'][-1] for m in ms)
  for h in range(H):
   old=[qs[i][h][2] for i in range(len(ms))]; sm=sum(old); new=[min(1.0,max(0.0,v*total/sm)) for v in old] if sm else old
   for i,x in enumerate(old):
    row=[min(1.0,max(0.0,q+new[i]-x)) for q in qs[i][h]]; row.sort(); qs[i][h]=[price6(q) for q in row]
  with open(os.path.join(OUTPUT_DIR,fn[:-3]+'.out'),'w',encoding='utf-8') as f:json.dump({'forecasts':[{'id':m['id'],'q':qs[i]} for i,m in enumerate(ms)]},f,separators=(',',':'),allow_nan=False);f.write('\n')
if __name__=='__main__':main()
