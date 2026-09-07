# Engineering Learning Log

Every entry is a real problem hit while building OpsTron, written so the *concept* survives after the fix is forgotten. Trivial changes are not recorded here.

Mastery levels: **Understand** (can explain) · **Read** (can follow the code) · **Modify** (can change it safely) · **Implement** (can build it fresh) · **Architect** (can design the approach)

---

## 1. A version pin is a bet on platform coverage, not just on a version

**Problem.** `pip install -r requirements.txt` failed on `chromadb==0.4.24`.

**Root cause.** `chromadb 0.4.x` depends on `chroma-hnswlib==0.7.3`, which publishes no wheel for CPython 3.12 on Windows. pip fell back to building it from source and needed an MSVC toolchain that wasn't installed. Nothing about the pin was *wrong* — the version simply predates the interpreter being used, and wheel availability is a property of time, not correctness.

**Concept.** Python packaging: wheels vs source distributions, ABI tags (`cp312`), platform tags (`manylinux_2_17` vs `manylinux_2_28`), and how an exact pin freezes the *build environment assumptions* alongside the version.

**Why it matters in OpsTron.** The backend deploys to Linux on Render and develops on Windows. Those two platforms have different wheel availability for the same pin, so a dependency that installs locally can fail in production and vice versa — which is exactly what happened next (entry 2).

**Solution.** Relaxed to `chromadb>=1.0`, which is wheel-only and needs no compiler. The `numpy<2.0` pin existed solely for `chromadb 0.4.x` and was dropped with it.

**Alternatives.** Install MSVC build tools (fixes one machine, not CI or teammates); pin an older Python (gives up 3.12); vendor a wheel (unmaintainable). Relaxing the range fixes it everywhere at once.

**Location.** `agent/requirements.txt`

**Learn.** Given a failing pin, determine whether a wheel exists for your interpreter and OS *before* concluding the package is broken. Read a wheel filename and say which Pythons and platforms it serves.

**Mastery:** Understand → Modify

**Exercise.** Run `pip download chromadb==0.4.24 --only-binary=:all: --python-version 3.12 --platform manylinux_2_17_x86_64`. Explain in one sentence why it fails and which specific dependency causes it.

---

## 2. The same requirements file resolves differently on different platforms

**Problem.** The Render build failed with `ResolutionImpossible` while the identical file installed fine on Windows.

**Root cause.** `chromadb 1.0.x` hard-pins `fastapi==0.115.9`. Render's build image only had `manylinux_2_17` chromadb wheels available, so pip backtracked down into the `1.0.x` line — where every candidate demands that exact FastAPI. Our `fastapi==0.115.6` made the resolution unsatisfiable. On Windows pip reached `chromadb 1.5.9`, which doesn't pin FastAPI at all, so the conflict never appeared.

**Concept.** Dependency resolution is a constraint-satisfaction search whose *candidate set* depends on platform tags. Two machines running the same `requirements.txt` explore different search spaces. Exact pins on libraries that other packages also pin is the classic way to make that space empty.

**Why it matters in OpsTron.** "Works on my machine" here is not sloppiness — it is a real, reproducible difference in available wheels. Any future dependency change must be validated against the deployment platform, not just locally.

**Solution.** `fastapi>=0.115.9,<0.116`. Verified by reproducing the failure locally with `--platform manylinux_2_17_x86_64` before and after.

**Alternatives.** Pin chromadb to a version that doesn't pin FastAPI (fragile — depends on wheels being available); vendor a constraints file (more machinery than the problem needs).

**Location.** `agent/requirements.txt`

**Learn.** Simulate another platform's resolution locally with `pip install --dry-run --python-version --platform --only-binary=:all:`. This turns a 10-minute failed deploy into a 30-second local check.

**Mastery:** Understand → Modify

**Exercise.** Reproduce the original failure: resolve `chromadb==1.0.12` together with `fastapi==0.115.6`. Then explain why adding `--platform manylinux_2_28_x86_64` changes the outcome.

---

## 3. A silently chosen value must never be hardcoded somewhere else

**Problem.** The frontend loaded perfectly and every API call failed, with no server-side error.

**Root cause.** The backend allowlisted CORS origins `5173` and `3000`. Vite defaults to `8080` and, when that port is taken, prints one grey line and serves on `8081` instead. The browser then sent an `Origin` the server had never heard of. The server never logs it, because a blocked preflight never reaches application code.

**Concept.** CORS is enforced by the *browser* using headers the server returns. A rejected origin is invisible server-side. More generally: when one component picks a value at runtime, no other component may hardcode that value.

**Why it matters in OpsTron.** Frontend and backend are separate origins in every environment — localhost in dev, `github.io` → `onrender.com` in production. CORS is load-bearing, not incidental.

**Solution.** In non-production, allow any localhost port via `allow_origin_regex`. Production keeps the explicit allowlist.

**Alternatives.** Add 8081 to the list (breaks on the next collision); force `--strictPort` (fails the dev server instead of adapting); proxy the API through Vite (hides a real production difference during development).

**Location.** `agent/app/core/config/settings.py::cors_origin_regex`, `agent/main.py`

**Learn.** Explain why a CORS failure appears only in the browser and produces no server log. Know which requests trigger a preflight.

**Mastery:** Understand → Implement

**Exercise.** With the backend running, `curl -X OPTIONS -H "Origin: http://localhost:9999" -H "Access-Control-Request-Method: GET" http://localhost:8001/health -D -`. Explain what the browser would do with that response.

---

## 4. A fallback that is also a valid value hides its own failure

**Problem.** `cors_origins()` computed `configured or [frontend]`. Setting `CORS_ALLOWED_ORIGINS` silently dropped `FRONTEND_URL` from the allowlist.

**Root cause.** `or` treats an empty list as "not supplied", which is right, but the branch made the two settings mutually exclusive when they are semantically additive. `FRONTEND_URL` is where the OAuth callback redirects the browser — so a deployment that set both ended up refusing the exact origin it sends users back to, with no error anywhere.

**Concept.** Configuration precedence design. "Default unless overridden" and "always included" are different relationships; choosing the wrong one produces failures that are invisible because nothing errors.

**Why it matters in OpsTron.** `FRONTEND_URL` has two jobs — OAuth redirect target and trusted origin. Any config where one setting silently disables another is a latent outage.

**Solution.** Always include `FRONTEND_URL`, then union with the configured list.

**Alternatives.** Document the interaction (documentation does not prevent the failure); drop `FRONTEND_URL` from CORS entirely and require the allowlist (more config, easy to get wrong).

**Location.** `agent/app/core/config/settings.py::cors_origins`, `agent/tests/test_config_and_security.py`

**Learn.** For each pair of settings, decide deliberately: override, merge, or independent. Write the test that pins that decision.

**Mastery:** Understand → Implement

**Exercise.** Construct a `Settings` with both values set and assert both appear. Then break it back to `configured or [frontend]` and watch which test fails.

---

## 5. Client libraries validate credential *shape*, not just validity

**Problem.** Supabase failed at startup with `Invalid API key` — before any network call.

**Root cause.** `supabase-py 2.10.0` matches the key against a JWT regex (`xxx.yyy.zzz`). Supabase now issues `sb_secret_...` keys, which contain no dots, so the client rejected them locally. The error names the key, which points the reader at credentials rather than at the library version.

**Concept.** Reading a credential's *shape*. JWTs are three base64 segments carrying claims; opaque tokens are random strings carrying nothing. A library that predates a provider's format change will reject valid credentials offline.

**Why it matters in OpsTron.** Supabase holds sessions and incident history. This failure degrades the app to stateless mode with a misleading message, so time gets spent regenerating perfectly good keys.

**Solution.** `supabase>=2.31`, which accepts both formats. That forced `httpx>=0.28` and `pydantic>=2.11.7` — its `realtime` dependency requires them.

**Alternatives.** Use a legacy JWT `service_role` key (works today, but Supabase is deprecating them — this trades a fix for a deadline).

**Location.** `agent/requirements.txt`, `agent/app/db/supabase_client.py`

**Learn.** When an auth error appears before any network request, suspect client-side validation. Distinguish a JWT from an opaque token at a glance.

**Mastery:** Understand → Modify

**Exercise.** Decode the payload of any JWT with base64. Then explain why `sb_secret_...` cannot be decoded that way and what the server must therefore do differently to validate it.

---

## 6. Distinguish two failures by which error the provider returns

**Problem.** GitHub login failed with `The code passed is incorrect or expired` on every fresh attempt.

**Root cause.** The OAuth app's registered callback pointed at a *different deployment's* backend. So: login started at our backend and issued a code for our `client_id`; GitHub delivered that code to the other server; that server exchanged it using *its own* `client_id`; GitHub rejected a code issued for a different client. The error blames the code, which is the one thing that was fine.

**Concept.** The OAuth 2.0 authorization-code flow, and specifically that the callback URL is a property of the *OAuth app registration*, not of the client that started the flow. Also: error taxonomy as a diagnostic tool.

**Why it matters in OpsTron.** OAuth spans three parties across two hosts, and this project has a near-identically-named upstream deployment. Reading the error precisely is what separates a 5-minute fix from an afternoon.

**Solution.** Point the callback at this fork's backend.

**Alternatives.** Pass `redirect_uri` explicitly at authorize *and* token exchange — GitHub then validates them against each other, failing louder and earlier. Worth doing as a hardening step.

**Location.** `agent/app/api/routes/auth.py::github_callback`

**Learn.** Trace all four legs of the code flow and name which party holds which secret at each step. Know that `incorrect_client_credentials` means a wrong secret, while `bad_verification_code` means a spent, expired, or *wrong-client* code.

**Mastery:** Understand → Implement

**Exercise.** `POST https://github.com/login/oauth/access_token` with a real `client_id`, a wrong secret, and a junk code. Then with a fake `client_id`. Explain what the two different responses prove about the order GitHub validates things in.

---

## 7. Default timeouts are a policy decision you inherit by accident

**Problem.** The same OAuth exchange occasionally failed even when everything was configured correctly.

**Root cause.** `httpx.AsyncClient()` defaults to a **5 second** timeout. A cold Render free-tier container can exceed that on an outbound call. GitHub burns the single-use code the moment it processes the exchange, whether or not the response reaches us — so a timeout destroys the code and the retry reports "expired", blaming the code rather than the timeout.

**Concept.** Timeouts as correctness, not just latency. With non-idempotent operations, a client-side timeout leaves the server having done the work and the client believing it failed.

**Why it matters in OpsTron.** The backend makes outbound calls to GitHub, Groq and Supabase, several of them non-idempotent. Cold starts are normal on free tiers.

**Solution.** Explicit 30s timeouts on both calls, plus a logged code fingerprint so a duplicated callback is identifiable.

**Alternatives.** Retry the exchange (actively harmful — the code is spent); raise the timeout globally (a shared default is worse than a per-call decision).

**Location.** `agent/app/api/routes/auth.py`

**Learn.** For every outbound call, state the timeout and what happens if it fires *after* the server acted. Identify which calls are safe to retry.

**Mastery:** Understand → Implement

**Exercise.** Find every `httpx` call in `agent/app/`. For each, say the timeout and whether a retry is safe. At least one is not.

---

## 8. Scripts named `test_*` are not a test suite

**Problem.** Three files named `test_*.py`, 105 lines total, no assertions, and pytest not installed.

**Root cause.** They printed output for a human to read. Nothing could fail, so nothing was verified — while the naming implied coverage that did not exist.

**Concept.** What makes a test a test: a stated expectation that can fail, deterministically, without a human interpreting output. And the unit/integration split — tests that hit paid, networked, non-deterministic services must be opt-in.

**Why it matters in OpsTron.** The riskiest surfaces are exactly the ones nothing covered: the public demo boundary, CORS resolution, and production startup validation.

**Solution.** 26 deterministic tests plus 1 marked integration test, with `addopts = -m "not integration"` so the default run makes no billed call. The old scripts moved to `agent/scripts/manual/` with a README saying they are not tests.

**Alternatives.** Add assertions to the existing scripts (they test the wrong things — imports succeeding, not behaviour being correct).

**Location.** `agent/tests/`, `agent/pytest.ini`, `agent/scripts/manual/`

**Learn.** Write a test that fails for exactly one reason. Decide, per test, whether it may touch the network.

**Mastery:** Understand → Implement

**Exercise.** Delete the `assert` in `test_culprit_precedes_the_first_error`, run the suite, and observe it still passes. That is what all three original files were.

---

## 9. Make the security boundary structural, not defensive

**Problem.** The demo must run the RCA pipeline for anonymous visitors. `/analyze` already did this unauthenticated — but it accepts an arbitrary uploaded log file.

**Root cause.** Publishing that from a public page would put attacker-controlled text into an LLM prompt and hand out unbounded model spend to anyone with `curl`.

**Concept.** Eliminating a class of attack by construction rather than by filtering. Validating hostile input is an ongoing obligation; never accepting it is a one-time design choice. Also: prompt injection as the LLM-specific case of untrusted input.

**Why it matters in OpsTron.** Every LLM call costs money and every prompt is an injection surface. The demo is the only unauthenticated surface that spends, so its boundary carries the most weight.

**Solution.** The demo accepts only a scenario **id**, used solely as a key into a fixed server-side mapping. An unknown key is refused before anything runs, so no visitor-controlled text reaches a prompt, a database write, or an outbound request. Rate limited per client IP on top.

**Alternatives.** Sanitise uploaded logs (you are now maintaining a filter against an adversary); require a captcha (blocks the recruiter, which defeats the point); cache one static response (stops being a demo of a working system).

**Location.** `agent/app/api/routes/demo.py`, `agent/app/demo/scenarios.py::get_scenario`

**Learn.** Given an untrusted input, ask whether it can be replaced by a choice from a fixed set. If yes, that is almost always the stronger design.

**Mastery:** Understand → Architect

**Exercise.** `POST /demo/scenarios/anything/analyze`. Explain why a 404 — rather than a 500 or a slow 200 — is the evidence that no model call was reachable.

---

## 10. A demo must not lie about what it is

**Problem.** A demo needs to be reliable, which tempts you toward canned output. Canned output that looks generated is a lie about your own system.

**Root cause.** The tension is real: live LLM calls are non-deterministic and can fail; static fixtures always look perfect.

**Concept.** Provenance as a first-class API concept — the response states which fields are fixtures and which were produced at request time. Honest demos are also better demos, because "this ran just now" is the impressive claim.

**Why it matters in OpsTron.** The whole product claim is that the analysis is genuine. A recruiter discovering the demo was a recording would discredit everything else.

**Solution.** The incident is a labelled fixture; the analysis is genuinely produced by the same orchestrator serving authenticated users. A `provenance` object ships with every response and is rendered above the fold. A pipeline failure returns **503** rather than substituting a stored report.

**Alternatives.** Cache the last good RCA as a fallback (rejected — a demo that silently serves a fixture when the pipeline is down is indistinguishable from one that never worked).

**Location.** `agent/app/api/routes/demo.py::PROVENANCE`, `lov_frontend/opstronic-delight/src/routes/demo.tsx::ProvenanceBanner`

**Learn.** Separate "reliable" from "pre-recorded". Design failure states you are willing to show a stranger.

**Mastery:** Understand → Architect

**Exercise.** Stop the backend and load `/demo`. Decide whether the error state is one you would be happy for a recruiter to see, and change it if not.

---

## 11. Encoding is a property of the stream, not the message

**Problem.** Every Windows startup printed a `UnicodeEncodeError` traceback that looked like a crash.

**Root cause.** Windows consoles default to cp1252. Log messages contain non-ASCII characters (check marks, em dashes). Python's logging swallows the failure so the app kept running — but the traceback buried the real startup lines.

**Concept.** Text encoding at I/O boundaries. `str` is abstract; bytes on a stream are not. The fix belongs at the boundary, not in every message.

**Why it matters in OpsTron.** Development is on Windows and deployment is on Linux. Fixing the messages would have been endless and would silently regress.

**Solution.** `sys.stdout.reconfigure(encoding="utf-8")` before logging is configured.

**Alternatives.** Strip non-ASCII from all log messages (endless, and regresses on the next emoji).

**Location.** `agent/main.py`

**Learn.** When encoding breaks, identify which boundary is converting and fix it there.

**Mastery:** Understand → Modify

**Exercise.** Find another output path in this codebase that could hit the same error and is not covered by the stdout fix.

---

## 12. Idempotency has to be checked statement by statement

**Problem.** Re-running `schema.sql` failed with `42710: policy ... already exists`, and every statement after it was skipped — leaving the schema half-applied.

**Root cause.** Tables and indexes used `IF NOT EXISTS`. `CREATE POLICY` and `CREATE TRIGGER` have no such form in Postgres. The file *looked* idempotent because the first 20 statements were.

**Concept.** Idempotency as a property of each statement, not of a file. Also: partial failure in a non-transactional script is worse than total failure, because the reported error names one thing while many others silently did not happen.

**Why it matters in OpsTron.** Setup instructions tell users to run this file. A newcomer re-running it would get a confusing error and a broken database.

**Solution.** `DROP ... IF EXISTS` before each of the 8 policies and the trigger.

**Alternatives.** Wrap in a transaction (all-or-nothing, but re-running still fails); use a migration tool like Alembic (correct for a team; heavier than this project needs today).

**Location.** `agent/app/db/schema.sql`

**Learn.** For each DDL statement, know whether re-running is safe. Verify by running the file twice.

**Mastery:** Understand → Implement

**Exercise.** Run `schema.sql` twice against a scratch project. Then remove one `DROP POLICY IF EXISTS` and count how many later tables fail to appear.

---

## 13. `.gitignore` globs are more literal than they look

**Problem.** A `.env.bak-20260907` containing a live service key sat untracked and **unignored** in the repo.

**Root cause.** The rule was `*.env`, which matches files *ending* in `.env`. `.env.bak-20260907` ends in a timestamp. One `git add .` would have published a credential.

**Concept.** Gitignore pattern semantics, and the difference between "not committed yet" and "protected from being committed".

**Why it matters in OpsTron.** The project has several env files across two subprojects, and backups get made during debugging — exactly when you are least careful.

**Solution.** Added `.env`, `.env.*` and `*.env.*`, with `!.env.example` so templates stay tracked. Verified with `git check-ignore -v`.

**Alternatives.** Delete backups manually (relies on memory at the worst moment).

**Location.** `.gitignore`

**Learn.** Verify ignore rules with `git check-ignore -v <path>` instead of assuming. Know that a leading `*` does not match a leading dot the way you might expect.

**Mastery:** Understand → Modify

**Exercise.** Create `agent/.env.backup` and `agent/prod.env.old`. Predict which the old `*.env` rule caught, then check with `git check-ignore -v`.

---

## 14. Two similarly-named deployments will eventually be confused

**Problem.** Hours were spent diagnosing a "broken" backend that was healthy — the wrong one was being tested.

**Root cause.** The upstream project deploys `opstronic.onrender.com`; this fork deploys `opstron.onrender.com`. The frontend build had upstream's URL baked in as a fallback, copied from upstream's own source default. Upstream's server answered normally, allowed only upstream's origin, and redirected OAuth to upstream's site — so every symptom looked like a misconfiguration of *our* deployment.

**Concept.** Environment identity. A deployment should be able to tell you which build and which config it is running; otherwise you debug by inference.

**Why it matters in OpsTron.** A fork inherits the upstream's defaults, and defaults that point at someone else's infrastructure are silent, not loud.

**Solution.** Corrected the build fallback to this fork's backend and verified the constant in the deployed bundle.

**Alternatives.** Require the env var with no fallback (fails loudly — arguably better, but breaks the deploy for anyone who forgets). A build-info endpoint exposing commit SHA would have made this diagnosable in seconds and is worth adding.

**Location.** `.github/workflows/deploy-frontend.yml`, `lov_frontend/opstronic-delight/src/lib/api.ts`

**Learn.** Confirm *which* instance you are talking to before diagnosing it. Fingerprint a deployment from the outside.

**Mastery:** Understand → Architect

**Exercise.** Design a `/version` endpoint returning commit SHA and build time. State how it would have shortened this to one request.
