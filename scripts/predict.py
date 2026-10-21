"""Experimental score-only opponent-adjusted ridge baseline; no validated betting recommendations."""
import argparse,csv,json,math,datetime
import numpy as np
def fit_predict(games,away,home,asof,alpha=15,decay=.9,cap=28):
    past=[r for r in games if r["date"]<asof]
    if not past:raise ValueError("No historical games before asof")
    names=sorted({x for r in past for x in (r["home"],r["away"])})
    if away not in names or home not in names:raise ValueError("Team absent from training games")
    ids={t:i for i,t in enumerate(names)};n=len(names)
    x=[];y=[];weights=[]
    last=max(r["date"] for r in past)
    for r in past:
        age=(datetime.date.fromisoformat(last)-datetime.date.fromisoformat(r["date"])).days
        weight=decay**(age/7)
        h=float(r["home_score"]);a=float(r["away_score"]);diff=h-a
        if abs(diff)>cap:
            avg=(h+a)/2;h=avg+math.copysign(cap/2,diff);a=avg-math.copysign(cap/2,diff)
        neutral=str(r.get("neutral","")).lower() in ("true","1")
        for offense,defense,points,site in ((r["home"],r["away"],h,0 if neutral else .5),(r["away"],r["home"],a,0 if neutral else -.5)):
            row=np.zeros(n*2+1);row[ids[offense]]=1;row[n+ids[defense]]=1;row[-1]=site
            x.append(row);y.append(points);weights.append(weight)
    X=np.asarray(x);Y=np.asarray(y);W=np.sqrt(np.asarray(weights))
    mu=np.average(Y,weights=weights)
    penalty=np.diag(np.r_[np.full(2*n,alpha),60.])
    b=np.linalg.solve((X*W[:,None]).T@(X*W[:,None])+penalty,(X*W[:,None]).T@((Y-mu)*W))
    def score(o,d,site):return mu+b[ids[o]]+b[n+ids[d]]+b[-1]*site
    hs=score(home,away,.5);aws=score(away,home,-.5)
    return {"status":"PASS_UNVALIDATED","asof_exclusive":asof,"training_games":len(past),
       "away":away,"home":home,"home_score_projection":round(float(hs),2),
       "away_score_projection":round(float(aws),2),"home_margin":round(float(hs-aws),2),
       "total":round(float(hs+aws),2),
       "limitations":"Score-only; injuries, EPA, odds, and out-of-sample betting validation missing"}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",default="data/games_2026.csv")
    p.add_argument("--away",required=True);p.add_argument("--home",required=True)
    p.add_argument("--asof",required=True);a=p.parse_args()
    with open(a.games,newline="") as f:rows=list(csv.DictReader(f))
    print(json.dumps(fit_predict(rows,a.away,a.home,a.asof),indent=2))
