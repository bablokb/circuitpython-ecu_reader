Query Data from APSystems ECU-x Systems
=======================================

This repository provides a library to query data from APSystems ECU-x
inverters.

The code is ported from
<https://github.com/ksheumaker/homeassistant-apsystems_ecur> with
minor adaptions. It runs with CircuitPython and CPython. MicroPython
should also work (maybe with minor modifications).


Installation
------------

Just copy `ecu_reader/` to your device. No other libraries are necessary.


Usage
-----

See one of the examples below `examples/`. You basically create an
inverter object:

    import socketpool
    import wifi
    
    import ecu_reader
    
    wifi.radio.connect('my_ssid','my_passwd')
    pool = socketpool.SocketPool(wifi.radio)
    
    inverter = ecu_reader.EcuReader("ip_of_inverter",pool)

and then read the data as attributes which will automatically trigger
reading the data from the ECU-x device:

    print(inverter.timestamp, inverter.current_power)

Since the inverter updates the data only every five minutes, the
`EcuReader`-class provides some utility-methods that support
optimizing the query intervals (see the examples on how to use this
feature).

In addition, reading one of the attributes will only trigger an update
if the data is considered old (i.e. older as five minutes). Otherwise,
the attribute returns cached data.

**If your device does not have a correct time, the time-dependent
logic won't work.** In this, case, pass `auto_update=False` to the
constructor and manage data-updates manually using
`inverter.update(force=True)`. See
[`examples/manual/main.py`](examples/manual/main.py) for a simple
template.
