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

def numerical_sort_key(write_dir):
    number = ""
    
    for char in write_dir:
        if char.isdigit():
            number += char
    
    return int(number) if number else 0

write_sort = sorted(write_frame, key=numerical_sort_key)

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
    STATE_ERORR = 3

def state_to_string(state):
    if state == ActivityState.STATE_WRITE:
        return "writing"
    elif state == ActivityState.STATE_READ:
        return "reading"
    elif state == ActivityState.STATE_IDLE:
        return "idling"
    elif state == ActivityState.STATE_ERROR:
        return "error"
    return "unknown"

def string_to_state(s):
    if s == "writing":
        return ActivityState.STATE_WRITE
    elif s == "reading":
        return ActivityState.STATE_READ
    elif s == "idling":
           return ActivityState.STATE_IDLE
    elif s == "error":
        return ActivityState.STATE_ERROR
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
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dottogotchi</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
font-family: 'Segoe UI', system-ui, sans-serif;
background-image: url('/dottos/dottohtml.jpg');
color: #fff; min-height: 100vh;
display: flex; flex-direction: column;
align-items: center; padding: 30px 20px;
}
h1 {
font-size: 2.4em; margin-bottom: 6px;
background: linear-gradient(90deg, #d9b3d9, #bb6791);
-webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.sub { color: #dfb1dc; margin-bottom: 28px; font-size: 0.9em; letter-spacing: 0.5px; }
.card {
background: rgba(255,255,255,0.06);
backdrop-filter: blur(12px);
border: 1px solid rgba(255,255,255,0.1);
border-radius: 18px; padding: 22px 32px;
margin-bottom: 28px; text-align: center;
min-width: 280px; transition: all 0.3s ease;
}
.card:hover { border-color: rgba(255,255,255,0.2); }
.lbl { color: #dfb1dc; font-size: 0.75em; text-transform: uppercase; letter-spacing: 2px; }
.val {
font-size: 2em; font-weight: 700; margin-top: 6px;
background: linear-gradient(90deg, #d9b3d9, #bb6791);
-webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.grid {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
gap: 10px; max-width: 580px; width: 100%;
}
.btn {
padding: 14px 8px; border: none; border-radius: 14px;
font-size: 0.95em; font-weight: 600; cursor: pointer;
transition: all 0.25s cubic-bezier(.4,0,.2,1); color: #fff;
position: relative; overflow: hidden;
}
.btn::after {
content: ''; position: absolute; inset: 0;
background: linear-gradient(135deg, rgba(255,255,255,0.15), transparent);
opacity: 0; transition: opacity 0.25s;
}
.btn:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
.btn:hover::after { opacity: 1; }
.btn:active { transform: translateY(-1px); }
.btn.active { box-shadow: 0 0 0 2px #fff, 0 8px 25px rgba(0,0,0,0.4); }
.b1 { background: linear-gradient(135deg, #514969,#2f265b); }
.b2 { background: linear-gradient(135deg, #c3568b,#9a1d45); }
.b3 { background: linear-gradient(135deg, #a44ca7,#62377e); }
.b4 { background: linear-gradient(135deg, #b0adbe,#9e7daf); }
.ft { margin-top: 36px; color: #444; font-size: 0.75em; }
</style>
</head>
<body>
<h1>Dottogotchi</h1>
<p class="sub">Heretical Study Companion</p>
<div class="card">
<div class="lbl">Dotto is</div>
<div class="val" id="cs">...</div>
</div>
<div class="grid">
<button class="btn b1" onclick="ss('idle')" data-s="idling">&#128788; Idle</button>
<button class="btn b2" onclick="ss('writing')" data-s="writing">&#9791; Writting</button>
<button class="btn b3" onclick="ss('read')" data-s="reading">&#128781; Reading</button>
<button class="btn b4" onclick="ss('fund')" data-s="fund">&#9901; Give Funding</button>
</div>
<p class="ft">v2.0 &middot; ESP32-S3</p>
<script>
let cur='';
function hl(s){
document.querySelectorAll('.btn').forEach(b=>b.classList.toggle('active',b.dataset.s===s));
}
function ss(s){
fetch('/state',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({state:s})}).then(r=>r.json()).then(d=>{
cur=d.state||s; document.getElementById('cs').textContent=cur; hl(cur);
}).catch(()=>{});
}
function gs(){
fetch('/status').then(r=>r.json()).then(d=>{
cur=d.state||'?'; document.getElementById('cs').textContent=cur; hl(cur);
}).catch(()=>{});
}
gs(); setInterval(gs,3000);
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
    
    print("POST HIT")
    
    body = request.body.decode("utf-8")
    state_str = parse_state_native(body)
    frame_index = 0
    read_loop_mode = False


    if state_str:
        new_state = string_to_state(state_str)

        if new_state != current_state:
            previous_state = current_state
            current_state = new_state

            # Reset animation
            frame_index = 0

            # Reset read intro animation
            if current_state == ActivityState.STATE_READ:
                read_loop_mode = False

            print("Changed state to:", state_str)

    return Response(
   request,
    json.dumps({
        "state": state_to_string(current_state),
        "status": "ok"
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

while True:
    server.poll()
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
    elif current_state == ActivityState.STATE_IDLE:
        frames = idle_frame
        folder = idle_dir
    
    elif current_state == ActivityState.STATE_ERROR:
        frames = error_frame
        folder = error_dir


    filename = folder + "/" + frames[frame_index]

    with open(filename, "rb") as f:
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

    # Update frame index
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
