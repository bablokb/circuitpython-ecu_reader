# ----------------------------------------------------------------------------
# Simple testprogram for the ecu_reader library.
#
# This example shows how to manually update the data in case the internal
# rtc of the device does not have the correct time.
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
if secrets.get("debug",False):
  print("creating EcuReader")
inverter = ecu_reader.EcuReader(secrets["remoteip"],pool,
                                port=secrets["remoteport"],
                                debug=secrets.get("debug",False),
                                auto_update=False)

print("Time  | Power(W)")
print("------|---------")
while True:
  start = time.time()
  if secrets.get("debug",False):
    print("reading data...")
  inverter.update(force=True)
  print(f"{inverter.timestamp.split(' ')[1][:5]} | {inverter.current_power:5.1f}")
  duration = time.time()-start
  
  # wait at least APSYSTEMS_UPD_INTERVAL - update-duration
  wait_time = int(ecu_reader.APSYSTEMS_UPD_INTERVAL - duration)
  if secrets.get("debug",False):
    print(f"waiting for next update ({wait_time}s)")
  time.sleep(wait_time)
