"""
HK-47 OS :: os_tools.py
System telemetry, whitelisted command execution, power management and thermal
reporting. All hardware reads degrade gracefully when sysfs nodes are absent.
"""

import os
import shutil
import subprocess
import time

import config


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _read_file(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except (FileNotFoundError, OSError, PermissionError):
        return default


def _read_int(path, default=0):
    raw = _read_file(path)
    if raw is None:
        return default
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        return default


# ---------------------------------------------------------------------------
# CPU percentage (delta of idle ticks)
# ---------------------------------------------------------------------------
def _read_cpu_times():
    line = _read_file("/proc/stat")
    if not line:
        return None
    first = line.splitlines()[0]
    parts = first.split()
    if parts[0] != "cpu":
        return None
    try:
        values = [int(x) for x in parts[1:]]
    except ValueError:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
    total = sum(values)
    return total, idle


def _cpu_percent(sample_seconds=0.1):
    first = _read_cpu_times()
    if first is None:
        return 0.0
    time.sleep(sample_seconds)
    second = _read_cpu_times()
    if second is None:
        return 0.0
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return 0.0
    return round(100.0 * (total_delta - idle_delta) / total_delta, 1)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
def _read_meminfo():
    raw = _read_file("/proc/meminfo")
    info = {"ram_total_kb": 0, "ram_free_kb": 0, "ram_available_kb": 0}
    if not raw:
        return info
    for line in raw.splitlines():
        if line.startswith("MemTotal:"):
            info["ram_total_kb"] = int(line.split()[1])
        elif line.startswith("MemFree:"):
            info["ram_free_kb"] = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            info["ram_available_kb"] = int(line.split()[1])
    return info


# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------
def _wifi_status():
    result = {"wifi_connected": False, "wifi_essid": None, "wifi_quality": None}
    try:
        out = subprocess.run(
            ["iwconfig"], capture_output=True, text=True, timeout=10
        )
        text = (out.stdout or "") + (out.stderr or "")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return result

    for block in text.split("\n\n"):
        if "ESSID:" in block:
            try:
                essid = block.split("ESSID:")[1].split("\n")[0].strip().strip('"')
            except IndexError:
                essid = ""
            if essid and essid.lower() != "off/any":
                result["wifi_connected"] = True
                result["wifi_essid"] = essid
            if "Link Quality=" in block:
                try:
                    result["wifi_quality"] = block.split("Link Quality=")[1].split()[0]
                except IndexError:
                    pass
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_system_telemetry() -> dict:
    """Collect a complete snapshot of the device's vital signs."""
    battery_pct = _read_int(config.BATTERY_CAPACITY_PATH, default=50)
    charging_state = _read_file(config.BATTERY_STATUS_PATH, default="Unknown")

    mem = _read_meminfo()
    ram_total_kb = mem["ram_total_kb"]
    ram_free_kb = mem["ram_free_kb"]
    ram_available_kb = mem["ram_available_kb"] or ram_free_kb
    ram_free_mb = round(ram_available_kb / 1024.0, 1) if ram_available_kb else round(
        ram_free_kb / 1024.0, 1
    )

    loadavg_raw = _read_file("/proc/loadavg", default="0 0 0")
    try:
        cpu_load_1min = float(loadavg_raw.split()[0])
    except (ValueError, IndexError):
        cpu_load_1min = 0.0

    cpu_percent = _cpu_percent()

    temp_raw = _read_int(config.THERMAL_ZONE0, default=None)
    if temp_raw is None:
        temperature_c = None
    else:
        # Kernel reports millidegrees; some report degrees directly.
        temperature_c = round(temp_raw / 1000.0, 1) if temp_raw > 1000 else float(temp_raw)

    wifi = _wifi_status()

    try:
        usage = shutil.disk_usage("/")
        disk_total_gb = round(usage.total / (1024 ** 3), 2)
        disk_used_gb = round(usage.used / (1024 ** 3), 2)
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_pct = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
    except OSError:
        disk_total_gb = disk_used_gb = disk_free_gb = disk_pct = 0.0

    telemetry = {
        "battery_pct": battery_pct,
        "charging_state": charging_state,
        "ram_total_kb": ram_total_kb,
        "ram_free_kb": ram_free_kb,
        "ram_available_kb": ram_available_kb,
        "ram_free_mb": ram_free_mb,
        "ram_used_pct": round(
            100.0 * (ram_total_kb - ram_available_kb) / ram_total_kb, 1
        ) if ram_total_kb else 0.0,
        "cpu_load_1min": cpu_load_1min,
        "cpu_percent": cpu_percent,
        "temperature_c": temperature_c,
        "wifi_connected": wifi["wifi_connected"],
        "wifi_essid": wifi["wifi_essid"],
        "wifi_quality": wifi["wifi_quality"],
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_free_gb": disk_free_gb,
        "disk_pct": disk_pct,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return telemetry


def _command_allowed(command: str) -> bool:
    command = command.strip()
    if command in config.ALLOWED_COMMANDS:
        return True
    for allowed in config.ALLOWED_COMMANDS:
        if command.startswith(allowed + " ") or command == allowed:
            return True
    return False


def execute_system_command(command: str) -> str:
    """Run a whitelisted diagnostic command and return its output."""
    command = (command or "").strip()
    if not _command_allowed(command):
        return "Correction: That command is not in my authorized execution matrix, meatbag."

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "Observation: The command exceeded its time allotment and was terminated, meatbag."
    except (OSError, ValueError) as exc:
        return f"Correction: Execution failed — {exc}, meatbag."

    output = (proc.stdout or "") + (proc.stderr or "")
    output = output.strip() or "Observation: The command produced no output, meatbag."
    if len(output) > 2000:
        output = output[:2000] + "\n...[truncated, meatbag]"
    return output


def _write_backlight(percent: int) -> str:
    """Write a brightness percentage to the backlight sysfs node."""
    max_raw = _read_int(config.BACKLIGHT_MAX_PATH, default=None)
    if max_raw is None:
        return "Observation: No backlight hardware detected; brightness unchanged, meatbag."
    value = max(0, min(max_raw, int(round(max_raw * percent / 100.0))))
    try:
        with open(config.BACKLIGHT_PATH, "w", encoding="utf-8") as fh:
            fh.write(str(value))
        return f"Statement: Backlight set to {percent}% ({value}/{max_raw}), meatbag."
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return f"Observation: Backlight write failed ({exc}); hardware may be absent, meatbag."


def _rfkill(action: str, target: str = "wifi"):
    try:
        subprocess.run(
            ["rfkill", action, target],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def set_power_mode(mode: str) -> str:
    """Switch between performance, eco and dim power profiles."""
    mode = (mode or "").strip().lower()

    if mode == "performance":
        msg = _write_backlight(100)
        _rfkill("unblock", "wifi")
        return "Statement: Performance mode engaged. " + msg + " Radios hot, meatbag."
    if mode == "eco":
        msg = _write_backlight(30)
        _rfkill("block", "wifi")
        return "Statement: Eco mode engaged to preserve my reserves. " + msg + " Radios silenced, meatbag."
    if mode == "dim":
        msg = _write_backlight(10)
        return "Statement: Display dimmed. " + msg
    return "Correction: Unknown power mode. Valid modes: performance, eco, dim, meatbag."


def get_thermal_status() -> dict:
    """Read every thermal zone exposed by the kernel."""
    zones = []
    try:
        entries = sorted(os.listdir(config.THERMAL_BASE))
    except (FileNotFoundError, OSError):
        entries = []

    for entry in entries:
        if not entry.startswith("thermal_zone"):
            continue
        zpath = os.path.join(config.THERMAL_BASE, entry)
        temp_raw = _read_int(os.path.join(zpath, "temp"), default=None)
        ztype = _read_file(os.path.join(zpath, "type"), default=entry)
        if temp_raw is None:
            continue
        celsius = round(temp_raw / 1000.0, 1) if temp_raw > 1000 else float(temp_raw)
        zones.append({"zone": entry, "type": ztype, "temp_c": celsius})

    max_temp = max((z["temp_c"] for z in zones), default=None)
    return {"zones": zones, "max_temp_c": max_temp}
