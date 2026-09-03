# ICU course-seat monitor

Checks the public ICU ISC pre-registration list for registration number
`21342` (ISC104 Foundation of Programming). It does **not** use or store an
ICU password.

## What it does

- Reads `https://course-reg.icu.ac.jp/reg/prereg_clist/ISC.html`.
- Finds the `LEFT` value for course registration number `21342`.
- On the transition from 0 to one or more seats, sends a webhook notification.
- Keeps its small state file so it does not alert repeatedly while the same
  space remains available.

It deliberately does not log in or submit registration. A background service
cannot safely retain the 90-minute login ticket, and registration needs to be
reviewed and submitted by you.

## Run once

```sh
cd /path/to/course-seat-monitor
python3 monitor.py
```

## Add an alert

Set `WEBHOOK_URL` to a private Discord or Slack-compatible incoming webhook:

```sh
export WEBHOOK_URL='https://example.invalid/private-webhook'
python3 monitor.py
```

Do not commit the webhook URL. It is a secret with permission to send messages
to that channel.

## Run every five minutes on a cloud server

Put this directory on any always-on Linux server, install Python 3, and add:

```cron
*/5 * * * * cd /opt/course-seat-monitor && /usr/bin/python3 monitor.py >> monitor.log 2>&1
```

Use a persistent disk/volume so `state.json` survives restarts. A small VPS or
home server is more reliable for exact five-minute checks than GitHub Actions,
whose scheduled jobs can start late.

## No VPS: GitHub Actions

This folder also includes `.github/workflows/seat-monitor.yml`. Create a
**private** GitHub repository, upload this folder, then add `WEBHOOK_URL` in
**Settings → Secrets and variables → Actions**. GitHub will run it on its own
servers every five minutes, even when your computer is off.

Because each GitHub Actions run is a fresh machine, it can send a notification
every five minutes while a seat remains open. That is intentional: it prevents
a one-time alert from being lost. GitHub's scheduler is not a real-time system,
so the run may occasionally start late; use a VPS if seconds matter.

## Container option

```sh
docker build -t icu-seat-monitor .
docker run --rm -v "$PWD:/state" -e STATE_FILE=/state/state.json \
  -e WEBHOOK_URL='https://example.invalid/private-webhook' icu-seat-monitor
```
