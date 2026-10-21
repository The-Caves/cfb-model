"""Private, research-only FanDuel market features for a decision-time cutoff.

Use only quotes actually retrieved on or before the decision. Historical
backfills may be useful for research, but cannot masquerade as live quotes.
This returns private sportsbook prices; NEVER publish output to a public
repository, GitHub Actions artifact, or public API.
"""
from collections import defaultdict
from scripts.game_context import parse_time
from scripts.market_event_crosswalk import crosswalk
from scripts.market_vault import connect

SIDES={"SPREAD":("HOME","AWAY"),"MONEYLINE":("HOME","AWAY"),
       "TOTAL":("OVER","UNDER")}

def raw_implied(american):
    if type(american) is not int or not (american<=-100 or american>=100):
        raise ValueError("Invalid American odds")
    return round((-american)/(-american+100) if american<0
                 else 100/(american+100),8)

def paired(rows,market):
    if len(rows)!=2 or {q["selection"] for q in rows}!=set(SIDES[market]):
        return None
    sides={q["selection"]:q for q in rows}
    left,right=[sides[k] for k in SIDES[market]]
    if market in ("SPREAD","TOTAL"):
        a,b=left["line_points"],right["line_points"]
        if a is None or b is None or (
            market=="SPREAD" and abs(a+b)>0.00001) or (
            market=="TOTAL" and abs(a-b)>0.00001):
            return None
    elif left["line_points"] is not None or right["line_points"] is not None:
        return None
    return sides

def summarize_market(earliest,latest,market,cutoff,max_age):
    age=round((cutoff-parse_time(latest["observed_at_utc"])).total_seconds()/60,2)
    updates=[q["provider_last_update_utc"] for q in latest["sides"].values()]
    publication_age=(round((cutoff-min(parse_time(t) for t in updates)).total_seconds()/60,2)
                     if all(updates) else None)
    fresh=age<=max_age and publication_age is not None and publication_age<=max_age
    odds={s:latest["sides"][s]["american_odds"] for s in SIDES[market]}
    implied={s:raw_implied(price) for s,price in odds.items()}
    total=sum(implied.values())
    reference="HOME" if market=="SPREAD" else "OVER" if market=="TOTAL" else None
    initial_line=earliest["sides"][reference]["line_points"] if reference else None
    latest_line=latest["sides"][reference]["line_points"] if reference else None
    return {
        "status":"RECENT_OBSERVED_NOT_EXECUTABLE" if fresh else "STALE_OR_UNTIMED_PRICE",
        "market":market,"first_observed_at_utc":earliest["observed_at_utc"],
        "latest_observed_at_utc":latest["observed_at_utc"],
        "quote_age_minutes":age,"source_update_age_minutes":publication_age,
        "first_observed_reference_line":initial_line,
        "latest_reference_line":latest_line,
        "observed_line_movement_points":round(latest_line-initial_line,2)
            if reference else None,
        "selections":{s:{"american_odds":odds[s],
                         "line_points":latest["sides"][s]["line_points"],
                         "raw_implied_probability":implied[s]}
                       for s in SIDES[market]},
        "two_way_overround":round(total,8),
        "two_way_normalized_probabilities":{s:round(implied[s]/total,8) for s in implied},
        "true_opener_verified":False,"true_closer_verified":False,
        "executable_at_fanduel_verified":False,
        "model_edge_calculated":False
    }

def market_board(vault_path,espn_context,aliases,decision_utc,bookmaker="fanduel",
                 max_age_minutes=180,conflicts=()):
    """Cutoff-safe, same-book, paired FanDuel-feature board; no betting advice.

    All odds must be captured BEFORE decision time and kickoff. Crucially, an
    older observation retrieved retrospectively AFTER cutoff is excluded.
    ESPN game metadata must have existed before each contributing quote.
    """
    decision=parse_time(decision_utc)
    espn_asof=parse_time(espn_context["asof_utc"])
    if espn_asof>decision:raise ValueError("ESPN context came after decision time")
    if not isinstance(bookmaker,str) or not bookmaker:
        raise ValueError("Bookmaker required")
    if type(max_age_minutes) not in (float,int) or max_age_minutes<=0:
        raise ValueError("Freshness minutes must be positive")
    db=connect(vault_path)
    try:
        db.row_factory=__import__("sqlite3").Row
        records=[dict(q) for q in db.execute(
            "SELECT q.* FROM quotes q WHERE q.bookmaker=? "
            "ORDER BY q.observed_at_utc",(bookmaker,))]
    finally:db.close()

    qa=defaultdict(int)
    eligible=[]
    for r in records:
        t=parse_time(r["observed_at_utc"])
        if decision>=parse_time(r["kickoff_utc"]):
            qa["game_started"]+=1;continue
        if t>decision:
            qa["observation_after_decision"]+=1;continue
        if parse_time(r["retrieved_at_utc"])>decision:
            qa["historical_backfill_after_decision"]+=1;continue
        if t<espn_asof:
            qa["no_prior_espn_context"]+=1;continue
        update=r["provider_last_update_utc"]
        if update and parse_time(update)>t:
            qa["source_update_after_observation"]+=1;continue
        eligible.append(r)

    # Each two-sided market must come from ONE source snapshot, never two
    # different captures or two different bookmakers.
    grouped=defaultdict(list)
    fingerprints=defaultdict(set)
    for r in eligible:
        if r["market"] not in SIDES:continue
        fingerprints[r["event_id"]].add((r["home_team_source"],
            r["away_team_source"],r["kickoff_utc"]))
        grouped[(r["event_id"],r["market"],r["snapshot_id"])].append(r)
    valid=defaultdict(list)
    for (eid,market,snapshot_id),rows in grouped.items():
        sides=paired(rows,market)
        if sides is None:
            qa["incomplete_or_invalid_pair"]+=1;continue
        if len({r["observed_at_utc"] for r in rows})!=1:
            qa["inconsistent_side_timestamps"]+=1;continue
        valid[(eid,market)].append({"sides":sides,"snapshot_id":snapshot_id,
                                     "observed_at_utc":rows[0]["observed_at_utc"]})
    board=defaultdict(dict)
    identities={}
    for (eid,market),observations in valid.items():
        if len(fingerprints[eid])!=1:
            qa["conflicting_event_identity"]+=1;continue
        by_time=defaultdict(list)
        for obs in observations:
            by_time[obs["observed_at_utc"]].append(obs)
        canonical=[]
        for time,occurrences in by_time.items():
            signatures={tuple((side,obs["sides"][side]["line_points"],
                               obs["sides"][side]["american_odds"])
                         for side in SIDES[market]) for obs in occurrences}
            if len(signatures)!=1:
                qa["contradictory_same_time_prices"]+=1
                canonical=[];break
            canonical.append(occurrences[0])
        if not canonical:continue
        chronological=sorted(canonical,key=lambda x:parse_time(x["observed_at_utc"]))
        board[eid][market]=summarize_market(chronological[0],chronological[-1],
                                           market,decision,max_age_minutes)
        identities[eid]=next(iter(fingerprints[eid]))
    output=[]
    for eid,markets in sorted(board.items()):
        home,away,kickoff=identities[eid]
        # Crosswalk validates exact teams, direction, kickoff and verified ESPN
        # game identifiers. We use the latest market observation for the join.
        latest=max(m["latest_observed_at_utc"] for m in markets.values())
        match=crosswalk({"quotes":[{"provider_event_id":eid,
            "home_team_source":home,"away_team_source":away,
            "kickoff_utc":kickoff,"observed_at_utc":latest}],
            "betting_status":"PASS_UNVALIDATED"},espn_context,aliases,conflicts)
        if match["coverage"]["matched"]!=1:
            for reason,n in match["coverage"]["reasons"].items():
                if reason!="MATCHED":qa["game_join_"+reason]+=n
            continue
        game=match["quotes"][0]
        output.append({"espn_game_id":game["espn_game_id"],
                       "provider_event_id":eid,"bookmaker":bookmaker,
                       "home_espn_team_id":game["home_espn_team_id"],
                       "away_espn_team_id":game["away_espn_team_id"],
                       "markets":markets,
                       "missing_markets":[m for m in SIDES if m not in markets],
                       "all_three_markets_recent":len(markets)==3 and all(
                           m["status"]=="RECENT_OBSERVED_NOT_EXECUTABLE"
                           for m in markets.values())})
    # Multiple provider event IDs can represent the same ESPN game.
    # Never offer two conflicting identities for one model matchup.
    duplicates=defaultdict(list)
    for record in output:duplicates[record["espn_game_id"]].append(record)
    safe=[group[0] for group in duplicates.values() if len(group)==1]
    qa["ambiguous_duplicate_espn_matches"]=sum(
        len(group) for group in duplicates.values() if len(group)>1)
    return {"status":"PRIVATE_MARKET_RESEARCH_ONLY",
            "decision_asof_utc":decision.isoformat(),
            "espn_context_asof_utc":espn_asof.isoformat(),
            "bookmaker":bookmaker,"events":safe,
            "qa":{"stored_quote_rows":len(records),
                  "time_eligible_quote_rows":len(eligible),
                  "matched_events":len(safe),"exclusions":dict(qa)},
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
