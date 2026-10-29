"""2026 SportsDataverse PBP/drive ingest; retrospective research, never betting clearance.

Join by ESPN game id AND final scores, require completed prior games,
quarantine inconsistent or incomplete games, and preserve observed missingness.
Provider release files are retrospectively mutable; retrieved_at != published_at.
"""
import argparse,csv,datetime as dt,hashlib,json,math,urllib.request
from collections import Counter,defaultdict
from pathlib import Path
from scripts.qb_passer_history import collect as collect_qb_passers, FIELDS as QB_PASSER_FIELDS

PBP_URL="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_2026.parquet"
DRIVE_URL="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_adv_drives/adv_drives_2026.parquet"
COLS=["season","game_id","pos_team_id","homeTeamId","awayTeamId","homeFinalScore","awayFinalScore",
      "status_type_completed","pass","rush","EPA","EPA_scrimmage","EPA_success","success",
      "statYardage","start.yardsToEndzone","down","qb_hurry","sack","passer_player_name",
      "drive.id","turnover_vec"]
DRIVE_COLS=["season","game_id","pos_team","drives","yards_per_drive","plays_per_drive",
            "avg_field_position","drive_total_gained_yards_rate"]
TEAM_FIELDS=["games_covered","scrimmage_plays","pass_plays","rush_plays","epa_plays","off_epa_sum",
             "def_epa_plays","def_epa_sum","pass_epa_plays","pass_epa_sum","rush_epa_plays",
             "rush_epa_sum","success_plays","success_count",
             "pass_success_plays","pass_success_count","rush_success_plays","rush_success_count",
             "pass_yards_plays","pass_yards_sum",
             "rush_yards_plays","rush_yards_sum","explosive_pass","explosive_rush",
             "third_plays","third_success","fourth_plays","fourth_success",
             "redzone_plays","redzone_success","pressure_observed","pressure_count",
             "sack_observed","sack_count","drives","drive_yards_sum","drive_plays_sum",
             "field_position_sum","field_position_n"]
FIELDS=["team","season","asof_exclusive","games_covered","scrimmage_plays","pass_plays",
        "rush_plays","off_epa_per_play","def_epa_allowed_per_play","pass_epa_per_play",
        "rush_epa_per_play","off_success_rate","pass_yards_per_play","rush_yards_per_play",
        "explosive_pass_rate_20plus","explosive_rush_rate_12plus","third_down_success_rate",
        "fourth_down_success_rate","redzone_play_success_rate","qb_hurry_rate_observed",
        "sack_rate_observed","drives_observed","yards_per_drive","plays_per_drive",
        "provider_mean_yards_to_goal_per_play","source","source_retrieved_utc","betting_status"]

def number(v):
    if v is None or v=="":return None
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None

def truth(v):
    if isinstance(v,bool):return v
    if v is None:return None
    if isinstance(v,(int,float)):return bool(v)
    s=str(v).strip().lower()
    return True if s in ("true","t","1","yes") else False if s in ("false","f","0","no") else None

def key(v):
    n=number(v)
    return str(int(n)) if n is not None and n.is_integer() else str(v or "").strip()

def rate(sum_,n):
    return round(sum_/n,5) if n else ""

def load_games(path,asof):
    cutoff=dt.date.fromisoformat(asof)
    if cutoff.year!=2026:raise ValueError("2026 season only")
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        games=list(csv.DictReader(f))
    result={}
    for g in games:
        day=dt.date.fromisoformat(g["date"])
        if day>=cutoff:continue
        gid=key(g["game_id"])
        if not gid or gid in result:raise ValueError("Missing/duplicate canonical game id")
        if not g["home"] or not g["away"] or g["home"]==g["away"]:raise ValueError("Invalid game teams")
        int(g["home_score"]);int(g["away_score"])
        result[gid]=g
    if not result:raise ValueError("No prior completed games")
    return result

def read_parquet(path,columns):
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path)
    names=set(pf.schema_arrow.names)
    for batch in pf.iter_batches(columns=[x for x in columns if x in names],batch_size=7000):
        yield from batch.to_pylist()

def metric(row,field):
    v=number(row.get(field))
    return v if v is not None and -40<=v<=40 else None

def per_game_features(play_rows,games,asof,min_plays=20,qb_out=None,qb_observed_at=None):
    """Rows are produced only for both-sided PBP-complete games with valid ESPN final scores."""
    buffs=defaultdict(lambda:defaultdict(list));ids={};issues=defaultdict(Counter);seen=Counter()
    cutoff=dt.date.fromisoformat(asof)
    if qb_out is not None and (not isinstance(qb_out,list) or not qb_observed_at):
        raise ValueError("QB attribution requires actual observation time and output list")
    qb_qa=Counter()
    for p in play_rows:
        gid=key(p.get("game_id"))
        if gid not in games or key(p.get("season"))!="2026":continue
        seen[gid]+=1;g=games[gid]
        if dt.date.fromisoformat(g["date"])>=cutoff:continue
        if truth(p.get("status_type_completed")) is False:
            issues[gid]["incomplete_play"]+=1;continue
        hs,as_=number(p.get("homeFinalScore")),number(p.get("awayFinalScore"))
        if hs is None or as_ is None:
            issues[gid]["missing_final_scores"]+=1;continue
        if int(hs)!=int(g["home_score"]) or int(as_)!=int(g["away_score"]):
            issues[gid]["score_mismatch"]+=1;continue
        hid,aid=key(p.get("homeTeamId")),key(p.get("awayTeamId"))
        if not hid or not aid or hid==aid:
            issues[gid]["missing_team_ids"]+=1;continue
        if gid in ids and ids[gid]!=(hid,aid):
            issues[gid]["conflicting_team_ids"]+=1;continue
        ids[gid]=(hid,aid)
        pos=key(p.get("pos_team_id"))
        if pos==hid:team=g["home"]
        elif pos==aid:team=g["away"]
        else:
            issues[gid]["unmapped_possession"]+=1;continue
        pa,ru=truth(p.get("pass")),truth(p.get("rush"))
        if pa is not True and ru is not True:continue
        if pa is True and ru is True:
            issues[gid]["ambiguous_play_type"]+=1;continue
        q=dict(p);q["_pass"]=bool(pa);q["_rush"]=bool(ru)
        buffs[gid][team].append(q)
    rows=[];quarantine=[]
    for gid in sorted(seen):
        g=games[gid];both=buffs[gid]
        critical=sum(issues[gid][x] for x in
                     ("score_mismatch","missing_final_scores","missing_team_ids","conflicting_team_ids"))
        if critical or min(len(both[g["home"]]),len(both[g["away"]]))<min_plays:
            quarantine.append({"game_id":gid,"date":g["date"],"home":g["home"],"away":g["away"],
                "reason":"FINAL_OR_ID_CONFLICT" if critical else "INSUFFICIENT_TWO_SIDED_PBP",
                "plays_home":len(both[g["home"]]),"plays_away":len(both[g["away"]]),
                "issues":dict(issues[gid])})
            continue
        for team,opp in ((g["home"],g["away"]),(g["away"],g["home"])):
            offensive=both[team];defensive=both[opp]
            stats=Counter({"games_covered":1,"scrimmage_plays":len(offensive),
                           "pass_plays":sum(p["_pass"] for p in offensive),
                           "rush_plays":sum(p["_rush"] for p in offensive)})
            for p in offensive:
                kind="pass" if p["_pass"] else "rush"
                epa=metric(p,"EPA")
                if epa is None:epa=metric(p,"EPA_scrimmage")
                if epa is not None:
                    stats["epa_plays"]+=1;stats["off_epa_sum"]+=epa
                    stats[kind+"_epa_plays"]+=1;stats[kind+"_epa_sum"]+=epa
                yards=number(p.get("statYardage"))
                if yards is not None and -100<=yards<=150:
                    stats[kind+"_yards_plays"]+=1;stats[kind+"_yards_sum"]+=yards
                    if yards>=(20 if kind=="pass" else 12):stats["explosive_"+kind]+=1
                success=truth(p.get("EPA_success"))
                if success is None:success=truth(p.get("success"))
                if success is not None:
                    stats["success_plays"]+=1;stats["success_count"]+=int(success)
                    stats[kind+"_success_plays"]+=1
                    stats[kind+"_success_count"]+=int(success)
                    down=number(p.get("down"))
                    if down==3:stats["third_plays"]+=1;stats["third_success"]+=int(success)
                    if down==4:stats["fourth_plays"]+=1;stats["fourth_success"]+=int(success)
                    ytg=number(p.get("start.yardsToEndzone"))
                    if ytg is not None and 0<=ytg<=20:
                        stats["redzone_plays"]+=1;stats["redzone_success"]+=int(success)
                if kind=="pass":
                    pressure=truth(p.get("qb_hurry"))
                    if pressure is not None:
                        stats["pressure_observed"]+=1;stats["pressure_count"]+=int(pressure)
                    sack=truth(p.get("sack"))
                    if sack is not None:
                        stats["sack_observed"]+=1;stats["sack_count"]+=int(sack)
            for p in defensive:
                epa=metric(p,"EPA")
                if epa is None:epa=metric(p,"EPA_scrimmage")
                if epa is not None:stats["def_epa_plays"]+=1;stats["def_epa_sum"]+=epa
            hid,aid=ids[gid]
            if qb_out is not None:
                passer_rows,audit=collect_qb_passers(g,team,opp,offensive,qb_observed_at)
                qb_out.extend(passer_rows)
                qb_qa["accepted_team_games"]+=1
                qb_qa["named_passer_rows"]+=len(passer_rows)
                qb_qa["named_pass_tagged_plays"]+=audit["named_pass_tagged_plays"]
                qb_qa["unnamed_pass_tagged_plays"]+=audit["unnamed_pass_tagged_plays"]
                qb_qa["team_games_without_passer_names"]+=int(not passer_rows)
            rows.append({"game_id":gid,"date":g["date"],"team":team,"opponent":opp,
                        "team_id":hid if team==g["home"] else aid,
                        "opponent_team_id":aid if team==g["home"] else hid,
                        "plays_for":len(offensive),"plays_against":len(defensive),**stats})
    qa={"pbp_games_seen":len(seen),"games_accepted":len(rows)//2,
        "games_quarantined":len(quarantine),"team_game_rows":len(rows),
        "quarantine":quarantine[:300],
        "reason":"Accepted game requires score match, consistent ESPN team ids and both offenses >=20 plays"}
    if qb_out is not None:
        qa["qb_passer_attribution"]={
            **dict(qb_qa),
            "status":"POSTGAME_PASSER_NOT_STARTER_VERIFIED",
            "source_time_authentic_for_old_games":False,
            "qb1_known_from_pbp":False}
    return rows,qa

def merge_drives(team_games,drive_rows,games):
    """Add verified two-sided team/game drive summaries, or keep metrics absent."""
    index={(r["game_id"],r["team_id"]):r for r in team_games}
    name_index={(r["game_id"],r["team"]):r for r in team_games}
    match_kinds=Counter()
    expected_samples=[{"game_id":r["game_id"],"team_id":r["team_id"],"team":r["team"]} for r in team_games[:6]]
    actual_samples=[]
    by_game=defaultdict(dict);ignored=Counter()
    for d in drive_rows:
        gid=key(d.get("game_id"))
        if gid not in games or key(d.get("season"))!="2026":continue
        tid=key(d.get("pos_team"))
        if len(actual_samples)<6:
            actual_samples.append({"game_id":gid,"pos_team":str(d.get("pos_team")),
                                   "pos_team_type":type(d.get("pos_team")).__name__,
                                   "row_keys":list(d.keys())[:35]})
        row=index.get((gid,tid))
        if row is not None:
            match_kinds["matched_by_espn_team_id"]+=1
        elif d.get("pos_team") in (games[gid]["home"],games[gid]["away"]):
            # 2026 release actually stores full ESPN display names in pos_team
            # despite upstream docs describing numeric IDs. Require exact
            # game-scoped name and previously accepted PBP home/away team.
            row=name_index.get((gid,d["pos_team"]))
            if row is not None:
                tid=row["team_id"]
                match_kinds["matched_by_exact_game_team_name"]+=1
        if row is None:
            ignored["unmatched_game_or_team"]+=1;continue
        if tid in by_game[gid]:
            ignored["duplicate_drive_summary"]+=1
            by_game[gid][tid]=None;continue
        count=number(d.get("drives"))
        yards=number(d.get("yards_per_drive"))
        plays=number(d.get("plays_per_drive"))
        position=number(d.get("avg_field_position"))
        if (count is None or count!=int(count) or not 1<=count<=45 or
            yards is None or not -30<=yards<=130 or
            plays is None or not 0<=plays<=35 or
            position is None or not 0<=position<=100):
            ignored["invalid_drive_summary"]+=1
            by_game[gid][tid]=None;continue
        by_game[gid][tid]={"drives":int(count),"yards_per_drive":yards,
                          "plays_per_drive":plays,"avg_field_position":position}
    applied=0;paired=0
    for gid,groups in by_game.items():
        sides=[r for r in team_games if r["game_id"]==gid]
        if len(sides)!=2:continue
        if any(groups.get(r["team_id"]) is None for r in sides):
            ignored["incomplete_game_pair"]+=1;continue
        paired+=1
        for r in sides:
            d=groups[r["team_id"]]
            r["drives"]=d["drives"]
            r["drive_yards_sum"]=d["yards_per_drive"]*d["drives"]
            r["drive_plays_sum"]=d["plays_per_drive"]*d["drives"]
            # Provider's avg_field_position is averaged across scrimmage PLAYS,
            # not independent drive starts: preserve its weighting and label.
            r["field_position_sum"]=d["avg_field_position"]*r["scrimmage_plays"]
            r["field_position_n"]=r["scrimmage_plays"]
            applied+=1
    return {"drive_rows_applied":applied,"complete_game_pairs":paired,
            "games_with_accepted_pbp":len({r["game_id"] for r in team_games}),
            "status":"VERIFIED_TWO_SIDED_GAME_TEAM_JOIN" if applied else "NO_VERIFIED_DRIVE_ROWS",
            "excluded":dict(ignored),"match_kinds":dict(match_kinds),
            "diagnostic_expected_team_ids":expected_samples,
            "diagnostic_received_drive_ids":actual_samples}

def aggregate_team_profiles(team_games,registry,asof,retrieved):
    by=defaultdict(list)
    for r in team_games:
        if r["date"]>=asof:raise ValueError("Forward-looking game leaked into profiles")
        by[r["team"]].append(r)
    def get(vs,num,den):return rate(sum(float(r.get(num,0) or 0) for r in vs),
                                 sum(float(r.get(den,0) or 0) for r in vs))
    out=[]
    for team in sorted(registry):
        vs=by.get(team,[])
        n=lambda k:sum(float(r.get(k,0) or 0) for r in vs)
        out.append({"team":team,"season":2026,"asof_exclusive":asof,
            "games_covered":int(n("games_covered")),"scrimmage_plays":int(n("scrimmage_plays")),
            "pass_plays":int(n("pass_plays")),"rush_plays":int(n("rush_plays")),
            "off_epa_per_play":get(vs,"off_epa_sum","epa_plays"),
            "def_epa_allowed_per_play":get(vs,"def_epa_sum","def_epa_plays"),
            "pass_epa_per_play":get(vs,"pass_epa_sum","pass_epa_plays"),
            "rush_epa_per_play":get(vs,"rush_epa_sum","rush_epa_plays"),
            "off_success_rate":get(vs,"success_count","success_plays"),
            "pass_yards_per_play":get(vs,"pass_yards_sum","pass_yards_plays"),
            "rush_yards_per_play":get(vs,"rush_yards_sum","rush_yards_plays"),
            "explosive_pass_rate_20plus":get(vs,"explosive_pass","pass_plays"),
            "explosive_rush_rate_12plus":get(vs,"explosive_rush","rush_plays"),
            "third_down_success_rate":get(vs,"third_success","third_plays"),
            "fourth_down_success_rate":get(vs,"fourth_success","fourth_plays"),
            "redzone_play_success_rate":get(vs,"redzone_success","redzone_plays"),
            "qb_hurry_rate_observed":get(vs,"pressure_count","pressure_observed"),
            "sack_rate_observed":get(vs,"sack_count","sack_observed"),
            "drives_observed":int(n("drives")) if n("drives") else "",
            "yards_per_drive":get(vs,"drive_yards_sum","drives"),
            "plays_per_drive":get(vs,"drive_plays_sum","drives"),
            "provider_mean_yards_to_goal_per_play":get(vs,"field_position_sum","field_position_n"),
            "source":"SDV_2026_PBP_RETROSPECTIVE","source_retrieved_utc":retrieved,
            "betting_status":"PASS_UNVALIDATED"})
    return out

def fetch(url,path,max_mb=100):
    path.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={"User-Agent":"cfb-model-research/0.3"})
    digest=hashlib.sha256();size=0
    with urllib.request.urlopen(req,timeout=120) as stream,path.open("wb") as out:
        while True:
            buf=stream.read(1024*1024)
            if not buf:break
            size+=len(buf)
            if size>max_mb*1024*1024:raise ValueError("Source exceeds maximum size")
            digest.update(buf);out.write(buf)
    with path.open("rb") as f:
        f.seek(-4,2);magic=f.read()
    if size<1000 or magic!=b"PAR1":raise ValueError("Invalid or empty Parquet asset")
    return {"source_url":url,"bytes":size,"sha256":digest.hexdigest()}

def execute(games_path,registry_path,output,asof,offline_pbp=None,offline_drives=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    timestamp=dt.datetime.now(dt.timezone.utc).isoformat()
    manifest={"status":"INCOMPLETE","season":2026,"asof_exclusive":asof,
              "retrieved_at_utc":timestamp,"betting_status":"PASS_UNVALIDATED",
              "historical_pregame_availability_verified":False,"sources":{},
              "limitations":["Provider releases can be revised retrospectively.",
                "No verified historical publication-time snapshots.",
                "EPA is provider supplied, never imputed from scoring.",
                "No injury or sportsbook market inputs." ]}
    try:
        games=load_games(games_path,asof)
        with open(registry_path,newline="",encoding="utf-8-sig") as f:
            registry=[r["espn_display_name"].strip() for r in csv.DictReader(f)]
        if len(registry)!=138 or len(set(registry))!=len(registry):raise ValueError("Expected 138 unique FBS schools")
        pbp=Path(offline_pbp) if offline_pbp else output/"raw"/"sdv_pbp_2026.parquet"
        drives=Path(offline_drives) if offline_drives else output/"raw"/"sdv_adv_drives_2026.parquet"
        if not offline_pbp:manifest["sources"]["pbp"]=fetch(PBP_URL,pbp,150)
        else:manifest["sources"]["pbp"]={"source":"user_supplied_local_research_file","path":str(pbp)}
        if not offline_drives:
            try:manifest["sources"]["drives"]=fetch(DRIVE_URL,drives,20)
            except Exception as exc:manifest["sources"]["drives"]={"status":"FAILED","error":str(exc)}
        else:manifest["sources"]["drives"]={"source":"user_supplied_local_research_file","path":str(drives)}
        import pyarrow.parquet as pq
        cols=set(pq.ParquetFile(pbp).schema_arrow.names)
        required={"game_id","season","pos_team_id","homeTeamId","awayTeamId",
                  "homeFinalScore","awayFinalScore","pass","rush"}
        if not required.issubset(cols):raise ValueError("PBP missing required fields: "+str(sorted(required-cols)))
        qb_records=[]
        qb_observed_at=dt.datetime.now(dt.timezone.utc).isoformat()
        team_games,qa=per_game_features(
            read_parquet(pbp,COLS),games,asof,
            qb_out=qb_records,qb_observed_at=qb_observed_at)
        manifest["pbp_qa"]=qa
        if not team_games:raise ValueError("No scoreboard-verified games in PBP release")
        if drives.exists():
            manifest["drive_qa"]=merge_drives(team_games,read_parquet(drives,DRIVE_COLS),games)
        output.mkdir(parents=True,exist_ok=True)
        with (output/"team_game_advanced_2026.csv").open("w",newline="") as f:
            fields=["game_id","date","team","opponent","team_id","opponent_team_id","plays_for","plays_against"]+TEAM_FIELDS
            w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(team_games)
        # This records historical player usage; never infer game-specific QB1.
        with (output/"qb_passer_game_history_2026.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=QB_PASSER_FIELDS,extrasaction="raise")
            w.writeheader();w.writerows(qb_records)
        manifest["qb_passer_history"]={
            "rows":len(qb_records),
            "source_observed_at_utc":qb_observed_at,
            "historical_original_publication_verified":False,
            "starter_identity_inferred":False,
            "status":"POSTGAME_PASSER_ATTRIBUTION_RESEARCH_ONLY"}
        profile=aggregate_team_profiles(team_games,registry,asof,timestamp)
        with (output/"team_profiles_advanced_2026.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(profile)
        manifest["profiles"]=len(profile)
        manifest["teams_with_pbp"]=sum(p["games_covered"]>0 for p in profile)
        manifest["teams_with_observed_epa"]=sum(p["off_epa_per_play"]!="" for p in profile)
        manifest["completed_score_games_before_asof"]=len(games)
        manifest["status"]="RESEARCH_PBP_IMPORTED_DRIVE_JOIN_VERIFIED" if manifest.get("drive_qa",{}).get("drive_rows_applied",0)>0 else "RESEARCH_PBP_IMPORTED_NO_VERIFIED_DRIVES"
        manifest["safe_to_publish_picks"]=False
    except Exception as exc:
        manifest["error"]=str(exc)
        manifest["safe_to_publish_picks"]=False
        manifest["status"]="ADVANCED_IMPORT_FAILED"
    (output/"advanced_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k!="pbp_qa"},indent=2))
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",default="data/games_2026.csv")
    p.add_argument("--registry",default="data/archive/2026_team_aliases.csv")
    p.add_argument("--output",default="data/advanced")
    p.add_argument("--asof",default=dt.date.today().isoformat())
    p.add_argument("--pbp-file");p.add_argument("--drives-file")
    a=p.parse_args()
    result=execute(a.games,a.registry,a.output,a.asof,a.pbp_file,a.drives_file)
    raise SystemExit(0 if result["status"].startswith("RESEARCH_PBP_IMPORTED") else 2)
