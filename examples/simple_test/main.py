# ----------------------------------------------------------------------------
# Simple testprogram for the ecu_reader library.
#
# Author: Bernhard Bablok
# License: Apache 2.0 (original license)
#
# Website: https://github.com/bablokb/circuitpython-ecu_reader
#
# ----------------------------------------------------------------------------

import time

import ecu_reader

# --- connect-helper   -------------------------------------------------------

def connect():
  """ try to connect """
  for _ in range(3):
    try:
      print("connecting to AP...")
      wifi.radio.connect(secrets["ssid"], secrets["password"])
      print("... connected")
      break
    except Exception as e:
      print("Failed:\n", e)
      time.sleep(1)
      continue

# --- main program   ----------------------------------------------------------

# Get hostname/port and wifi details from a secrets.py file
try:
  from secrets import secrets
except ImportError:
  print("WiFi secrets are kept in secrets.py, please add them there!")
  raise

try:
  # CircuitPython
  import socketpool
  import wifi
  connect()
  pool = socketpool.SocketPool(wifi.radio)
except:
  # CPython
  import socket as pool

# setup interface
print("creating EcuReader")
inverter = ecu_reader.EcuReader(secrets["remoteip"],pool,
                                port=secrets["remoteport"],
                                debug=secrets.get("debug",False))

while True:
  print("reading data...")
  data = inverter.asdict()        # this will auto-update
  print(f"{data=}")

  # calculate wait-time for expected next update (every 5 minutes)
  wait_time = int(inverter.next_update()-time.time()+1)
  print(f"waiting for next update ({wait_time}s)")
  time.sleep(wait_time)
