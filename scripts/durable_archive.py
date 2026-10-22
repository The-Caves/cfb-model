"""Optional private S3 COMPLIANCE Object Lock archive for pregame observations.

The object is not considered durable until versioning, lock, private bucket
policy, SSE, retention, remote bytes and SHA-256 have been verified.
"""
import argparse,datetime as dt,hashlib,json,os,re
from pathlib import Path
from scripts.model_v03 import timestamp
from scripts.weekly_profiles import canonical

MIN_DAYS=365
STATUS="S3_COMPLIANCE_READBACK_VERIFIED"
UTC=dt.timezone.utc
BLOCK=("BlockPublicAcls","IgnorePublicAcls","BlockPublicPolicy","RestrictPublicBuckets")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_capture(data,expected_run=None):
    rec=json.loads(data)
    if canonical(rec)!=data:
        raise ValueError("Noncanonical capture JSON bytes")
    if (rec.get("status")!="OBSERVED_PREGAME_RESEARCH_CAPTURE" or
        rec.get("betting_status")!="PASS_UNVALIDATED" or
        rec.get("safe_for_betting") is not False or
        rec.get("historical_publication_times_verified") is not False):
        raise ValueError("Invalid research capture provenance")
    rid=str(rec.get("run_id",""))
    if not re.fullmatch(r"[0-9]{1,24}",rid) or (
        expected_run is not None and str(expected_run)!=rid):
        raise ValueError("Invalid workflow run ID")
    observed=timestamp(rec["captured_at_utc"])
    if any(timestamp(t)>observed for t in rec["sources"].values()):
        raise ValueError("Source retrieved after capture")
    if not rec.get("games"):
        raise ValueError("Missing future games")
    ids=set()
    for game in rec["games"]:
        gid=str(game["game_id"])
        if not gid or gid in ids:raise ValueError("Duplicate game ID")
        ids.add(gid)
        if timestamp(game["kickoff_utc"])<=observed:
            raise ValueError("Pregame capture at or after kickoff")
        if game["profile_source"]!="RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED":
            raise ValueError("Historical data wrongly certified")
        if sha(canonical(game["team_profiles"]))!=game["team_profiles_sha256"]:
            raise ValueError("Profile checksum mismatch")
    sources=rec.get("source_file_sha256")
    if not isinstance(sources,dict) or len(sources)!=6 or any(
        not re.fullmatch(r"[0-9a-f]{64}",str(v)) for v in sources.values()):
        raise ValueError("Invalid source checksums")
    return rec

def check_bucket(s3,bucket):
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]",str(bucket)):
        raise ValueError("Invalid private bucket identifier")
    if s3.get_bucket_versioning(Bucket=bucket).get("Status")!="Enabled":
        raise ValueError("S3 bucket versioning must be enabled")
    lock=s3.get_object_lock_configuration(Bucket=bucket)
    if lock.get("ObjectLockConfiguration",{}).get("ObjectLockEnabled")!="Enabled":
        raise ValueError("S3 Object Lock must be enabled")
    block=s3.get_public_access_block(Bucket=bucket).get(
        "PublicAccessBlockConfiguration",{})
    if not all(block.get(flag) is True for flag in BLOCK):
        raise ValueError("S3 bucket public access must be fully blocked")

def verify_remote(s3,bucket,key,version_id,expected_hash,until):
    if not version_id:raise ValueError("Missing immutable object version")
    head=s3.head_object(Bucket=bucket,Key=key,VersionId=version_id)
    if head.get("VersionId")!=version_id:
        raise ValueError("Unverified object version")
    if head.get("ObjectLockMode")!="COMPLIANCE":
        raise ValueError("Remote COMPLIANCE lock missing")
    retain=head.get("ObjectLockRetainUntilDate")
    if retain is None or timestamp(retain.isoformat())<until:
        raise ValueError("Remote retention less than requested")
    if head.get("ServerSideEncryption") not in ("AES256","aws:kms","aws:kms:dsse"):
        raise ValueError("Remote encryption unverified")
    if head.get("Metadata",{}).get("sha256")!=expected_hash:
        raise ValueError("Remote digest metadata mismatch")
    actual=s3.get_object(Bucket=bucket,Key=key,VersionId=version_id)["Body"].read()
    if len(actual)!=head.get("ContentLength") or sha(actual)!=expected_hash:
        raise ValueError("Remote content SHA-256 readback failed")
    validate_capture(actual)
    return True

def archive_file(path,s3,bucket,region,run_id,now=None,days=MIN_DAYS):
    if type(days) is not int or days<MIN_DAYS:
        raise ValueError("At least 365 days retention required")
    if not region or not isinstance(region,str):
        raise ValueError("Region required")
    file=Path(path)
    data=file.read_bytes()
    rec=validate_capture(data,run_id)
    if file.name!="capture-"+rec["run_id"]+".json":
        raise ValueError("Capture filename does not match run ID")
    check_bucket(s3,bucket)
    current=timestamp(now) if now is not None else dt.datetime.now(UTC)
    if current<timestamp(rec["captured_at_utc"]):
        raise ValueError("Archive time precedes original capture")
    expires=current+dt.timedelta(days=days)
    key="cfb-2026/pregame-captures/run-"+rec["run_id"]+"/"+file.name
    checksum=sha(data)
    result=s3.put_object(
        Bucket=bucket,Key=key,Body=data,ContentType="application/json",
        ServerSideEncryption="AES256",IfNoneMatch="*",
        ObjectLockMode="COMPLIANCE",ObjectLockRetainUntilDate=expires,
        Metadata={"sha256":checksum,"run-id":rec["run_id"]})
    vid=result.get("VersionId")
    verify_remote(s3,bucket,key,vid,checksum,expires)
    return {"status":STATUS,"backend":"S3_OBJECT_LOCK_COMPLIANCE",
            "bucket":bucket,"region":region,"key":key,"version_id":vid,
            "run_id":rec["run_id"],"sha256":checksum,
            "capture_observed_at_utc":rec["captured_at_utc"],
            "archive_verified_at_utc":current.isoformat(),
            "retain_until_utc":expires.isoformat(),
            "remote_sha256_readback_verified":True,
            "remote_compliance_retention_verified":True,
            "historical_publication_times_verified":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def save_receipt(receipt,path):
    """Write a public-safe audit summary, never private bucket/key/version IDs.

    The true object path is derived inside the authorized AWS account from
    the known run ID, while version IDs remain discoverable inside private S3.
    """
    if receipt.get("status")!=STATUS or not (
        receipt.get("remote_sha256_readback_verified") and
        receipt.get("remote_compliance_retention_verified")):
        raise ValueError("An unverified archive cannot issue a receipt")
    public_keys=("status","backend","run_id","sha256",
                 "capture_observed_at_utc","archive_verified_at_utc",
                 "retain_until_utc","remote_sha256_readback_verified",
                 "remote_compliance_retention_verified",
                 "historical_publication_times_verified",
                 "safe_for_betting","betting_status")
    safe={k:receipt[k] for k in public_keys}
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("xb") as stream:stream.write(canonical(safe))

def main():
    p=argparse.ArgumentParser()
    for name in ("capture","receipt","bucket","region","run-id"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--retention-days",type=int,default=365)
    a=p.parse_args()
    import boto3
    s3=boto3.client("s3",region_name=a.region)
    receipt=archive_file(a.capture,s3,a.bucket,a.region,a.run_id,
                         days=a.retention_days)
    save_receipt(receipt,a.receipt)
    # No bucket, key or private content printed to public workflow logs.
    print(json.dumps({"status":STATUS,"run_id":receipt["run_id"],
                      "digest":receipt["sha256"],"betting_status":"PASS_UNVALIDATED"}))
if __name__=="__main__":
    main()
