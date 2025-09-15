# Immersive Status

A zero-cost, public status page for **[https://immersive-app.com/up](https://immersive-app.com/up)**, hosted on **GitHub Pages** at **[https://status.immersive-app.com](https://status.immersive-app.com)**, with an **uptime checker** that runs on a schedule via **GitHub Actions** and sends **AWS SES** alerts if the site is down.

---

## Overview

* **Status page**: `/docs/index.html` (Tailwind) served by GitHub Pages at `status.immersive-app.com`.
* **Heartbeat data**: `/docs/status.json` updated by a scheduled GitHub Action.
* **Checker**: `.github/scripts/check_uptime.py` `GET`s `https://immersive-app.com/up`, measures latency, and decides UP/DOWN.
* **Alerting**: On failure (non-2xx/3xx or exception), the Action sends an email via **AWS SES** using **OIDC** (no AWS keys in the repo).
* **No secrets committed**: Sender/recipient emails and the AWS Role ARN live in **GitHub Secrets**.

---

## How it works

### Components

1. **GitHub Pages (static UI)**

   * `docs/index.html` loads `docs/status.json` and flips the UI between:

     * **“Immersive is up”** when `ok: true`
     * **“Immersive is down”** when `ok: false`
   * `docs/CNAME` pins the custom domain: `status.immersive-app.com`.

2. **GitHub Actions (scheduler + writer)**

   * Workflow: `.github/workflows/uptime.yml`.
   * Runs **every 10 minutes** (cron) and on manual dispatch.
   * Steps:

     1. Assume an AWS IAM Role via **OIDC**.
     2. Run the Python checker.
     3. Write/commit `docs/status.json` with the latest result.
     4. If DOWN, send **SES** email to the configured recipient.

3. **AWS SES (email)**

   * Domain `immersive-app.com` is verified in SES (with DKIM).
   * `FROM_EMAIL` is a verified identity (and `TO_EMAIL` too while in SES Sandbox).
   * The Actions runner sends via `ses:SendEmail` using the assumed role (no static keys).

4. **DNS**

   * **Namecheap** CNAME: `status -> immersive-app.github.io`
   * GitHub Pages configured to serve from `/docs` with the custom domain and HTTPS.

### Data flow

```
Cron → Action → requests.get(https://immersive-app.com/up)
                  ├─ success → ok=true → write docs/status.json → commit
                  └─ failure → ok=false → write docs/status.json → commit → SES email
GitHub Pages serves docs/index.html → fetches docs/status.json → flips UI
```

---

## Install / Setup

> These steps assume the repo is **`immersive-app/immersive-status`** and the status domain is **`status.immersive-app.com`**.

### 0) File structure (already in this repo)

```
docs/
  CNAME                # "status.immersive-app.com"
  index.html           # Tailwind UI that reads status.json
  status.json          # Filled by the Action (seed file for first load)
.github/
  workflows/
    uptime.yml         # Scheduler + SES sender + status.json commit
  scripts/
    check_uptime.py    # The HTTP checker
```

### 1) GitHub Pages

* Repo → **Settings → Pages**

  * **Build and deployment**: *Deploy from a branch*
  * **Branch**: `main`, **Folder**: `/docs`
  * **Custom domain**: `status.immersive-app.com`
  * After DNS propagates, enable **Enforce HTTPS**

### 2) Namecheap DNS

* **Advanced DNS** for `immersive-app.com`:

  * Add **CNAME**:

    * Host: `status`
    * Target: `immersive-app.github.io`
    * TTL: Automatic
* Ensure no other record exists on `status` (no A/AAAA/URL Redirect at the same host).

### 3) AWS SES (email sending)

* In **SES Console**:

  * Verify **domain** `immersive-app.com` and enable **DKIM** (add the SES-provided TXT/CNAMEs in Namecheap).
  * Create/verify a **sender** (e.g., `noreply@immersive-app.com`).
  * While in **SES Sandbox**, also **verify the recipient** address, or request production access.

### 4) AWS IAM (OIDC, no static keys)

* Create/confirm OIDC provider: `token.actions.githubusercontent.com` (AWS adds this once per account).

* Create an **IAM role** (e.g., `github-uptime-actions`) with:

  * **Trust policy** (restrict to this repo & branch):

    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
          },
          "Action": "sts:AssumeRoleWithWebIdentity",
          "Condition": {
            "StringEquals": {
              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
            "StringLike": {
              "token.actions.githubusercontent.com:sub": "repo:immersive-app/immersive-status:ref:refs/heads/main"
            }
          }
        }
      ]
    }
    ```

  * **Permissions policy** (least privilege for SES; optionally scope to your identity ARN):

    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "SendEmail",
          "Effect": "Allow",
          "Action": ["ses:SendEmail", "ses:SendRawEmail"],
          "Resource": "*"
          /* Or restrict:
          "Resource": "arn:aws:ses:<REGION>:<ACCOUNT_ID>:identity/immersive-app.com"
          */
        }
      ]
    }
    ```

* Copy the role ARN (e.g., `arn:aws:iam::<ACCOUNT_ID>:role/github-uptime-actions`).

### 5) GitHub Secrets

Repo → **Settings → Secrets and variables → Actions** → **New repository secret**:

* `AWS_ROLE_ARN` → your role ARN (from step 4)
* `FROM_EMAIL` → verified SES sender (e.g., `noreply@immersive-app.com`)
* `TO_EMAIL` → recipient (must be verified in Sandbox)

> Region is set inside the workflow (`AWS_REGION: eu-west-1`). Change if your SES region differs.

### 6) First run & verification

* Manually trigger: **Actions → Uptime Check → Run workflow**.
* Confirm the job logs show the HTTP status and (if down) an SES email send.
* Check that a commit updated `docs/status.json`.
* Visit **[https://status.immersive-app.com](https://status.immersive-app.com)** — the page should reflect the latest result.

### 7) Customize (optional)

* **Frequency**: edit the cron in `.github/workflows/uptime.yml`.

  > GitHub Actions cron runs in **UTC**.
* **Timeout**: `TIMEOUT_SECONDS` in the workflow `env`.
* **Endpoint**: `TARGET_URL` (defaults to `https://immersive-app.com/up`).
* **UI**: edit text/styles in `docs/index.html`.
* **History**: extend the script to append to `docs/history.json` for basic charts.

---

## Security notes

* **No AWS keys** in the repo. The Action uses **OIDC** to assume a role at runtime.
* **Secrets** (`AWS_ROLE_ARN`, `FROM_EMAIL`, `TO_EMAIL`) are stored as **GitHub Secrets**.
* IAM trust policy is **scoped to this repo and branch**; you can further constrain by workflow path if desired.
* Keep SES in Sandbox during testing; request production access when ready to email arbitrary recipients.

---

## Costs

* **GitHub Pages & Actions**: free for low usage.
* **AWS SES**: typically pennies per month (and free tier in some regions).
* **No egress/CDN costs** for the status page beyond normal GitHub hosting.

---

## Troubleshooting

* **Status page doesn’t update**: check that the Action committed `docs/status.json`; ensure Pages is set to `/docs`.
* **Custom domain not secure**: confirm CNAME points to `immersive-app.github.io`, re-save the domain in Pages, then enable **Enforce HTTPS**.
* **No emails**: verify SES identities (and recipient if in Sandbox), confirm region, and check IAM permissions.
* **Intermittent cache**: the page fetches `status.json` with `cache: 'no-store'`. If you suspect CDN lag, reload or append a cache-buster query (e.g., `status.json?t=...`) in the HTML.

---

## License

Choose your license model (e.g., proprietary or source-available). See `/LICENSE` for details.
