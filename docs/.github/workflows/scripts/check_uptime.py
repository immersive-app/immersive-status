import os, time, json, sys
import requests
import boto3
from botocore.exceptions import BotoCoreError, ClientError

URL = os.environ["TARGET_URL"]
TIMEOUT = int(os.environ.get("TIMEOUT_SECONDS", "10"))
AWS_REGION = os.environ["AWS_REGION"]
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAIL = os.environ["TO_EMAIL"]

def send_email(subject, html):
    ses = boto3.client("sesv2", region_name=AWS_REGION)
    ses.send_email(
        FromEmailAddress=FROM_EMAIL,
        Destination={"ToAddresses": [TO_EMAIL]},
        Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Html": {"Data": html}}}},
    )

def write_status(ok, status_code, latency_ms, err_msg=None):
    payload = {
        "ok": bool(ok),
        "status": status_code,
        "latency_ms": int(latency_ms) if latency_ms is not None else None,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": URL,
        "error": err_msg,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/status.json", "w") as f:
        json.dump(payload, f, indent=2)

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
    write_status(ok, status, latency_ms, err)

    if ok:
        print(f"OK {status} in {latency_ms}ms")
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
