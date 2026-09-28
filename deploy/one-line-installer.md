# One-line installer

On Linux:

```sh
curl -fsSL https://github.com/rasonyang/ai-native-callcenter/releases/latest/download/install.sh | sudo sh
```

On macOS (Colima or Docker Desktop), drop the `sudo`:

```sh
curl -fsSL https://github.com/rasonyang/ai-native-callcenter/releases/latest/download/install.sh | sh
```

## What it does

The installer checks the host first, asks for the voice provider and its key,
generates every password into `.env`, starts the published images and checks
the running stack with `aicc doctor`. It then prints the address and the admin
password.

## What you get

The stack comes up seeded with a team, two queues, six published bilingual
flows (each behind an English, a Chinese and a US number, the main line being
800-555-0199), eighteen simulated customer telephones and a week of history,
so the wallboard is not empty and a softphone can ring the bot straight away.
Install the [web-sip-phone](https://chromewebstore.google.com/detail/dkhaojcfjdcdpldokeokajkmambkbacp)
extension, sign in as an agent and dial 95001 (English) or 95002 (Chinese).

## Supported platforms

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

Options, upgrades, removal and the manual compose install are in
[deploy/README.md](README.md).
