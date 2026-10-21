"""Chronological, game-disjoint research folds with postgame label safeguards.

Accepts private pregame feature records and separate outcome labels emitted by
scripts.market_settlement. Returns record IDs and aggregate QA only. No model,
picks, ROI, or sportsbook data are emitted by this module.
"""
from collections import Counter
from scripts.game_context import parse_time

def build_folds(feature_rows,label_rows,boundaries,evaluation_asof_utc,
                min_train_games=1):
    """For each [train_cutoff, test_end), train strictly on prior known labels.

    Training outcomes must have been published before train_cutoff. A test
    record belongs to its kickoff window and must have been selected only
    after train_cutoff but before kickoff. This conservative design avoids
    cross-fold pre-decision picks and repeat-game leakage.
    """
    if type(min_train_games) is not int or min_train_games<1:
        raise ValueError("min_train_games must be a positive integer")
    if len(boundaries)<2:
        raise ValueError("At least two chronological boundaries required")
    parsed=[parse_time(t) for t in boundaries]
    if any(a>=b for a,b in zip(parsed,parsed[1:])):
        raise ValueError("Fold boundaries must be strictly increasing")
    evaluation=parse_time(evaluation_asof_utc)
    if evaluation<parsed[0]:
        raise ValueError("Evaluation as-of precedes folds")
    if not isinstance(feature_rows,list) or not isinstance(label_rows,list):
        raise ValueError("Expected separate feature and label collections")
    feat={}
    logical_keys=set()
    for row in feature_rows:
        rid=row["row_id"]
        if rid in feat:raise ValueError("Duplicate pregame feature row ID")
        required=("espn_game_id","decision_asof_utc","pregame_context_asof_utc",
                  "kickoff_utc","market_observed_at_utc","market_retrieved_at_utc",
                  "market","selection","bookmaker","market_source_sha256")
        if any(not row.get(k) for k in required):
            raise ValueError("Missing pregame feature evidence")
        if row.get("status")!="PREGAME_RESEARCH_FEATURE_ONLY":
            raise ValueError("Invalid feature status")
        # A repeated price for the same game, book, market, selection would
        # overweight that game. Repeated decision-time rows must be curated
        # into one fixed policy before an actual walk-forward evaluation.
        logical=(str(row["espn_game_id"]),row["bookmaker"],
                 row["market"],row["selection"])
        if logical in logical_keys:
            raise ValueError("Repeated game/market selection; select a fixed decision policy")
        logical_keys.add(logical)
        prediction=parse_time(row["decision_asof_utc"])
        kickoff=parse_time(row["kickoff_utc"])
        if prediction>=kickoff:
            raise ValueError("Decision cannot follow kickoff")
        for k in ("pregame_context_asof_utc","market_observed_at_utc",
                  "market_retrieved_at_utc"):
            if parse_time(row[k])>prediction:
                raise ValueError("Future pregame information would leak")
        if parse_time(row["market_observed_at_utc"])>=kickoff:
            raise ValueError("In-play price cannot be a pregame feature")
        if len(str(row["market_source_sha256"]))!=64:
            raise ValueError("Missing snapshot provenance")
        for forbidden in ("home_score","away_score","settlement","result",
                          "outcome_known_at_utc","label","actual_margin"):
            if forbidden in row:
                raise ValueError("Postgame outcome leaked into features")
        feat[rid]=row
    labels={}
    for row in label_rows:
        rid=row["row_id"]
        if rid in labels:raise ValueError("Duplicate settlement label ID")
        if rid not in feat:raise ValueError("Label without matching feature")
        if row.get("status")!="POSTGAME_LABEL_ONLY":
            raise ValueError("Invalid postgame label")
        if row.get("settlement") not in ("WIN","LOSS","PUSH"):
            raise ValueError("Unknown settlement")
        if str(row.get("espn_game_id"))!=str(feat[rid]["espn_game_id"]):
            raise ValueError("Label linked to wrong ESPN game")
        available=parse_time(row["outcome_known_at_utc"])
        if available<=parse_time(feat[rid]["kickoff_utc"]):
            raise ValueError("Impossible early final label")
        labels[rid]=row
    folds=[]
    for start,end in zip(parsed,parsed[1:]):
        train=[];test=[];pending=[];excluded=Counter()
        for rid,row in feat.items():
            kickoff=parse_time(row["kickoff_utc"])
            decision=parse_time(row["decision_asof_utc"])
            label=labels.get(rid)
            if kickoff<start:
                if label is not None and parse_time(label["outcome_known_at_utc"])<start:
                    train.append(rid)
                else:
                    excluded["historical_label_not_known_at_training_cutoff"]+=1
            elif start<=kickoff<end:
                if decision<start:
                    excluded["decision_before_test_window"]+=1
                    continue
                if label is not None and parse_time(label["outcome_known_at_utc"])<=evaluation:
                    test.append(rid)
                else:
                    pending.append(rid)
            else:
                excluded["outside_fold"]+=1
        train_games={str(feat[rid]["espn_game_id"]) for rid in train}
        test_games={str(feat[rid]["espn_game_id"]) for rid in test+pending}
        if train_games & test_games:
            raise ValueError("Game ID leaked from training into test")
        status=("READY_FOR_RESEARCH_EVALUATION"
                if len(train_games)>=min_train_games and test
                else "INSUFFICIENT_TRAINING_OR_TEST_LABELS")
        folds.append({
            "training_cutoff_utc":start.isoformat(),
            "test_end_exclusive_utc":end.isoformat(),
            "evaluation_asof_utc":evaluation.isoformat(),
            "train_row_ids":sorted(train),
            "test_labeled_row_ids":sorted(test),
            "test_pending_row_ids":sorted(pending),
            "train_game_count":len(train_games),
            "test_game_count":len(test_games),
            "excluded":dict(excluded),
            "status":status,
            "prediction_engine_validated":False
        })
    return {"status":"WALK_FORWARD_SPLITS_ONLY",
            "folds":folds,"features_total":len(feat),
            "labels_total":len(labels),
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
