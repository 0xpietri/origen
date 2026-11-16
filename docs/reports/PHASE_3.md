# Phase 3 report: deploy on factory (2026-11-16)

origen's deploy lives with the server's other deploys, in factory-panel
(`deploy/origen/`, `docs/deploy.md` "origen", report `docs/reports/origen-deploy.md`
there); nothing in this repository changes for it. Its details are the ones fixed
in 14.5 of the spec.

## Done
- CI of `main` at `5d27d28` (phase 2) is green and published the multi-arch image
  `ghcr.io/0xpietri/origen:5d27d286d9cd4d64c8824366f0fd85cd5656189c` (public).
- factory-panel: `deploy/origen/compose.yaml` (read-only root, no capabilities,
  no volumes, no secrets, `127.0.0.1:8800`, 256 MB), the Caddy site
  `origen.pietri.dev` and `origendeploy` (newest commit of main, or a given one to
  roll back; keeps the deployed and the previous image), with tests.
- Section 9: the Caddy site does not use the shared access log snippet; it writes
  its own log with the query string and the Referer removed, so no place reaches a
  log. origen already logs method, path, status and duration only.

## Tried
In the cloud sandbox, the published image under that compose file: healthy,
`/v1/sky` for 168 hours in 0.44 s, 85 MB of 256 MB in use, root read only.

## Commands (on factory, after the factory-panel PR is merged and pulled)
```
sudo ln -sf /srv/domains/pietri.dev/panel/deploy/origen/origendeploy /usr/local/bin/origendeploy
origendeploy                                                     # newest main, healthy check
sudo cp /srv/domains/pietri.dev/panel/deploy/origen/origen.pietri.dev.caddy /etc/caddy/sites/
sudo sh -c 'set -a; . /etc/caddy/crowdsec.env; caddy validate --config /etc/caddy/Caddyfile' && sudo systemctl reload caddy
curl -s https://origen.pietri.dev/healthz
```
Before them: the Cloudflare record `A origen.pietri.dev → 129.121.91.157`, proxied.
docs/deploy.md in factory-panel has the CrowdSec check and the log check.

## Not done here
- The run on factory itself, and Caddy's validation of the site file (the sandbox
  could not run Caddy).
- pietri.dev pointing its tick at origen: its own thread.
