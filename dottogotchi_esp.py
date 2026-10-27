import board
import displayio
import i2cdisplaybus
from adafruit_displayio_sh1107 import SH1107, DISPLAY_OFFSET_ADAFRUIT_128x128_OLED_5297
import adafruit_imageload
import os
from adafruit_httpserver import (
    Server,
    Request,
    Response,
    GET,
    POST
)
import adafruit_pathlib
import socketpool
import wifi
import time
import json
import gc
import asyncio
from buzzer_music.player import MusicPlayer

#display reset
displayio.release_displays()
#directories
root_path = '/dottos'
folders = ['wake','write','read','read_loop']

write_dir = root_path + "/write"
write_frame = os.listdir(write_dir)
read_dir = root_path + "/read"
read_frame=os.listdir(read_dir)
readl_dir = root_path + "/read_loop"
readl_frame=os.listdir(readl_dir)
idle_dir = root_path + "/idle"
idle_frame=os.listdir(idle_dir)
wake_dir = root_path + "/wake"
wake_frame=os.listdir(wake_dir)
alarm_dir = root_path + "/alarm"
alarm_frame=os.listdir(alarm_dir)

#frame sorting
def numerical_sort_key(write_dir):
    number = ""
    for char in write_dir:
        if char.isdigit():
            number += char
    return int(number) if number else 0
write_sort = sorted(write_frame, key=numerical_sort_key)
def numerical_sort_key(alarm_dir):
    number = ""
    for char in alarm_dir:
        if char.isdigit():
            number += char
    return int(number) if number else 0
alarm_sort = sorted(alarm_frame, key=numerical_sort_key)

#music
FOUR_UNSPEAKABLES="""
2.00 C#6 2 42;
3.00 C#6 1 42;
4.00 C#6 1 42;
4.75 C#6 0.75 42;
5.50 C#6 0.75 42;
6.00 C#6 0.5 42;
14.00 C6 8 42;
16.00 C#6 2 42;
17.00 C#6 1 42;
18.00 C#6 1 42;
18.75 G6 0.75 42;
19.50 C#6 0.75 42;
20.00 A#6 0.5 42;
28.00 C6 8 42;
30.00 A#6 2 42;
31.00 A#6 1 42;
32.00 A#6 1 42;
32.75 A#6 0.75 42;
33.50 G#6 0.75 42;
34.00 G6 0.5 42;
38.00 G6 4 42;
38.75 G#6 0.75 42;
39.50 G6 0.75 42;
40.00 F6 0.5 42;
43.00 C6 3 42;
43.25 C#6 0.25 42;
43.50 C#6 1.5 42;
45.00 C6 0.25 42;
45.25 C#6 0.25 42;
45.50 C6 6 42;
"""
alarm_player = MusicPlayer([board.D10], debug=True)
alarm_task = None
async def play_alarm():
    try:
        while current_state == ActivityState.STATE_ALARM:
            await alarm_player.play(
                song=FOUR_UNSPEAKABLES,
                bpm=472,
            )
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        raise

#wifi connect
network_name = os.getenv("CIRCUITPY_WIFI_SSID")
network_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
print ("connecting to wifi...")
try:
    wifi.radio.connect(network_name,network_password)
    device_ip = wifi.radio.ipv4_address
    print("connected to wifi with IP:",device_ip)
except Exception as e:
    print("Failed to connect to WiFi:", e)

# display boot
i2c = board.I2C()
display_bus = i2cdisplaybus.I2CDisplayBus(
board.I2C(),
device_address=0x3C,
)
display = SH1107(display_bus, width=128, height=128,
    display_offset=DISPLAY_OFFSET_ADAFRUIT_128x128_OLED_5297, rotation=90)
screen = displayio.Group()
display.root_group = screen
frame_index=0

#Defining activity state(dotto emotions)
class ActivityState:
    STATE_READ = 0
    STATE_WRITE = 1
    STATE_IDLE = 2
    STATE_ALARM = 3

def state_to_string(state):
    if state == ActivityState.STATE_WRITE:
        return "writing"
    elif state == ActivityState.STATE_READ:
        return "reading"
    elif state == ActivityState.STATE_IDLE:
        return "idling"
    elif state == ActivityState.STATE_ALARM:
        return "alarmed"
    return "unknown"

def string_to_state(s):
    if s == "writing":
        return ActivityState.STATE_WRITE
    elif s == "reading":
        return ActivityState.STATE_READ
    elif s == "idling":
           return ActivityState.STATE_IDLE
    elif s == "alarmed":
        return ActivityState.STATE_ALARM
    return ActivityState.STATE_IDLE

def parse_state_native(text):
    try:
        data = json.loads(text)
        return data.get("state", "")
    except Exception:
        return ""
state_change_time = 0
state_just_changed = False
oneshot_played = False
post_index = 0
beat_phase = 0
frame_index = 0
read_loop_mode = False
current_state = ActivityState.STATE_IDLE
previous_state = current_state
start_time_seconds = time.time()

#server(html control)
pool= socketpool.SocketPool(wifi.radio)
server = Server(pool,debug=True)
server.start(str(wifi.radio.ipv4_address))
@server.route("/dottos/dottohtml.jpg", GET)
def dotto_image(request):
    with open("/dottos/dottohtml.jpg", "rb") as f:
        image = f.read()
    return Response(
        request,
        image,
        content_type="image/jpeg"
    )
@server.route("/", GET)
def root(request):
    return Response(
    request,
#html code for interface
    """
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dottogotchi</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: "Segoe UI", system-ui, sans-serif;
      color: #fff;
      min-height: 100vh;
      padding: 30px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background:
        url("/dottos/dottohtml.jpg") center / cover fixed no-repeat;
    }
    h1 {
      font-size: 2.4em;
      margin-bottom: 6px;
      background: linear-gradient(90deg, #ffc4e1, #d94582);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    h2 {
      font-size: 2.4em;
      margin-bottom: 6px;
      background: linear-gradient(90deg, #ffc4e1, #d94582);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .sub {
      color: #dfb1dc;
      margin-bottom: 28px;
      font-size: 0.9em;
      letter-spacing: 0.5px;
    }
    .card {
      background: rgba(255, 255, 255, 0.06);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 18px;
      padding: 22px 32px;
      margin-bottom: 28px;
      text-align: center;
      min-width: 280px;
      transition: all 0.3s ease;
    }
    .card:hover {
      border-color: rgba(255, 255, 255, 0.2);
    }
    .lbl {
      color: #dfb1dc;
      font-size: 0.75em;
      text-transform: uppercase;
      letter-spacing: 2px;
    }
    .val {
      font-size: 2em;
      font-weight: 700;
      margin-top: 6px;
      background: linear-gradient(90deg,#ffc4e1, #d94582);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .ft {
      color: #dfb1dc;
      font-size: 0.75em;
      margin-top: 5px;
      margin-bottom: 20px;
    }
    /* Alarm clock */
    .wrapper {
      width: 440px;
      max-width: 100%;
      padding: 30px 30px 38px;
      background:#514969;
      border-radius: 50px;
      border-color: #706896;
      display: flex;
      flex-direction: column;
      align-items: center;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
    }
    .clock-icon {
      width: 103px;
      max-width: 100%;
      margin-bottom: 10px;
    }
    .wrapper .time {
      font-size: 38px;
      font-weight: 500;
      margin: 20px 0 30px;
    }
    .content {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .content.disable {
      cursor: no-drop;
    }
    .content .column {
      padding: 0 10px;
      border-radius: 5px;
      border: 1px solid #bfbfbf;
      width: calc(100% / 3 - 5px);
    }
    .content.disable .column {
      opacity: 0.6;
      pointer-events: none;
    }
    .column select {
      width: 100%;
      height: 53px;
      border: none;
      outline: none;
      background: transparent;
      color:#ffc4e1;
      font-size: 19px;
    }
    .column select option {
      color: #222;
      background:#fff;
    }
    .wrapper button {
      width: 100%;
      border: none;
      outline: none;
      color:#FFEDF7;
      cursor: pointer;
      font-size: 20px;
      padding: 17px 0;
      margin-top: 20px;
      border-radius: 5px;
      background: linear-gradient(90deg,#ffc4e1, #d94582);
      transition: background 0.2s ease;
    }
    .wrapper button:hover {
      background: #f276aa;
    }
    .wrapper button:active {
      transform: scale(0.99);
    }
    @media (max-width: 480px) {
      body {
        padding: 20px 10px;
      }
      h1 {
        font-size: 2em;
      }
      .wrapper {
        padding: 25px 20px 30px;
      }
      .wrapper .time {
        font-size: 30px;
      }
      .content .column {
        padding: 0 6px;
      }
      .column select {
        font-size: 16px;
      }
    }
  </style>
</head>
<body>
  <h1>Dottogotchi</h1>
  <p class="sub">Heretical Study Companion</p>
  <div class="card">
    <div class="lbl">Dottore is</div>
    <div class="val" id="cs">...</div>
  </div>
  <p class="ft">v2.0 &middot; ESP32-S3</p>
  <div class="wrapper">
    <h2 class="time">00:00:00 PM</h2>
    <div class="content">
      <div class="column">
        <select id="hour">
          <option value="Hour" selected disabled hidden>Hour</option>
        </select>
      </div>
      <div class="column">
        <select id="minute">
          <option value="Minute" selected disabled hidden>Minute</option>
        </select>
      </div>
      <div class="column">
        <select id="ampm">
          <option value="AM/PM" selected disabled hidden>AM/PM</option>
        </select>
      </div>
    </div>
    <button id="setAlarmBtn">Set Alarm</button>
  </div>
  <script>
    /* -----------------------------
       Dottogotchi ESP32 state
    ----------------------------- */
    let cur = "";
    function highlightState(state) {
      // Optional hook for your existing UI.
      // Define hl() elsewhere if you want visual state changes.
      if (typeof hl === "function") {
        hl(state);
      }
    }
    function setState(state) {
      fetch("/state", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ state: state })
      })
      .then(response => response.json())
      .then(data => {
        cur = data.state || state;
        document.getElementById("cs").textContent = cur;
        highlightState(cur);
      })
      .catch(() => {});
    }
    function getState() {
      fetch("/status")
        .then(response => response.json())
        .then(data => {
          cur = data.state || "?";
          document.getElementById("cs").textContent = cur;
          highlightState(cur);
        })
        .catch(() => {});
    }
    getState();
    setInterval(getState, 3000);
    /* -----------------------------
       Alarm clock
    ----------------------------- */
    const currentTime = document.querySelector(".time");
    const content = document.querySelector(".content");
    const selectMenu = document.querySelectorAll("select");
    const setAlarmBtn = document.querySelector("#setAlarmBtn");
    let alarmTime = "";
    let isAlarmSet = false;
    /* -----------------------------
       Populate hours
    ----------------------------- */
    for (let i = 12; i >= 1; i--) {
      const hour = i < 10 ? `0${i}` : i;
      const option = document.createElement("option");
      option.value = hour;
      option.textContent = hour;
      selectMenu[0].appendChild(option);
    }
    /* -----------------------------
       Populate minutes
    ----------------------------- */
    for (let i = 59; i >= 0; i--) {
      const minute = i < 10 ? `0${i}` : i;
      const option = document.createElement("option");
      option.value = minute;
      option.textContent = minute;
      selectMenu[1].appendChild(option);
    }
    /* -----------------------------
       Populate AM / PM
    ----------------------------- */
    ["AM", "PM"].forEach(ampm => {
      const option = document.createElement("option");
      option.value = ampm;
      option.textContent = ampm;
      selectMenu[2].appendChild(option);
    });
    /* -----------------------------
   Update clock and check alarm
    ----------------------------- */
    let alarmFired = false;

    function updateClock() {
      const date = new Date();

      let h = date.getHours();
      const m = date.getMinutes();
      const s = date.getSeconds();

      const ampm = h >= 12 ? "PM" : "AM";

      h = h % 12;
      if (h === 0) h = 12;

      const hour = String(h).padStart(2, "0");
      const minute = String(m).padStart(2, "0");
      const second = String(s).padStart(2, "0");

      currentTime.textContent =
        `${hour}:${minute}:${second} ${ampm}`;

      // Fire once, rather than POSTing every second
  // during the entire matching minute.
      if (
        alarmTime &&
        !alarmFired &&
        `${hour}:${minute} ${ampm}` === alarmTime
      ) {
        alarmFired = true;
        setState("alarmed");
        setAlarmBtn.textContent = "Stop Alarm";
      }
    }

    updateClock();
    setInterval(updateClock, 1000);

    /* -----------------------------
       Set / Clear alarm
    ----------------------------- */
    function setAlarm() {
      if (isAlarmSet) {
        // Clear the pending alarm or silence the alarm state.
        alarmTime = "";
        alarmFired = false;
        isAlarmSet = false;

        content.classList.remove("disable");
        setAlarmBtn.textContent = "Set Alarm";

        setState("idling");
        return;
      }

      const hour = selectMenu[0].value;
      const minute = selectMenu[1].value;
      const ampm = selectMenu[2].value;

      if (
        hour === "Hour" ||
        minute === "Minute" ||
        ampm === "AM/PM"
      ) {
        alert("Please select a valid alarm time!");
        return;
      }

      alarmTime = `${hour}:${minute} ${ampm}`;
      alarmFired = false;
      isAlarmSet = true;

      content.classList.add("disable");
      setAlarmBtn.textContent = "Clear Alarm";

      // Handle an alarm set for the current minute.
      updateClock();
    }

    setAlarmBtn.addEventListener("click", setAlarm);
  </script>
</body>
</html>
""",
    content_type="text/html"
) 
#changing between state
@server.route("/state",POST)
def state(request):
    global current_state
    global previous_state
    global state_change_time
    global state_just_changed
    global frame_index
    global oneshot_played
    global post_index
    global beat_phases
    global read_loop_mode
    
    try:
        data = request.json()
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        state_str = data.get("state", "")
        new_state = string_to_state(state_str)

        if state_str not in (
            "writing", "reading", "idling", "alarmed"
        ):
            return Response(
                request,
                json.dumps({
                    "status": "error",
                    "message": "Invalid state",
                    "state": state_to_string(current_state),
                }),
                content_type="application/json",
            )

        if new_state != current_state:
            previous_state = current_state
            current_state = new_state
            state_change_time = time.monotonic()
            state_just_changed = True
            frame_index = 0
            oneshot_played = False
            post_index = 0
            read_loop_mode = False

            print(
                "State changed:",
                state_to_string(previous_state),
                "->",
                state_to_string(current_state),
            )

        return Response(
            request,
            json.dumps({
                "status": "ok",
                "state": state_to_string(current_state),
            }),
            content_type="application/json",
        )
    except Exception as e:
            print("State request error:", e)
            return Response(
                request,
                json.dumps({
                    "status": "error",
                    "message": "Invalid request",
                }),
                content_type="application/json",
        )
        
@server.route("/status", methods=["GET"])
def handle_get_status(request):
    uptime = int(time.time() - start_time_seconds)
    gc.collect()
    free = gc.mem_free()
    return Response(
    request,
    json.dumps({
        "state": state_to_string(current_state),
        "uptime": uptime,
        "heap": free,
    }),
    content_type="application/json",
)

bootframes = wake_frame
bootfolder = wake_dir
for bootfilename in wake_frame:
    bootfilename = wake_dir + "/" + bootfilename
    with open(bootfilename, "rb") as f:
        odb = displayio.OnDiskBitmap(f)
        bitmap = displayio.TileGrid(
            odb,
            pixel_shader=odb.pixel_shader,
        )
        screen.append(bitmap)
        display.refresh(target_frames_per_second=20)
        screen.pop()
        del bitmap
        del odb
        gc.collect()

async def device_loop():
    global frame_index
    global read_loop_mode
    global alarm_task

    while True:
        server.poll()
        if current_state == ActivityState.STATE_ALARM:
            if alarm_task is None:
                alarm_task = asyncio.create_task(play_alarm())
        elif alarm_task is not None:
            alarm_task.cancel()
            alarm_task = None
        
        if current_state == ActivityState.STATE_WRITE:
            frames = write_sort
            folder = write_dir
        elif current_state == ActivityState.STATE_READ:
            if read_loop_mode:
                frames = readl_frame
                folder = readl_dir
            else:
                frames = read_frame
                folder = read_dir

        elif current_state == ActivityState.STATE_ALARM:
            frames = alarm_frame
            folder = alarm_dir
            
        elif current_state == ActivityState.STATE_IDLE:
            frames = idle_frame
            folder = idle_dir
        
        if frames:
            frame_index %= len(frames)
            filename = folder + "/" + frames[frame_index]
            try:
                with open(filename, "rb") as f:
                    odb = displayio.OnDiskBitmap(f)
                    bitmap = displayio.TileGrid(
                        odb,
                        pixel_shader=odb.pixel_shader,
                    )
                    screen.append(bitmap)
                    display.refresh(
                        target_frames_per_second=20
                    )
                    screen.pop()
                    del bitmap
                    del odb
            except OSError as e:
                    print("Animation frame error:", e)
      
            if current_state == ActivityState.STATE_READ:
                if not read_loop_mode:
                    if frame_index == len(read_frame) - 1:
                        read_loop_mode = True
                        frame_index = 0
                    else:
                        frame_index += 1
                else:
                    frame_index = (frame_index + 1) % len(readl_frame)
            else:
                frame_index = (frame_index + 1) % len(frames)

        gc.collect()
        await asyncio.sleep(0)

asyncio.run(device_loop())

