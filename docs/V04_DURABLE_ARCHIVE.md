# v0.4 Step 2B — private durable pregame evidence storage

**Deployment status: Code and mock AWS tests implemented; private bucket and AWS role NOT configured or verified.**

Our workflow's source-time observations are currently retained as **30-day GitHub Actions artifacts**. The `scripts/durable_archive.py` implementation offers **optional** AWS S3 Object Lock in COMPLIANCE mode for a minimum **365-day** retention, using GitHub OpenID Connect (OIDC) authentication instead of static AWS keys.

The archive refuses malformed, post-kickoff, noncanonical, retrospective-misrepresented or checksum-inconsistent capture records **before any remote write**. It checks that the destination bucket has versioning ENABLED, Object Lock ENABLED and all four public-access-block switches enabled. It then conditionally writes to a per-workflow-run object key (`IfNoneMatch: *`) with SSE-S3 encryption and 365-day COMPLIANCE retention. An actual success requires the remote object version ID, HEAD verification of lock, retention, encryption and metadata digest, and a readback of the exact version that matches the SHA-256 of the original file. A receipt is written **only after all verifications succeed**.

## Deployment needed in your AWS account

Set up a **private S3 bucket with Object Lock enabled at bucket creation, versioning enabled, block public access enabled and an appropriate region**. Validate the irreversible/legal implications of COMPLIANCE mode: an object generally cannot be deleted or shortened even by an administrator before expiration, and AWS may charge for storage and API calls. Review data and provider licensing before enabling archival.

Create an IAM role with an AWS GitHub OIDC trust relationship restricted to audience `sts.amazonaws.com` and GitHub subject `repo:The-Caves/cfb-model:ref:refs/heads/main`. Scope the role to the specific private bucket and `cfb-2026/pregame-captures/` object prefix only for object operations. Its permissions must allow the documented bucket configuration checks, `s3:PutObject`, `s3:GetObject`, `s3:GetObjectVersion`, and the permissions needed to upload/read Object Lock compliance retention; consult the AWS IAM action names relevant to Object Lock in your account and enable a least-privilege policy. Do not grant public bucket access or store long-lived AWS keys in GitHub.

Set GitHub repository *Actions variables* (Settings > Secrets and variables > Actions > Variables):

- `CFB_ARCHIVE_BUCKET`: private Object-Lock-enabled S3 bucket name
- `CFB_ARCHIVE_REGION`: AWS region
- `CFB_ARCHIVE_ROLE_ARN`: restricted IAM role ARN to assume through GitHub OIDC

Only when all three variables exist will `.github/workflows/cfb-data-intake.yml` install the S3 Python SDK, assume the role and attempt verified archival. With missing variables, the workflow states **NOT CONFIGURED**, skips cloud archiving, and keeps the existing successful 30-day artifact path. With all three configured but a bad bucket/lock/permission/retention/readback, the archive step fails and must not claim storage succeeded.

The receipt `data/pregame_evidence/durable-receipt-<run ID>.json`, included in the existing short-lived Actions artifact, records the S3 object, version ID, SHA-256, retention date and verification status. Do not publicly commit source data or private sportsbook prices.

**Limitations:** This preserves **our actual workflow-time captures going forward**, not the original September source versions that were only downloaded later. The archive is not a clock-attestation authority or independently verified publication-history service. No actual AWS archival has been performed in this code milestone, and genuine source-time backtesting and FanDuel price validation remain incomplete. All statuses remain `PASS_UNVALIDATED`.

Public workflow receipts intentionally **redact the S3 bucket, object key and object version ID**, because the repo and its Actions artifacts may be viewable by other users. Authorized operators can reconstruct the private object key using the documented prefix and numeric workflow run ID inside their AWS account, and discover immutable versions via the private S3 API. The actual upload module verifies the exact VersionId before writing a redacted audit receipt; those private resource identifiers do not go into the public workflow artifact.

## Repository code-validation checkpoint

GitHub Actions validation completed **285 passing tests** on commit `8a13672d3ad9fb52d329c2e243bd467e94c3c4eb`. All S3 calls in this validation were mocked. No AWS bucket was created, contacted or charged by the tests. The opt-in full workflow still must confirm it takes the correct configuration path before deployment is considered finished. Actual durable storage requires an externally configured, private Object-Lock-enabled bucket and restricted OIDC role.

AWS S3's `PutObject` API requires a `Content-MD5` or SDK checksum-algorithm header when specifying Object Lock retention. The uploader sets both `ChecksumAlgorithm=SHA256` and the matching Base64 `ChecksumSHA256` of the original bytes, in addition to the post-upload private versioned readback. [AWS Boto3 reference](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).
