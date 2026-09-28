# AI Native Call Center

An open-source call center where the AI is the default answer, not an add-on.

Calls arrive at FreeSWITCH and are answered by a voice model over a
speech-to-speech connection the application terminates itself. The model talks;
a flow steers the conversation and decides when a person is needed. When one
is, the caller is transferred into a real queue where real agents are waiting,
their SIP leg held by a companion Chrome extension. Everything the two halves
do lands in one call record.

It is **one Go binary** — REST API, event stream and the whole web interface
inside it — plus PostgreSQL and FreeSWITCH.

[简体中文](README.zh-CN.md) · [Deploying](deploy/README.md) ·
[Design](docs/design/00-overview.md)

<!-- Recorded from the agent desktop prototype (ui-test / CallDesk): an inbound
     call answered, the live transcript filling in, then after-call work. -->
![Agent desktop: an inbound call is answered, the live transcript fills in, then after-call work](docs/assets/agent-desktop.gif)

## Try it

On Linux:

```sh
curl -fsSL https://github.com/rasonyang/ai-native-callcenter/releases/latest/download/install.sh | sudo sh
```

On macOS (Colima or Docker Desktop), drop the `sudo`. The installer checks the
host first, asks for the voice provider and its key, generates every password
into `.env`, starts the published images and checks the running stack with
`aicc doctor`. It then prints the address and the admin password.

The stack comes up seeded with a team, two queues, six published bilingual
flows (each behind an English, a Chinese and a US number, the main line being
800-555-0199), eighteen simulated customer telephones and a week of history,
so the wallboard is not empty and a softphone can ring the bot straight away.
Install the [web-sip-phone](https://chromewebstore.google.com/detail/dkhaojcfjdcdpldokeokajkmambkbacp)
extension, sign in as an agent and dial 95001 (English) or 95002 (Chinese).
Options, upgrades, removal and the manual compose install:
[deploy/README.md](deploy/README.md).

### Supported platforms

Only combinations verified live (on 2026-09-28, with this release's images)
are listed:

| OS | Arch | Runtime | Versions | What was verified |
|---|---|---|---|---|
| Ubuntu 24.04.5 LTS | x86_64 | Docker Engine | Engine 29.8.0, Compose v5.5.1 | The installer end to end (install, rerun, `--external-ip`, `--upgrade`, `--uninstall` / `--purge`, preflight failures); `aicc doctor` all PASS; a WebRTC agent on another LAN machine (Chrome 154 on macOS, web-sip-phone 1.0.7) registered over `ws://` with two-way audio to the bot on 95001 |
| macOS 26.6.2 | arm64 | Colima (vz, port forwarder `grpc`) | Colima 0.10.3, Docker 28.4.0, Compose 5.1.4 | The macOS overlay stack; `aicc doctor` all PASS; a WebRTC agent on the same host with two-way audio (switch configuration from this release); installer preflight (`--check`) only. A full installer run on macOS is not yet verified |

- Colima: 0.10.3 is the oldest version verified, and it must run the `grpc`
  port forwarder (`colima start --port-forwarder grpc`); the default `ssh`
  forwarder does not forward UDP.
- Both images are published for `linux/amd64` and `linux/arm64`. The
  installer's preflight refuses a host whose architecture an image lacks; it
  never runs an image under emulation.
- Not yet verified: Docker Desktop, macOS 12 on Intel, and Linux
  distributions other than Ubuntu 24.04.

## What it does

**Answers with a model, not a menu.** The AI leg is a SIP endpoint inside the
application: FreeSWITCH bridges the caller to it and audio goes straight to the
provider — G.711 passed through byte for byte where the provider accepts it, so
nothing decodes or resamples on the way.

**Steers without scripting the conversation.** The model owns the dialogue; the
flow owns the phase. A phase carries instructions and a list of tools the model
may use; transitions fire on tool results. A phase may also carry a line of its
own — a greeting, a hand-over script, a goodbye — which the bot is meant to say
as written rather than paraphrase: `doubao` is handed the words to speak, the
other four providers are instructed to repeat them word for word. The built-in
tools may *refuse* —
"the queue is closed" is something to talk about, not an error — and the
persona, the rules and the bot's voice are published and versioned together.

**Hands over to people properly.** Transfers go into `mod_callcenter` queues,
and the agent's screen has popped by the time the phone rings: a
`PARTY_RINGING` event over SSE says who is calling and carries the call's
`userData`, and the bot-phase transcript is already there to read, because the
call id is minted before any leg exists and survives the transfer. Agents work
in the browser: presence, call control, callbacks — but not the audio, which
belongs to the [web-sip-phone](https://github.com/rasonyang/web-sip-phone)
Chrome extension, a separate repository. It holds the agent's SIP registration
with credentials this application issues at sign-in, and it has no dialpad of
its own: answering, holding and hanging up are REST calls here, carried to the
phone over ESL `uuid_phone_event`. Supervisors get a live wallboard, the queue
view and the roster.

**Keeps one record per conversation.** A call that a bot answered, handed to a
queue and an agent finished is one CDR with one transcript and one recording —
not three fragments. Recordings go to a filesystem or to any S3-compatible
store.

**Speaks two languages, and admits which provider it runs.** English and
Chinese throughout, interface and bot. One provider answers every call in a
deployment, chosen at startup: `qwen` or `doubao` inside mainland China,
`openai` or `gemini` elsewhere, or `gateway` for a Realtime gateway of your
own. A call's language never selects it. Three of those are profiles of one
protocol; `doubao` and `gemini` each speak a different one and have a client of
their own ([how a provider is added](docs/provider-extension.md)).

## How it fits together

```
                    ┌──────────── one Go binary ────────────┐
  caller ──▶ FreeSWITCH ──▶ SIP UAS ──▶ provider (Realtime, speech-to-speech)
                 │            │
                 │            └─ flow engine: phases, tools, transfers
                 │
                 ├─ mod_callcenter queues ──▶ agents (browser + web-sip-phone)
                 │
                 └─ ESL ──▶ call registry ──▶ REST + SSE ──▶ web interface
                                                    │
                                              PostgreSQL
```

FreeSWITCH reads its directory and its `mod_callcenter` queues *from the
database*, through Lua. The dialplan is static XML, but its rules decide
nothing by themselves: each one hands the call to a Lua script that looks the
answer up. Adding an extension, a queue or a number is a database change; the
switch's own files change only when the routing itself does.

Two design notes worth knowing before reading the code:

* The domain model is Genesys-lineage. A **call** aggregates **parties**; leg
  events are `PARTY_*`, call-scoped ones are `CALL_*`.
* Every live call is an actor — one goroutine as its sole mutator, snapshots by
  mailbox. Nothing in `internal/telephony` locks call state, because there is
  no shared call state; the AI leg is the exception, holding mutexes over the
  playback and recording state its own goroutines share.

The full design is in [`docs/design/`](docs/design/), starting with
[the overview](docs/design/00-overview.md).

## Building

```sh
make dev-up            # PostgreSQL in Docker
cd web && npm install && npm run build && cd ..
make build             # bin/aicc, with the interface embedded
./bin/aicc useradd -username admin -password '…' -role ADMIN
./bin/aicc
```

For frontend work, `make web-dev` runs Vite on 5173 against the API on 8080.

```sh
go test -race ./...    # always -race; it has caught real bugs here
make lint              # go vet, gofmt, oxlint
make api-check         # the API contract gate
```

The HTTP API is spec-first: [`docs/openapi.json`](docs/openapi.json) is the
single source of truth, and the Go server and the TypeScript client are
generated from it. Edit the contract, run `make api-generate`, then implement.
Never the other way round.

## Extending it

* **A new voice provider** is a profile, not a client:
  [`docs/provider-extension.md`](docs/provider-extension.md).
* **A new flow** is a JSON document validated at load — see
  [`internal/seed/flows/`](internal/seed/flows/) for a working bilingual one.
* **A new screen** follows the design system in
  [`web/CLAUDE.md`](web/CLAUDE.md), which is binding rather than advisory.
* **An integration with another product** is a service behind the flow's
  backend URL, never code in this tree:
  [`CONTRIBUTING.md`](CONTRIBUTING.md#integrations-live-outside-the-tree).

## Status

The human path, the AI path, the product surface and the packaging are built
and verified against live FreeSWITCH and live providers.

Performance is not yet a claim this project makes. The design has a capacity
budget and a latency target ([design 06](docs/design/06-capacity.md)), and the
harness to test them against is in the repository
([docs/load-tests.md](docs/load-tests.md)) — but the benchmark campaign itself
is still to come, so treat the budget as an intention rather than a
measurement.

What is deliberately *not* here, and will not be: any cascaded
ASR + LLM + TTS pipeline inside this process. That composition belongs in a
separate service speaking the same protocol.

## License

Apache-2.0. See [LICENSE](LICENSE).
