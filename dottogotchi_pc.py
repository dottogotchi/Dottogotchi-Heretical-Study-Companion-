"""
============================================
Dottogotchi Heretical Study Companion
============================================

  Preboot installs via terminal:
    pip install requests pycaw pynput comtypes psutil
Run in terminal;
    python dottogotchi.py --ip {your IP}
============================================
"""

import argparse
import time
import threading
import sys
import requests
import psutil
import ctypes
import ctypes.wintypes

# ─── Idle Time Detection (Windows) ─────────────
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint),
    ]

def get_idle_seconds():
    """Get the number of seconds since last user input (mouse/keyboard)."""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    except Exception:
        return 0


# ─── Keyboard Activity Monitor ─────────────────
class KeyboardMonitor:
    """Tracks typing speed using pynput."""
    
    def __init__(self):
        self.key_count = 0
        self.keys_per_second = 0.0
        self._lock = threading.Lock()
        self._running = False
    
    def start(self):
        """Start monitoring keyboard in background thread."""
        try:
            from pynput import keyboard
            
            def on_press(key):
                with self._lock:
                    self.key_count += 1
            
            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.daemon = True
            self._listener.start()
            self._running = True
            
            # Start KPS calculation thread
            calc_thread = threading.Thread(target=self._calc_kps, daemon=True)
            calc_thread.start()
            
            print("✅ Keyboard monitor started")
        except ImportError:
            print("⚠️  pynput not installed. Keyboard detection disabled.")
            print("   Install with: pip install pynput")
    
    def _calc_kps(self):
        """Calculate keys-per-second every second."""
        while True:
            time.sleep(1)
            with self._lock:
                self.keys_per_second = self.key_count
                self.key_count = 0
    
    def get_kps(self):
        """Get current keys per second."""
        with self._lock:
            return self.keys_per_second


# ─── State Detection Logic ─────────────────────
IDLE_THRESHOLD_SEC = 120       # 2 minutes
TYPING_KPS_THRESHOLD = 3      # 3 keys per second = "fast typing"

def is_process_running(exename="chrome.exe"):
    """Return True if a process with the given executable name exists."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == exename.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return False

def detect_state(kb_monitor):
    """Detect current activity state based on system signals."""

    # Priority 1: Fast typing → typing
    kps = kb_monitor.get_kps()
    if kps >= TYPING_KPS_THRESHOLD:
        return "writing"
    if is_process_running("chrome.exe"):
        return "reading"
    # Default
    return "idling"

# ─── Send State to ESP32 ──────────────────────
def send_state(ip, state):
    """Send state to Dottogotchi"""
    url = f"http://{ip}/state"
    try:
        resp = requests.post(url, json={"state": state}, timeout=3)
        if resp.status_code == 200:
            return True
        else:
            print(f"⚠️  Server returned {resp.status_code}: {resp.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {ip}. Is the ESP32 running?")
        return False
    except requests.exceptions.Timeout:
        print(f"⏰ Request to {ip} timed out.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# ─── Main ─────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Dottogotchi-send your laptop activity to tiny scientist"
    )
    parser.add_argument(
        '--ip', required=True,
        help="IP address of the ESP32 Dottogotchi(shown on OLED at boot)"
    )
    parser.add_argument(
        "--state", default=None,
        choices=["write", "read","idle"],
        help="Manually set a specific state (overrides auto-detection)"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Polling interval in seconds (default: 2.0)"
    )
    args = parser.parse_args()

    if args.state:
        print(f"  📌 Manual mode: sending '{args.state}' once")
        success = send_state(args.ip, args.state)
        if success:
            print(f"  ✅ State '{args.state}' sent successfully!")
        else:
            print(f"  ❌ Failed to send state.")
        return  # This works perfectly here to exit main()
    
    # Auto-detection mode
    print(f"  🔄 Auto-detection mode (interval: {args.interval}s)")
    print(f"  📡 Detecting: write, read, idle")
    print(f"  ⏹️  Press Ctrl+C to stop\n")
    
    # Start keyboard monitor
    kb_monitor = KeyboardMonitor()
    kb_monitor.start()
    
    # Give keyboard listener a moment to start
    time.sleep(0.5)
    
    last_state = None
    consecutive_errors = 0
    MAX_ERRORS = 10
    
    try:
        while True:
            state = detect_state(kb_monitor)
            
            # Only send if state changed (reduces network traffic)
            if state != last_state:
                timestamp = time.strftime("%H:%M:%S")
                success = send_state(args.ip, state)
                if success:
                    print(f"  [{timestamp}] {state}")
                    last_state = state
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_ERRORS:
                        print(f"\n  ❌ Too many connection errors ({MAX_ERRORS}). Exiting.")
                        print(f"     Check if ESP32 is powered and on same network.")
                        sys.exit(1)
            
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\n\n  Dottogotchi has stopped")


if __name__ == "__main__":
    main()




