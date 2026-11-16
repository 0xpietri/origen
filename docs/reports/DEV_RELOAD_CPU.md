# Dev server CPU (`origen serve --reload`)

**Symptom.** With `uv run origen serve --reload` running, the PC sat around 80 °C; the
`origen` process used ~40 % of a core while idle.

**Cause.** uvicorn is installed without `watchfiles`, so `--reload` uses its polling
reloader (StatReload). It walks every `*.py` under the reload directories four times a
second. The default directory is the current one, the repo root, which holds `.venv`
(~3,400 `.py` files). The server process itself was idle; the reloader was the cost.

**Fix.** `origen serve --reload` now watches only the package (`src/origen`), which is
where code changes happen. Measured in the sandbox: reloader 40 % → under 1 % of a core;
editing a module still reloads.

**Production is not affected.** The image runs `origen serve` without `--reload`
(Dockerfile `CMD`), so there is no reloader. On factory, origen does not appear among the
top processes and the server sat at 7 % CPU when this was checked (2026-11-16).

## Try it

```sh
git pull && uv run origen serve --reload   # log says: Will watch for changes in these directories: ['…/src/origen']
```
