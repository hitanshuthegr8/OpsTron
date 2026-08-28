# OpsTron Bring-Up: Error Log & Explanations

A record of every defect hit while taking OpsTron from a fresh checkout to a running
system on Windows (Python 3.12) — what each looked like from the outside, how it was
found, and what it generalizes to.

**Date:** 19 Aug 2026

## The through-line

Ten defects. **Not one was a logic error.** Every failure lived in configuration,
packaging, or the seam between two systems that each worked correctly on their own.
Four of them failed *silently* — no crash, no error, just wrong behaviour somewhere
downstream. Those are the expensive ones.

| # | Defect | Class | Signature |
|---|--------|-------|-----------|
| 01 | Env file resolved to wrong directory | Configuration | *(silent)* |
| 02 | LLM model decommissioned upstream | Third-party drift | `404 model_not_found` |
| 03 | No prebuilt wheel for platform | Packaging | `MSVC 14.0 required` |
| 04 | `sys.path` and data dir both off by one | Path arithmetic | `ModuleNotFoundError` |
| 05 | Frontend port absent from CORS list | Cross-service | *(preflight)* |
| 06 | Build variable compiled to empty string | Build-time config | `404` on Pages |
| 07 | Post-login redirect to dead port | Cross-service | *(silent)* |
| 08 | Upstream status propagated verbatim | Misleading status | `422` (GitHub's) |
| 09 | Error detail discarded by API client | Error plumbing | *(silent)* |
| 10 | Webhook target not publicly reachable | Architectural | `422` validation |

---

## 00 — Orientation: the decoy `.git`

`git log` failed with *"not a git repository"* even though a `.git` directory was
plainly there. It was empty. The real project sat one level deeper in a same-named
subfolder with its own valid `.git`.

```
OpsTron/
├── .git/          ← empty, no HEAD, no objects
└── OpsTron/       ← the actual repository
    ├── agent/     FastAPI backend, 32 routes
    ├── lov_frontend/
    └── runbooks/
```

**Lesson:** when a tool insists something doesn't exist, check whether you're looking
at a decoy. An empty directory with the right name is not the thing.

---

## 01 — Every credential read as empty

**Class:** Configuration · **Silent failure**

### Symptom

None. The app imported cleanly, started cleanly, reported healthy. Every API key was
an empty string at runtime, despite a fully populated `.env` in the repository.

### How I found it

Not by reading code — by printing what the code actually *resolved to*. I asked the
settings object for both its values and the path it believed it was reading:

```
GROQ set:        False
SUPABASE set:    False
env_file:        ...\OpsTron\agent\.env
env_file exists: False   ← the file is at the repo root, not here
```

### Root cause

`settings.py` built its env path by walking three directories up from itself, landing
in `agent/`. The `.env` lived one level higher, at the repository root.

### Fix

A resolver that checks both locations and returns the first that exists, so the same
checkout works either way.

### Generalizes to

**pydantic-settings fails open.** A missing `.env` is not an error — every field
silently falls back to its default. That turns a config mistake into a runtime mystery
three layers away. Any config loader that defaults rather than raises deserves an
explicit startup assertion. This codebase *had* one (`validate_startup`), but it only
ran in production — exactly backwards from where a developer needs the feedback.

---

## 02 — The model had been decommissioned

**Class:** Third-party drift · **Loud failure**

### Symptom

With credentials finally loading, the four-agent pipeline ran and returned
`"root_cause": "analysis_failed"`. Two of four agents had thrown.

```
Groq invocation failed: Error code: 404 — {'error': {'message':
'The model `llama-3.3-70b-versatile` does not exist or you do not have
access to it.', 'code': 'model_not_found'}}
```

### How I found it

The status code did the work. **404, not 401** — the key authenticated fine and the
*resource* was missing. That single distinction ruled out the entire class of "bad
credentials" theories. Rather than guess a replacement, I asked the provider what the
key could actually reach:

```
GET https://api.groq.com/openai/v1/models  →  200
  openai/gpt-oss-120b      ← chosen
  openai/gpt-oss-20b
  qwen/qwen3.6-27b
  groq/compound
  (no llama-3.3 of any size)
```

### Fix

Rather than swap one hardcoded string for another, made the model a setting
(`GROQ_MODEL`) with a working default. The next decommission becomes an env-var edit,
not a code change.

### Generalizes to

**Read the status code before reading the message.** 401 = *who are you*, 403 = *not
allowed*, 404 = *no such thing*, 422 = *understood but refused*. Each points at a
different layer, and getting this right collapses the search space immediately.

Second point: hosted model names are perishable. Anything naming a vendor's model is
configuration, not source code.

---

## 03 — A dependency that cannot install on this platform

**Class:** Packaging · **Loud failure**

### Symptom

Runbook search — one of the four advertised agents — was dark. The vector store logged
*"ChromaDB unavailable"* and degraded gracefully, so nothing crashed; the feature just
quietly did not exist.

### How I found it

The warning named the cause (`No module named 'chromadb'`), but installing the pinned
version failed more interestingly:

```
Building wheel for chroma-hnswlib (pyproject.toml) ... error
  building 'hnswlib' extension
  error: Microsoft Visual C++ 14.0 or greater is required.
```

### Root cause

`chromadb==0.4.24` depends on `chroma-hnswlib`, which ships no prebuilt wheel for
Python 3.12 on Windows. With no wheel, pip falls back to compiling C++ from source,
which needs a toolchain this machine doesn't have.

### Fix

Not installing a compiler — moving to `chromadb>=1.0`, which distributes prebuilt
binaries and drops the hnswlib compile step entirely. Verified with
`--only-binary=:all: --dry-run` *before* committing to the install.

### Generalizes to

**"Requires build tools" means pip found no wheel for your platform.** The instinct is
to install the compiler; the cheaper move is usually to find a version that ships a
wheel for your Python and OS.

Note the interaction with graceful degradation here: the try/except around the import
kept the app alive, which is good engineering — but it also meant a headline feature
was missing with only a `WARNING` to show for it. **Graceful degradation and silent
absence are one line apart.**

---

## 04 — Two off-by-one path bugs in one twelve-line script

**Class:** Path arithmetic · **Loud failure**

### Symptom

The runbook loader wouldn't reach its first statement.

```
ModuleNotFoundError: No module named 'app'
```

### Root cause

Two independent miscounts of the same kind:

1. The `sys.path` insert walked up two levels (reaching `agent/app`) when it needed
   three (`agent/`).
2. Once fixed, the runbooks directory resolved to `agent/runbooks` — which doesn't
   exist; the files live at the repository root.

### Fix

Corrected the `sys.path` depth, and gave the directory lookup the same
check-both-locations treatment as the `.env`. All three runbooks indexed on the next run.

### Generalizes to

**Nested `os.path.dirname` calls are unreadable and therefore untrustworthy.** Three of
the ten defects here were this exact shape. Nobody can verify
`dirname(dirname(dirname(abspath(__file__))))` by eye — which is precisely why it stays
wrong. `pathlib`'s `Path(__file__).parents[2]` is countable at a glance, and anchoring
on a known marker file beats counting levels at all.

---

## 05 — Backend and frontend disagreed about the port

**Class:** Cross-service config · **Silent failure**

### Symptom

None yet — caught before it could bite, which is the only reason it was cheap.

### How I found it

Comparing two things that are supposed to agree. The Vite banner announced port
**8080**; the backend's computed CORS allowlist did not contain it:

```
vite   → http://localhost:8080
cors   → ['...:3000', '...:5173']   ← 8080 absent
```

### Root cause

The frontend's build preset pins 8080, but the backend's development CORS defaults were
written for the more common 3000 and 5173. Nobody had reconciled them.

### Generalizes to

**A CORS failure surfaces in the browser, far from its cause.** The server logs a clean
200 for the preflight and moves on; only the client sees the block, as a console error
that names no misconfigured setting. When two services must agree on a value, print both
and compare — don't read each one separately and assume.

---

## 06 — A 404 on the deployed site from an empty build variable

**Class:** Build-time config · **Silent failure**

### Symptom

Clicking *Continue with GitHub* on the deployed Pages site landed on
`hitanshuthegr8.github.io/auth/github/login` — a GitHub Pages 404.

### How I found it

The URL itself was the evidence. It pointed at the *frontend's* own origin for a
*backend* route, which only happens if the base URL is empty. One grep confirmed the
mechanism:

```js
export const BACKEND = import.meta.env.VITE_BACKEND_URL || "";
...
window.location.href = `${BACKEND}/auth/github/login`;
                        └─ empty → path resolves against the current origin
```

### Root cause

The deploy workflow injects `VITE_BACKEND_URL` from a repository secret
(`OPSTRON_BACKEND_URL`) that was never set. Vite substitutes build-time variables
literally, so an unset secret compiles to `""` and ships that way.

I confirmed the *local* build was unaffected by fetching the dev server's transformed
module and reading the value Vite had actually inlined — evidence rather than assumption.

### Generalizes to

**`|| ""` converts a missing configuration into a plausible wrong answer.** An empty
base URL doesn't throw; it silently rewrites every absolute call into a relative one.
And because this is build-time substitution, the mistake is baked into the artifact —
you cannot fix it by changing an environment variable on the host. Fail the build on a
missing required variable instead of defaulting it.

---

## 07 — Login redirected to a port with nothing on it

**Class:** Cross-service config

### Symptom

OAuth would have completed successfully and then dropped the user on `localhost:3000`,
where no server runs.

### How I found it

Read the callback handler's last line *before* testing it. It redirects to
`{FRONTEND_URL}/login?token=…`, and `FRONTEND_URL` was 3000 while the frontend was on 8080.

### Fix

Repointed `FRONTEND_URL`. Also verified the app's `/OpsTron` basepath redirect preserves
the query string — otherwise the session token would be stripped in transit and login
would fail in a far more confusing way:

```
/login?token=TESTTOKEN123
  → /OpsTron/login?token=TESTTOKEN123   token survives ✓
```

### Generalizes to

**Trace the whole redirect chain, not just the endpoints.** Multi-hop auth flows fail at
the hops. Testing "does login start" and "does the callback return 200" would both have
passed while the user still ended up nowhere.

---

## 08 — A 422 that belonged to someone else's API

**Class:** Misleading status · **Loud failure**

### Symptom

Installing the repository webhook returned `422 Unprocessable Entity` from our own
endpoint. In FastAPI, 422 almost always means request-body validation failed — so the
obvious theory was a malformed payload.

### How I found it

That theory was wrong, and disproving it was the useful step:

1. Checked the field contract on both sides — the frontend sent all four required
   fields, and `/integrations/repos` did return the `owner` field it depended on.
2. Probed the endpoint directly and found that **auth runs before body validation**:
   every unauthenticated request returns 401, never 422. So a 422 could only mean auth
   had *passed*, putting the failure downstream.
3. The server log settled it:

```
httpx  POST https://api.github.com/repos/…/hooks  422 Unprocessable Entity
ERROR  GitHub webhook install failed: 422 — "GitHub cannot reach your
       backend URL (localhost is not publicly accessible)."
```

### Root cause

GitHub refuses to register a webhook pointing at `localhost`, because it could never
deliver to it. GitHub returned 422; our handler re-raised that status code verbatim, so
a third party's validation error arrived wearing our API's clothes.

### Generalizes to

**Propagating an upstream status code makes the failure lie about its origin.** A 422
from your own API means one thing to every developer who reads it; passing through a
vendor's 422 destroys that meaning. Translate upstream failures into your own vocabulary
— 502, or 400 with an explicit "upstream rejected this" — and keep the original in the log.

Corollary: the server log had the complete answer in plain English the entire time.
**Check what the system already wrote down before forming theories.**

---

## 09 — The good error message never reached the screen

**Class:** Error plumbing · **Silent failure**

### Symptom

Clicking the button appeared to do nothing. The backend had already composed a precise,
actionable explanation — and the interface discarded it.

### Root cause

The API client stringified the raw response body and threw it. FastAPI wraps every error
as `{"detail": "…"}`, so the useful sentence was buried inside JSON punctuation, and
validation errors — which arrive as an *array* of objects — rendered as unreadable noise.

### Fix

Parse the envelope: pull out `detail` when it's a string, and flatten it to
`field: message` pairs when it's a list.

### Generalizes to

**An error the user cannot read is an error that does not exist.** Someone wrote a
genuinely excellent message here — it named the cause, explained why, and suggested the
fix. It was thrown away one layer from the screen. Error plumbing is a feature, and it's
worth building once in the shared client rather than at every call site.

---

## 10 — The webhook itself (diagnosed, not fixed)

**Class:** Architectural · **Open**

### Status

Defects 01–09 were mistakes. This one is a **constraint**: GitHub must reach the webhook
target over the public internet, and a laptop on `localhost:8001` cannot be reached from
GitHub's servers. No amount of code changes that.

### Options

- Expose the local backend through a tunnel (ngrok/cloudflared) and register that public
  URL. Note this puts your local backend on the public internet while it runs.
- Deploy the backend (`railway.toml` is already in the repo) and point the webhook at the
  deployed address. This also unblocks the GitHub Pages site, since you'd finally have a
  URL for the `OPSTRON_BACKEND_URL` secret.

### Generalizes to

**Separate "this is broken" from "this cannot work that way."** Inbound webhooks are a
structural constraint on local development: any service that must call *you* cannot reach
a private machine. Recognizing that class early saves hours of looking for a bug that
isn't there — and it's worth being able to articulate, because it shows you understand the
network topology rather than just the code.

---

## Method — the moves that earned their keep

**1. Print what resolved, not what was written.**
Source code states intent; runtime state is fact. Defect 01 was invisible in the source
and obvious the moment the resolved path was printed alongside the values it produced.

**2. Read the log the system already wrote.**
Defect 08's full explanation sat in the server log while the browser console showed only
a status number. Both were available; only one was being read.

**3. Let the status code choose the layer.**
401 vs 404 eliminated every credential theory in defect 02. Probing auth-vs-validation
ordering proved the payload was innocent in defect 08.

**4. Test the layer you changed, then end to end.**
Each fix was confirmed at its own level (settings reload, direct pipeline call) and then
again over HTTP. A unit that works inside a process can still fail across one.

**5. Compare the two things that must agree.**
Port mismatches, base URLs, redirect targets. Reading each side separately invites the
assumption that they match; printing both side by side does not.

**6. Verify the install before committing to it.**
A `--dry-run` answered whether prebuilt wheels existed in seconds, instead of discovering
a missing compiler partway through a long install.

---

## Files changed

| File | Change |
|------|--------|
| `agent/app/core/config/settings.py` | `.env` resolver (agent/ or repo root); added `GROQ_MODEL`; added port 8080 to dev CORS |
| `agent/app/core/llm.py` | Model read from `GROQ_MODEL` instead of hardcoded |
| `agent/app/db/load_runbooks.py` | Fixed `sys.path` depth; runbooks dir resolver |
| `lov_frontend/opstronic-delight/src/lib/api.ts` | Unwrap FastAPI `{"detail": …}` so errors reach the UI |
| `.env` | `FRONTEND_URL` → `http://localhost:8080` |

**Environment notes:** `chromadb>=1.0` installed (the pinned `0.4.24` cannot build on
Windows + Python 3.12); frontend `.env` created with
`VITE_BACKEND_URL=http://localhost:8001`.
