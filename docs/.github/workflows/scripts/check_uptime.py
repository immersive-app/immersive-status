import os, time, json, sys
import requests
import boto3
from botocore.exceptions import BotoCoreError, ClientError

URL = os.environ["TARGET_URL"]
TIMEOUT = int(os.environ.get("TIMEOUT_SECONDS", "10"))
AWS_REGION = os.environ["AWS_REGION"]
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAIL = os.environ["TO_EMAIL"]
STATUS_FILE = "docs/status.json"

def read_previous_status():
    """Read the previous status from status.json if it exists."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def send_email(subject, html):
    ses = boto3.client("sesv2", region_name=AWS_REGION)
    ses.send_email(
        FromEmailAddress=FROM_EMAIL,
        Destination={"ToAddresses": [TO_EMAIL]},
        Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Html": {"Data": html}}}},
    )

def write_status(ok, status_code, latency_ms, err_msg=None):
    # Read previous status before writing new one
    previous_status = read_previous_status()
    
    payload = {
        "ok": bool(ok),
        "status": status_code,
        "latency_ms": int(latency_ms) if latency_ms is not None else None,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": URL,
        "error": err_msg,
    }
    os.makedirs("docs", exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    
    # Determine if we should commit based on previous status
    should_commit = False
    
    # If no previous status, always commit
    if previous_status is None:
        should_commit = True
    # If status changed from failure to success, commit
    elif not previous_status.get("ok", False) and ok:
        should_commit = True
    # If status is still failure, commit (to update timestamp and error details)
    elif not ok:
        should_commit = True
    # If status is still success, don't commit (no change)
    else:
        should_commit = False
    
    return should_commit

def main():
    t0 = time.time()
    status = None
    ok = False
    err = None
    try:
        r = requests.get(URL, timeout=TIMEOUT)
        status = r.status_code
        ok = 200 <= status < 400
    except Exception as e:
        err = str(e)

    latency_ms = int((time.time() - t0) * 1000)
    should_commit = write_status(ok, status, latency_ms, err)
    
    # Set environment variable to signal whether to commit
    os.environ["SHOULD_COMMIT"] = "true" if should_commit else "false"

    if ok:
        print(f"OK {status} in {latency_ms}ms")
        if should_commit:
            print("Status changed - will commit")
        else:
            print("Status unchanged - skipping commit")
        return

    subject = f"[Immersive Uptime] DOWN: {URL} (status={status}, err={err})"
    body = f"""
      <h3>Immersive is DOWN</h3>
      <p><b>URL:</b> {URL}</p>
      <p><b>Status:</b> {status}</p>
      <p><b>Error:</b> {err}</p>
      <p><b>Latency:</b> {latency_ms} ms</p>
      <p><b>Checked at (UTC):</b> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    """
    try:
        send_email(subject, body)
        print("Alert email sent via SES.")
    except (BotoCoreError, ClientError) as e:
        print(f"Failed to send SES email: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(2)

if __name__ == "__main__":
    main()
