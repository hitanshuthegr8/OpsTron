# Concepts Learned — OpsTron

A running log of the *ideas* behind the problems hit on this project. `error_explanation.md`
records what broke and how it was diagnosed; this file records what is worth **remembering
after the bug is gone**.

Newest entries at the bottom.

---

## 1. `localhost` is a word, not an address

`127.0.0.1` / `localhost` means **"the machine running this code."** It is not a location —
it is a pronoun. It resolves differently depending on *who says it*.

- Your browser says `localhost:8001` → your laptop → your backend ✅
- GitHub's server says `localhost:8001` → *GitHub's* machine → nothing there ❌

This is why you can call out to a hundred APIs successfully and still be unreachable.

> **Analogy:** writing "come to my house" is perfectly clear when handed to someone in your
> kitchen, and useless when mailed, because the reader resolves "my house" to *their* house.

---

## 2. Direction of the call decides everything

Every network interaction has a caller and an answerer. Most confusion comes from not
noticing which role you need to play.

```
YOU ──calls──▶ GitHub / Groq / Supabase          ✅ always works
GitHub ──calls──▶ YOU                            ❌ needs a public address
```

Anything that must call **you** — webhooks, callbacks, push notifications — is a fundamentally
harder problem than anything you call. Recognise this class of feature early.

---

## 3. Why your laptop has no public address (NAT)

Think of an office building: one public phone number, many internal extensions.

- Your home network has one **public IP** from your ISP.
- Your laptop has a **private IP** (`192.168.1.102`) that only exists inside that network.
- Your router is the receptionist, and by default it forwards no incoming calls.

This is **NAT** (Network Address Translation). It is why billions of devices browse the
internet while almost none of them are reachable from it.

---

## 4. How tunnels (ngrok) actually work

A tunnel does **not** open a hole in your router. It inverts the direction:

```
YOUR LAPTOP ──opens & holds a line──▶ ngrok server (has a real public address)
                                              ▲
GitHub ──────────────calls────────────────────┘
```

Because *your machine* started the connection, NAT permits it. ngrok then publishes its own
public address, and anything arriving there is pushed back down the line you already opened.

> **The trick:** an incoming call becomes a response on an outgoing one. This same pattern
> appears in WebSockets, long polling, and message queues.

---

## 5. Never let a client tell the server facts the server owns

The original webhook code had the **browser** decide the public callback URL:

```js
webhook_url: `${BACKEND}/notify-deployment`   // browser only knows "localhost:8001"
```

A browser cannot know the server's public address — it only knows how *it* reaches the server.
The fix was to make the backend authoritative via a `PUBLIC_URL` setting.

> **Rule:** the server owns its own address, its own secrets, its own identity. Anything a
> client asserts about those is a guess at best, and an attack at worst — a malicious client
> could have pointed the webhook at its own server.

---

## 6. Failing open vs failing closed

Code that hits a problem can either **stop loudly** or **continue quietly with a default**.
Quiet continuation is what makes bugs expensive.

| Example from this project | What it did | Result |
|---|---|---|
| `pydantic-settings` with a missing `.env` | every key → `""` | app "started fine", nothing worked |
| `VITE_BACKEND_URL \|\| ""` | URL → relative path | deployed site 404'd |
| ChromaDB import in `try/except` | feature silently absent | a headline agent just didn't exist |

Graceful degradation is good engineering — but **graceful degradation and silent absence are
one line apart.** The difference is whether anyone is told.

> **Practice:** for anything required, assert it at startup and crash with a clear message.
> A loud failure at boot beats a silent wrong answer three layers away.

---

## 7. HTTP status codes tell you which layer failed

Reading the number before the message collapses the search space instantly.

| Code | Means | Look at |
|---|---|---|
| 401 | Who are you? | credentials, tokens, session |
| 403 | I know you, you may not | permissions, scopes |
| 404 | No such thing | the resource / URL / model name |
| 422 | Understood, but refuse | the payload's *content* |
| 500 | I broke | the server's own logs |

Real payoff on this project: a Groq failure was **404, not 401** — proving the key was fine
and the *model name* was dead. That eliminated every "bad credentials" theory in one step.

---

## 8. A propagated status code lies about its origin

The webhook endpoint did this:

```python
raise HTTPException(status_code=response.status_code, detail=message)  # response = GitHub's
```

GitHub returned 422. Our API returned 422. But in FastAPI, 422 has a specific meaning —
*your request body failed validation* — so it pointed at entirely the wrong thing.

> **Rule:** translate upstream failures into your own vocabulary (`502`, or `400` with
> "upstream rejected this") and keep the original in the log. A status code is a contract with
> whoever reads it.

---

## 9. Check what the system already wrote down

The webhook failure had a complete, plain-English explanation sitting in the server log the
whole time. The browser console showed only a number.

> **Habit:** before forming theories, read the logs that already exist. The answer is often
> already written; it just wasn't where you were looking.

---

## 10. An error the user cannot read does not exist

The backend composed an excellent message — named the cause, explained why, suggested the fix.
The API client threw away the `detail` field, so it never reached the screen. The button
simply appeared to do nothing.

> **Error plumbing is a feature.** Build the unwrapping once in the shared client, not at
> every call site.

---

## 11. Two caches that disagree will loop forever

The `/login` ↔ `/onboarding` bounce. Two pieces of state were supposed to mean "logged in":

- `ops_token` — the session token, checked by the **API**
- `opstronic:state:v2` — the cached user object, checked by the **router**

On a 401, `clearAuth()` removed the token but **left the cached user**. So:

```
API says "logged out" → redirect to /login
  → router sees cached user → "logged in!" → redirect to /onboarding
    → onboarding calls the API → 401 → repeat forever
```

Note the codebase already had a correct cleanup (`logout()` cleared both). The bug was that
the *error path* used the incomplete one.

> **Rule:** if two stores represent one fact, either derive one from the other, or clear them
> in the same function. Never let an error path do a partial cleanup — that is exactly when
> the two halves drift apart.

---

## 12. In-memory state dies with the process

Sessions lived in a plain dictionary:

```python
active_sessions: dict = {}
```

Every backend restart logged everyone out. The code anticipated this and fell back to the
database — but the database was gone, so the fallback was dead too.

> **Two lessons.** First, in-memory state is invisible until the process restarts, and then
> it is everyone's problem at once — this is also why it breaks the moment you run more than
> one server. Second, **a fallback you never test is not a fallback.** It had been silently
> broken for the whole session.

---

## 13. Read the *shape* of a credential, not just its presence

Supabase rejected the key with "Invalid API key". Two separate problems, both visible from
the key's shape and one DNS lookup:

- The key was 41 chars starting `sb_sec…` — Supabase's **new** format. The pinned client
  expected the legacy JWT (`eyJ…`, two dots, ~200 chars).
- The project hostname returned **Non-existent domain**, while `supabase.com` resolved fine —
  proving the project itself was gone, not the network.

> **Habit:** when a credential is rejected, check its *format* against what the client expects,
> and confirm the host actually resolves. "Invalid API key" can mean wrong key, wrong format,
> or vanished project — three different fixes.

---

## 14. Ephemeral filesystems: "it persisted locally" is not persistence

Runbooks were indexed into ChromaDB on disk at `./db/chroma_data`. That worked locally
forever, because a laptop's disk survives the process. On Render it silently did not:

- Nothing ran the indexer at deploy time, so the store started **empty**.
- Even indexing it once by hand would not have stuck — hosted containers (Render, Railway,
  Heroku, most PaaS) have **ephemeral filesystems**. Anything written at runtime is gone on
  the next deploy, restart, or spin-down.

The result: RAG worked perfectly in development and was completely hollow in production.
Every RCA shipped without its remediation step, and nothing errored.

**The fix** was to rebuild the index during application startup, in the `lifespan` hook —
cheap for a small fixed set of documents, and it removes the dependency on disk outliving
the process entirely.

> **Rule:** on a hosted container, treat the filesystem as scratch space that vanishes.
> Anything that must survive belongs in a database, an object store, or gets rebuilt at boot
> from something in the image.

There is a wider lesson here too. This bug could only appear **in production**, because it
was caused by an environment difference, not by the code. Dev and prod differ in filesystem
persistence, available CPU, cold starts, network reachability, and installed wheels — and
every one of those has bitten this project at least once.

---

## 15. Measure before you claim a number

Latency looked like a great resume metric until it was measured three times in a row:

```
run 1:  8.4s
run 2: 38.3s
run 3: 53.0s
```

Same input, same endpoint, a 6x spread — free-tier CPU contention stacked on top of LLM
inference variance and two external API calls. Any single number picked from that would have
been indefensible under "how did you measure it?"

> **Rule:** quote numbers that are *structural* (endpoint counts, pipeline stages, scoring
> weights) or that you actually benchmarked under stated conditions. A number you cannot
> reproduce on demand is a liability, not an achievement — it invites exactly the question
> you cannot answer.

---

## 16. Choices vs results — which numbers actually count

Most "metrics" on a project are **design choices**, not outcomes:

| Choice (you decided it) | Result (you measured it) |
|---|---|
| 5 confidence signals | 92% retrieval precision@1 |
| 60-second dedup window | 22:1 event collapse under storm |
| 28 API endpoints | 231 of 242 events suppressed |
| 5 severity levels | 120 pages reduced to 3 |

Both belong on a resume, but they answer different questions. A choice shows you designed a
system. A **result** shows the design worked. Only the second survives "so did it actually
help?"

Measured on this project:

- **Runbook retrieval precision@1: 92% (11/12).** Twelve realistic incident phrasings, each
  with a known-correct runbook. The single miss — "502 bad gateway, no healthy upstreams"
  matched *api_timeout* instead of *service_down* — is genuinely ambiguous, which is a more
  honest answer than a suspicious 100%.
- **Event storm collapse: 22:1.** 242 raw events from three crashlooping containers reduced
  to 11 reaching the RCA layer — 95.5% suppressed.
- **Alert fatigue: 120 pages down to 3**, via the 5-minute per-service cooldown.

> **Rule:** design a small evaluation you can re-run on demand. Twelve hand-labelled queries
> took ten minutes to write and turned an unverifiable claim into a defensible one. And keep
> the miss in the number — a reported 100% invites doubt, while 92% with an explained failure
> invites a conversation you can win.
