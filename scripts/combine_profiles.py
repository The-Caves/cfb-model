"""Build a single, provenance-aware 2026 research profile from validated inputs.

Strict team, season and as-of joins; missing advanced features remain missing.
This is NOT a trained predictive model nor proof of historical pregame features.
"""
import argparse,csv,datetime as dt,json
from pathlib import Path

CORE_SKIP={"epa_offense","epa_defense"}
ADV_SKIP={"team","season","asof_exclusive","betting_status"}
ADV_RENAME={"games_covered":"pbp_games_covered","source":"advanced_source",
            "source_retrieved_utc":"advanced_source_retrieved_utc"}

def rows(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        header=reader.fieldnames or []
        if not {"team","season","asof_exclusive","betting_status"}.issubset(set(header)):
            raise ValueError("Profile missing required fields: "+str(path))
        contents=list(reader)
    unique={}
    for row in contents:
        team=row["team"].strip()
        if not team or team in unique:raise ValueError("Blank/duplicate team: "+team)
        if row["season"]!="2026":raise ValueError("Wrong profile season: "+team)
        dt.date.fromisoformat(row["asof_exclusive"])
        unique[team]=row
    if not unique:raise ValueError("Empty team profiles")
    return header,unique

def combine(score_path,advanced_path,out,expected_teams=138):
    sh,score=rows(score_path)
    ah,advanced=rows(advanced_path)
    if score.keys()!=advanced.keys():
        missing_score=sorted(advanced.keys()-score.keys())
        missing_adv=sorted(score.keys()-advanced.keys())
        raise ValueError(f"Team registries disagree; missing score={missing_score}, missing advanced={missing_adv}")
    if expected_teams is not None and len(score)!=expected_teams:
        raise ValueError(f"Expected {expected_teams} profiles; got {len(score)}")
    dates={r["asof_exclusive"] for r in score.values()}|{r["asof_exclusive"] for r in advanced.values()}
    if len(dates)!=1:raise ValueError("Profile as-of cutoffs differ")
    asof=dates.pop()
    if dt.date.fromisoformat(asof).year!=2026:raise ValueError("Profiles must be for 2026")
    base=[k for k in sh if k not in CORE_SKIP]
    cols=[ADV_RENAME.get(k,k) for k in ah if k not in ADV_SKIP]
    if len(set(base+cols))!=len(base+cols):raise ValueError("Duplicate enriched fields")
    fields=base+cols+["profile_quality","research_status"]
    merged=[]
    for team in sorted(score):
        a=advanced[team];s=score[team]
        d={k:s[k] for k in base}
        for k in ah:
            if k not in ADV_SKIP:d[ADV_RENAME.get(k,k)]=a[k]
        if a["betting_status"]!="PASS_UNVALIDATED" or s["betting_status"]!="PASS_UNVALIDATED":
            raise ValueError("Unvalidated gate not enforced for "+team)
        # PBP coverage is separate from score-game coverage; don't claim
        # missing advanced games imply missing team or injured players.
        d["profile_quality"]="SCORE_PLUS_RETROSPECTIVE_ADVANCED" if int(a["games_covered"] or 0)>0 else "SCORE_ONLY_ADVANCED_UNAVAILABLE"
        d["research_status"]="PASS_UNVALIDATED"
        merged.append(d)
    output=Path(out);output.mkdir(parents=True,exist_ok=True)
    with (output/"team_profiles_2026_enriched.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(merged)
    qa={"status":"RESEARCH_PROFILE_MERGE_COMPLETE","season":2026,"asof_exclusive":asof,
        "teams":len(merged),"teams_with_advanced":sum(bool(r.get("off_epa_per_play")) for r in merged),
        "source_score_profiles":str(score_path),"source_advanced_profiles":str(advanced_path),
        "data_publication_timestamp_verified":False,"safe_for_betting":False,
        "warnings":["Retrospective advanced dataset can include later provider corrections.",
                    "No historical pregame injury or market data. No model validated."]}
    (output/"enriched_manifest.json").write_text(json.dumps(qa,indent=2)+"\n")
    return qa

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--scores",default="data/team_profiles_2026.csv")
    p.add_argument("--advanced",default="data/advanced/team_profiles_advanced_2026.csv")
    p.add_argument("--output",default="data/enriched")
    p.add_argument("--expected-teams",type=int,default=138)
    a=p.parse_args()
    print(json.dumps(combine(a.scores,a.advanced,a.output,a.expected_teams),indent=2))
