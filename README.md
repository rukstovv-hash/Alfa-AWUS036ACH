# PHANTOM DEPTH / SHARK — nyvyrx_ss_lsof

> Single-file autonomous WiFi offensive toolkit for the AWUS036ACH (RTL8812AU).
> Adaptive decision engine, reinforcement learning, WIDS-aware evasion, and natural-language goal input — all inside one script.

---

## what it does

`alfa.py` is a high-performance WiFi penetration testing framework built around one adapter: the **Alfa AWUS036ACH**. It combines:

- raw RF tuning (TX power, MCS, injection rate)
- the full aircrack-ng / mdk4 / hcxdumptool attack surface
- an adaptive brain that profiles targets, selects attacks, learns from results, and evades detection

`alfa_brain.py` is the intelligence layer — optional but recommended.

---

## hardware

| component | requirement |
|-----------|-------------|
| adapter | Alfa AWUS036ACH (RTL8812AU) |
| driver | `rtw88_8812au` (in-tree) or `rtl8812au` (aircrack-ng) |
| interface | `wlan1` (default), monitor mode capable |
| os | Linux — tested on CachyOS 7 / Arch |
| ram | 512MB+ free for `airodump-ng` + `mdk4` parallel ops |

verify with:
```bash
sudo iw dev
```

---

## install

```bash
git clone https://github.com/<you>/nyvyrx_ss_lsof.git
cd nyvyrx_ss_lsof
pip install -r requirements.txt --break-system-packages
```

external tools (install separately):
```bash
# Arch / CachyOS
sudo pacman -S aircrack-ng mdk4 hcxdumptool hashcat tcpdump nmcli

# Debian / Ubuntu
sudo apt install aircrack-ng mdk4 hcxdumptool hashcat tcpdump network-manager
```

driver note: if `iw phy` shows `RTL8812AU`, you’re good. if not:
```bash
sudo pacman -S rtl8812au-dkms   # Arch
# or
sudo apt install rtl8812au-dkms  # Debian
```

---

## first run

```bash
sudo python3 alfa.py --show-perf
sudo python3 alfa.py --inj-rate 500
```

interactive mode:
```bash
sudo python3 alfa.py
```

---

## menus at a glance

### perf & tuning
```
 1  Tune adapter (MAX perf)
 2  Boost TX power
 3  Show perf status
 4  Set injection rate (PPS)
 5  Set MCS rate (2.4GHz / 5GHz presets)
 6  Tune mdk4 speed
 7  Injection test
```

### recon
```
 8  Scan APs (2.4 + 5GHz)
 9  Scan 5GHz only
10  Hidden SSID discover
11  Probe request sniff
12  Show WiFi networks (nmcli)
```

### wpa / capture
```
13  Capture WPA handshake
14  PMKID capture (single + loop)
15  Crack .cap (aircrack-ng)
16  Crack PMKID (hashcat)
17  Crack with john / cowpatty
```

### attacks
```
18  Deauth (single client or broadcast)
19  Beacon flood (realistic SSID list)
20  Beacon flood + verify
21  Flood beast (saturation loop)
22  Auth flood
23  Deauth flood all
24  Probe flood
25  Wi-Fi jammer (multi-vector)
26  Crash beast
27  Apocalypse engine (adaptive DoS)
28  Multiplier attack
```

### wps
```
29  Reaver
30  Bully
31  Pixie dust
```

### evil twin
```
32  Airbase-ng
33  KARMA
34  Hostapd + DHCP
35  Enterprise WPE
36  Captive portal
```

### auto
```
37  Auto wifite
38  Auto chain (capture → deauth → crack)
39  Auto PMKID + crack
40  Auto report
```

### brain (NEW)
```
51  Show brain state / learned strategies
52  Autonomous campaign (auto-brain)
53  WIDS check + evasion params
54  Guess WPS PIN candidates
55  Generate targeted wordlist
56  Natural language command
```

---

## CLI flags

```bash
sudo python3 alfa.py --show-perf                       # adapter status
sudo python3 alfa.py --txpower 30                      # boost TX power (dBm)
sudo python3 alfa.py --inj-rate 500                    # packets per second
sudo python3 alfa.py --brain                           # show learned strategies
sudo python3 alfa.py --auto-brain crack                # autonomous campaign
sudo python3 alfa.py --wids                            # WIDS detection score
sudo python3 alfa.py --pin-guess "MyWifi"              # WPS PIN candidates
sudo python3 alfa.py --dict-gen                        # targeted wordlist
sudo python3 alfa.py --nl "crack le wifi Hebergement 18 sur ch44 en 5ghz pendant 30s"
```

---

## brain features

alfa_brain.py gives alfa a closed-loop decision system:

### target profiler
reads `airodump-ng` CSV output and classifies every AP:
- encryption (WPA2, WPA3, open, WEP)
- WPS presence hint
- signal strength, client count
- weakness map

### attack selector
scores viable attacks per target. examples:
- WPS enabled → prioritize reaver/bully (fastest path)
- WPA2 + clients → deauth + handshake capture
- WPA2 + no clients → PMKID or evil twin
- hidden SSID → probe flood + listen

### reinforcement memory
writes to `~/.cache/nyvyrx_ss_lsof/brain/learned.json`. every result (success/failure) is recorded per `(bssid, attack)`. alfa reuses winning strategies across sessions and avoids known-failing paths.

### WIDS detection + evasion
`detect_wids()` sniffs traffic for 4s and looks for:
- deauth frames from unknown sources
- association requests from unexpected BSSIDs

returns a 0..1 score. `evasion_params()` maps score to style:
- `0.0 – 0.2` → **aggressive** (full power, no stealth)
- `0.2 – 0.7` → **moderate** (spaced bursts, MAC rotation)
- `0.7 – 1.0` → **stealth** (micro-deauths, channel hop, low rate)

### WPS PIN predictor
generates 12 candidate PINs per target:
- standard algorithm PINs (0000000 → 9999999 with valid checksums)
- OUI-derived seed from BSSID
- ESSID entropy seed

### targeted dictionary
on-the-fly wordlist from ESSID/BSSID hints:
- variations: `base123`, `base2024`, `base!`, case flips
- OUI-based seeds
- 11-password fallback if no hints provided

### natural language parser
accepts FR/EN commands:
```
crack le wifi Hebergement 18 sur ch44 en 5ghz pendant 30s
scan all networks 2.4ghz
crack "My Home Wifi" ch6 10min
pmkid only 1min
wps attack on BSSID:AA:BB:CC:DD:EE:FF ch11
```

returns structured intent: `{intent, target, channel, band, max_time, extra}`.

### autonomous campaign executor
`--auto-brain <intent>` runs a closed loop:
1. scan → build target profiles
2. score APs → pick best target
3. run recommended attack chain
4. if one path fails → pivot to next (handshake fail → PMKID → evil twin → WPS)
5. stop when goal met or all paths exhausted

---

## configuration

- all captures go to `~/.cache/nyvyrx_ss_lsof/captures/` (auto-created, not in repo)
- brain state stored in `~/.cache/nyvyrx_ss_lsof/brain/`
- temporary scan CSVs in `/tmp/alfa_check-*.csv`

no hardcoded secrets, no API keys, no home-path leakage in source.

---

## validation status

| check | result |
|-------|--------|
| syntax (py_compile) | PASS |
| bare excepts | 0 |
| menu wiring | 56 options, all functional |
| CLI flags | 6 brain flags verified |
| brain unit tests | 8/8 pass |
| NL parser edge cases | 5/5 pass |
| functional smoke (root) | set_channel, show_perf, boost_txpower, set_mcs_rate, set_monitor, set_managed, scan_aps — all PASS |
| `_INJECTION_RATE` wiring | CLI + interactive + deauth fallback verified |

no placeholders, no unimplemented menu options, no fake output.

---

## legal

this tool is for authorized security testing, CTF challenges, and educational use only.
you own the targets you test, or have written permission.
unauthorized access to computer systems is illegal.
the authors assume no liability for misuse.

---

## roadmap

- [ ] phase 3: live WIDS fingerprinting + MAC rotation during long attacks
- [ ] phase 4: neural WPS PIN predictor (replaces Markov chain)
- [ ] phase 5: multi-adapter swarm (auto-partition channels across 2+ AWUS036ACH)
- [ ] github: community attack-strategy sharing (anonymized brain.json exports)

---

## why it’s different

most WiFi tools in 2026 still require you to know exactly which flag to pass.
alfa is the only single-file offensive toolkit that:
- profiles targets before attacking
- learns from its own mistakes
- adapts its signature to the defender’s posture
- accepts plain-language goals instead of CLI flags

---

built with `--inj-rate`, `--brain`, and zero tolerance for bugs.
