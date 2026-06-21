# PHANTOM DEPTH / SHARK

> Offensive WiFi toolkit for the AWUS036ACH (RTL8812AU).
> Linux-native.

## Why this exists

Most off-the-shelf WiFi auditing tools either ship as fragmented CLI one-liners (`aircrack-ng`, `mdk4`, `reaver`, etc.) or as heavy frameworks that assume a perfect environment.

This project exists to turn one cheap adapter — the **Alfa AWUS036ACH** — into a single coherent offensive platform that:

- maximizes RTL8812AU performance out of the box
- removes guesswork from attack selection
- remembers what works and adapts automatically
- stays distro-agnostic across all major Linux distributions

It is built for authorized penetration testers and CTF players who want one file, one interface, and zero placeholders.

## Installation

### Prerequisites

- Linux host (Arch, CachyOS, Debian, Kali, Ubuntu, Fedora, NixOS, Gentoo)
- Alfa AWUS036ACH (RTL8812AU) on USB 3.0
- Python 3.8+
- Root / sudo access

### 1. Install system dependencies

```bash
# Debian / Kali / Ubuntu
sudo apt update
sudo apt install -y aircrack-ng mdk4 hcxdumptool hashcat tcpdump iw iproute2 python3

# Arch / CachyOS
sudo pacman -S --noconfirm aircrack-ng mdk4 hcxdumptool hashcat tcpdump iw iproute2 python

# Fedora / RHEL
sudo dnf install -y aircrack-ng mdk4 hcxdumptool hashcat tcpdump iw iproute2 python3

# NixOS — add to configuration.nix:
# environment.systemPackages = with pkgs; [ aircrack-ng mdk4 hcxdumptool hashcat tcpdump iw python3 ];
```

No external Python packages are required. The toolkit uses only the standard library.

### 2. Install the driver

Prefer the in-tree driver if available:

```bash
lsmod | grep rtw88_8812au
```

If not loaded, build from source:

```bash
git clone https://github.com/morrownr/8821au-20210702.git
cd 8821au-20210702
make
sudo make install
sudo modprobe 8821au
```

### 3. Set regulatory domain

```bash
sudo iw reg set CA   # or your country code
```

### 4. Clone and verify

```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
python3 -m py_compile "Alfa AWUS036ACH/Alfa_AWUS036ACH.py"
```

### 5. Run

```bash
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py"
```

### Common CLI modes

```bash
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --brain
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --wids
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --pin-guess <SSID>
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --dict-gen
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --nl "crack the wifi TestNet ch44 5ghz 10min"
sudo python3 "Alfa AWUS036ACH/Alfa_AWUS036ACH.py" --auto-brain
```

## What it actually does

**Radio control**
- Monitor mode / managed mode toggle
- RF-kill unblock
- Full adapter tuning (txpower, retry, fragmentation, RTS/CTS, AMPDU, power save, USB autosuspend off)
- Live performance readout (dBm, bitrate, throughput, TX power, retries)

**Target discovery**
- BSSID / SSID / channel / band / signal scanning
- Client association mapping
- PMKID capture and conversion to hashcat-ready `hc22000` format
- PMKID capture loop with circular file rotation

**Offensive modes**
- Deauthentication flood with client-targeted + broadcast variants
- PMKID-only capture (no client needed)
- WPS PIN prediction (checksum-valid candidates per target)
- Evil twin rogue AP + captive portal (hostapd + dnsmasq)
- WIDS detection (4-second tcpdump sniff, heuristics)
- Adaptive evasion presets derived from WIDS score

**Decision engine ("brain")**
- Target profiling from airodump-ng CSV output
- Weakness scoring: OPEN, WEP, WPA, WPA2, WPA3, Enterprise (802.1X), WPS, close-proximity
- Attack recommendation engine with confidence ordering
- Reinforcement persistence (`brain.json` / `learned.json`) that records outcomes and success rates per BSSID + attack type
- Natural language parser — accepts both English and French commands, extracts intent / SSID / channel / band / duration

**Automation**
- Autonomous campaign mode: scan → profile → select attack → execute → pivot on failure
- Targeted wordlist generation from ESSID/BSSID entropy
- Multi-adapter enumeration via `iw dev`

## Capabilities by layer

| Layer | Tools / mechanisms |
|-------|----------------------|
| Radio | `iw`, `ip`, `rfkill`, mac80211 sysfs |
| Capture | `airodump-ng`, `hcxdumptool`, `tcpdump`, `hcxpcapngtool` |
| Attacks | `aireplay-ng`, `mdk4`, `airbase-ng`, `hostapd`, `dnsmasq`, `reaver`, `bully` |
| Cracking | `hashcat` (PMKID / WPA handshake, `hc22000` or `pcap` input) |
| Decision | Inlined Python brain module: CSV profiling, scoring, persistence, NL parsing |

## How it decides what to do

Every scanned AP gets classified into:

- **Encryption type** (OPEN / WEP / WPA / WPA2 / WPA3 / Enterprise)
- **Authentication model** (PSK, MGT, WPS)
- **Band and channel**
- **Signal strength**
- **Client count**
- **WPS hint**

From that profile the engine scores weaknesses and ranks attacks:

- OPEN → passive sniff
- WEP → WEP crack
- WPA/WPA2 + clients → deauth + handshake capture
- WPA/WPA2 + no clients → PMKID capture
- WPS enabled → PIN prediction
- Enterprise → evil twin / WPE
- Close proximity → high-power aggressive deauth

Results are recorded and reused across sessions. Success rates per BSSID + attack pair are tracked, so repeated engagements get progressively smarter.

## Distro support

| Distro | Status |
|--------|--------|
| Arch / CachyOS | Native, tested |
| Debian / Kali / Ubuntu | Supported |
| Fedora / RHEL | Supported |
| NixOS | Supported |
| Gentoo | Supported |
| macOS | Not supported |
| Windows | Not supported |

Dependency installation paths are auto-detected at runtime (`apt`, `dnf`, `yum`, `pacman`, `zypper`, `apk`, `nix-env`).  
No hardcoded package-manager commands remain in the codebase.

## Hardware assumptions

- Adapter: Alfa AWUS036ACH (RTL8812AU)
- Driver: `rtw88_8812au` (in-tree or built)
- Interface naming: `wlan1` (managed) / `wlan1mon` (monitor)
- Regulatory domain set to a full-power profile (e.g. `DFS-FCC`)
- USB 3.0 recommended for sustained throughput

## Design rules

- **Single file** — `Alfa AWUS036ACH.py` contains every mode and every brain function inlined
- **No placeholders** — every CLI flag wires to real behavior
- **No stubs** — defused functions are either implemented or omitted
- **sudo execution** — all radio and attack paths require root
- **Killer on exit** — Ctrl+C triggers full cleanup (process tree kill, monitor-to-managed restore, NetworkManager restore if present)

## Legal

Use only against networks you own or for which you have **explicit written authorization**.  
Unauthorized interception, modification, or disruption of radio communications is illegal under the laws of most jurisdictions.

---

PHANTOM DEPTH / SHARK
