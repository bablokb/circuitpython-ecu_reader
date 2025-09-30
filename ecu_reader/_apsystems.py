# ----------------------------------------------------------------------------
# CircuitPython Library for APSystems ECU-x Inverters.
#
# This is a port of https://github.com/ksheumaker/homeassistant-apsystems_ecur
# with minor adaptions for CircuitPython.
#
# Author: Bernhard Bablok
# License: Apache 2.0 (original license)
#
# Website: https://github.com/bablokb/circuitpython-ecu_reader
#
# ----------------------------------------------------------------------------

import binascii
import time

APSYSTEMS_UPD_INTERVAL = 300
""" update interval in seconds """

class APSystemsInvalidData(Exception):
  pass

class APSystemsInvalidInverter(Exception):
  pass

class APSystemsData:
  def __init__(self):
    self.last_update             = time.time() - APSYSTEMS_UPD_INTERVAL - 1
    self.timestamp               = None
    self.ecu_id                  = None
    self.inverters               = {}
    self.lifetime_energy         = None
    self.current_power           = None
    self.today_energy            = None
    self.qty_of_inverters        = None
    self.qty_of_online_inverters = None
    self.firmware                = None

class APSystemsSocket:
  """ socket abstraction for APSystems """

  def __init__(self,host,port,pool,debug):
    if not debug:
      self._debug = lambda x: None
    self._host = host
    self._port = port
    self._pool = pool

    # what do we expect socket data to end in
    self._recv_suffix = b'END\n'

    # how long to wait on socket commands until we get our recv_suffix
    self._timeout = 30

    # how big of a buffer to read at a time from the socket
    # https://github.com/ksheumaker/homeassistant-apsystems_ecur/issues/108
    self._recv_size = 1024

    # how long to wait between socket open/closes
    self._socket_sleep_time = 5

    self._cmd_suffix = "END\n"
    self._ecu_query = "APS1100160001" + self._cmd_suffix
    self._inverter_query_prefix = "APS1100280002"
    self._inverter_query_suffix = self._cmd_suffix
    self._inverter_signal_prefix = "APS1100280030"
    self._inverter_signal_suffix = self._cmd_suffix
    self._inverter_byte_start = 26

    self._ecu_raw_data = None
    self._inverter_raw_data = None
    self._inverter_raw_signal = None
    self._socket_open = False
    self._errors = []

  def _debug(self,msg):
    """ print debug message """
    print(msg)

  def _send_read_from_socket(self, cmd, buffer):
    try:
      self._sock.settimeout(self._timeout)
      self._sock.sendall(cmd.encode('utf-8'))
      time.sleep(self._socket_sleep_time)
      # An infinite loop was causing the integration to block
      # https://github.com/ksheumaker/homeassistant-apsystems_ecur/issues/115
      # Solution might cause a new issue when large solar array's applies
      self._sock.recv_into(buffer,self._recv_size)
      return
    except Exception as err:
      self._close_socket()
      raise APSystemsInvalidData(err)

  def _close_socket(self):
    try:
      if self._socket_open:
        data = bytearray(self._recv_size)
        self._sock.recv_into(data,self._recv_size) #flush incoming/outgoing data after shutdown request before actually closing the socket
        self._sock.close()
        self._socket_open = False
    except Exception as err:
      raise APSystemsInvalidData(err)

  def _open_socket(self):
    self._socket_open = False
    try:
      self._sock = self._pool.socket(family=self._pool.AF_INET,
                                    type=self._pool.SOCK_STREAM)
      self._sock.settimeout(self._timeout)
      self._debug(f"connecting to {self._host}:{self._port} ...")
      self._sock.connect((self._host, self._port))
      self._socket_open = True
    except Exception as err:
      raise APSystemsInvalidData(err)

  def read(self,data):
    """ read data from APSystems """

    self._open_socket()
    cmd = self._ecu_query
    self._ecu_raw_data = bytearray(self._recv_size)
    self._send_read_from_socket(cmd,self._ecu_raw_data)
    self._close_socket()

    # read and process basic data
    try:
      self._parse_ecu_data(data)
      if data.lifetime_energy == 0:
        error = f"ECU returned 0 for lifetime energy, this is either a glitch from the ECU or a brand new installed ECU. Raw Data={self._ecu_raw_data}"
        self._add_error(error)
        raise APSystemsInvalidData(error)
    except Exception as err:
      raise APSystemsInvalidData(err)

    # read inverter data (part1)
    self._open_socket()
    cmd = (self._inverter_query_prefix +
           data.ecu_id + self._inverter_query_suffix)
    self._inverter_raw_data = bytearray(self._recv_size)
    self._send_read_from_socket(cmd,self._inverter_raw_data)
    self._close_socket()

    # read inverter data (part2)
    self._open_socket()
    cmd = (self._inverter_signal_prefix +
           data.ecu_id + self._inverter_signal_suffix)
    self._inverter_raw_signal = bytearray(self._recv_size)
    self._send_read_from_socket(cmd,self._inverter_raw_signal)
    self._close_socket()

    # process inverter data
    self._parse_inverter_data(data)

  def _aps_int(self, codec, start):
    try:
      return int(binascii.hexlify(codec[(start):(start+2)]), 16)
    except ValueError as err:
      debugdata = binascii.hexlify(codec)
      error = f"Unable to convert binary to int location={start} data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

  def _aps_short(self, codec, start):
    try:
      return int(binascii.hexlify(codec[(start):(start+1)]), 8)
    except ValueError as err:
      debugdata = binascii.hexlify(codec)
      error = f"Unable to convert binary to short int location={start} data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

  def _aps_double(self, codec, start):
    try:
      return int (binascii.hexlify(codec[(start):(start+4)]), 16)
    except ValueError as err:
      debugdata = binascii.hexlify(codec)
      error = f"Unable to convert binary to double location={start} data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

  def _aps_bool(self, codec, start):
    return bool(binascii.hexlify(codec[(start):(start+2)]))

  def _aps_uid(self, codec, start):
    return str(binascii.hexlify(codec[(start):(start+12)]))[2:14]

  def _aps_str(self, codec, start, amount):
    return codec[start:(start+amount)].decode('utf-8')

  def _aps_timestamp(self, codec, start, amount):
    timestr=str(binascii.hexlify(codec[start:(start+amount)]))[2:(amount+2)]
    return timestr[0:4]+"-"+timestr[4:6]+"-"+timestr[6:8]+" "+timestr[8:10]+":"+timestr[10:12]+":"+timestr[12:14]

  def _check_ecu_checksum(self, data, cmd):
    datalen = len(data) - 1
    try:
      checksum = int(data[5:9])
    except ValueError as err:
      debugdata = binascii.hexlify(data)
      error = f"could not extract checksum int from '{cmd}' data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

    if datalen != checksum:
      debugdata = binascii.hexlify(data)
      error = f"Checksum on '{cmd}' failed checksum={checksum} datalen={datalen} data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

    start_str = self._aps_str(data, 0, 3)
    end_str = self._aps_str(data, len(data) - 4, 3)

    if start_str != 'APS':
      debugdata = binascii.hexlify(data)
      error = f"Result on '{cmd}' incorrect start signature '{start_str}' != APS data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

    if end_str != 'END':
      debugdata = binascii.hexlify(data)
      error = f"Result on '{cmd}' incorrect end signature '{end_str}' != END data={debugdata}"
      self._add_error(error)
      raise APSystemsInvalidData(error)

    return True

  def _parse_ecu_data(self, result):
    data = self._ecu_raw_data
    data_len = data.find(b'END')+3
    self._debug("ecu_raw_data:")
    self._debug(data[:data_len])
    self._debug(f"data[9:9+4]:     {data[9:13]}")
    self._debug(f"ecu_id:          {data[13:25]}")
    self._debug(f"lifetime energy: {data[27:31]}")
    self._debug(f"today energy:    {data[35:39]}")
    self._debug(f"current power:   {data[31:35]}")
    self._debug(f"data[25:25+2]:   {data[25:27]}")
    self._debug(60*'-')

    if self._ecu_raw_data != '' and (self._aps_str(self._ecu_raw_data,9,4)) == '0001':
      self._check_ecu_checksum(data[:data_len+1], "ECU Query")
      result.ecu_id = self._aps_str(data, 13, 12)
      result.lifetime_energy = self._aps_double(data, 27) / 10
      result.current_power = self._aps_double(data, 31)
      result.today_energy = self._aps_double(data, 35) / 100
      if self._aps_str(data,25,2) == "01":
        result.qty_of_inverters = self._aps_int(data, 46)
        result.qty_of_online_inverters = self._aps_int(data, 48)
        vsl = int(self._aps_str(data, 52, 3))
        result.firmware = self._aps_str(data, 55, vsl)
      elif self._aps_str(data,25,2) == "02":
        result.qty_of_inverters = self._aps_int(data, 39)
        result.qty_of_online_inverters = self._aps_int(data, 41)
        vsl = int(self._aps_str(data, 49, 3))
        result.firmware = self._aps_str(data, 52, vsl)

      self._debug(f"{result.ecu_id=}")
      self._debug(f"{result.lifetime_energy=}")
      self._debug(f"{result.current_power=}")
      self._debug(f"{result.today_energy=}")
      self._debug(f"{result.qty_of_inverters=}")
      self._debug(f"{result.qty_of_online_inverters=}")
      self._debug(f"{result.firmware=}")
      self._debug(60*'-')

  def _parse_signal_data(self, result):
    data = self._inverter_raw_signal
    data_len = data.find(b'END')+3
    self._debug("inverter_raw_data:")
    self._debug(data[:data_len])
    self._debug(60*'-')
    signal_data = {}
    if (self._inverter_raw_signal != '' and
        (self._aps_str(self._inverter_raw_signal,9,4)) == '0030'):
      self._check_ecu_checksum(data[:data_len+1], "Signal Query")
      if not result.qty_of_inverters:
        return signal_data
      location = 15
      for i in range(0, result.qty_of_inverters):
        uid = self._aps_uid(data, location)
        location += 6
        strength = data[location]
        location += 1
        strength = int((strength / 255) * 100)
        signal_data[uid] = strength
      return signal_data

  def _parse_inverter_data(self, result):
    data = self._inverter_raw_data
    data_len = data.find(b'END')+3
    self._debug("inverter_raw_data:")
    self._debug(data[:data_len])
    self._debug(60*'-')
    result.inverters = {}
    if (self._inverter_raw_data != '' and
        (self._aps_str(self._inverter_raw_data,9,4)) == '0002'):
      self._check_ecu_checksum(data[:data_len+1], "Inverter data")
      istr = ''
      cnt1 = 0
      cnt2 = 26
      if self._aps_str(data, 14, 2) == '00':
        result.timestamp = self._aps_timestamp(data, 19, 14)
        result.last_update = self._timestamp2epoch(result.timestamp)

        inverter_qty = self._aps_int(data, 17) 
        signal = self._parse_signal_data(result)
        result.inverters = {}

        while cnt1 < inverter_qty:
          inv={}
          if self._aps_str(data, 15, 2) == '01':
            inverter_uid = self._aps_uid(data, cnt2)
            inv["uid"] = inverter_uid
            inv["online"] = bool(self._aps_short(data, cnt2 + 6))
            istr = self._aps_str(data, cnt2 + 7, 2)
            inv["signal"] = signal.get(inverter_uid, 0)
            if istr in [ '01', '04', '05']:
              power = []
              voltages = []
              inv["frequency"] = self._aps_int(data, cnt2 + 9) / 10
              if inv["online"]:
                inv["temperature"] = self._aps_int(data, cnt2 + 11) - 100
              power.append(self._aps_int(data, cnt2 + 13))
              voltages.append(self._aps_int(data, cnt2 + 15))
              power.append(self._aps_int(data, cnt2 + 17))
              voltages.append(self._aps_int(data, cnt2 + 19))
              inv_details = {
              "model" : "YC600/DS3/DS3D-L/DS3-H",
              "channel_qty" : 2,
              "power" : power,
              "voltage" : voltages
              }
              inv.update(inv_details)
              cnt2 = cnt2 + 21
            elif istr == '02':
              power = []
              voltages = []
              inv["frequency"] = self._aps_int(data, cnt2 + 9) / 10
              if inv["online"]:
                inv["temperature"] = self._aps_int(data, cnt2 + 11) - 100
              power.append(self._aps_int(data, cnt2 + 13))
              voltages.append(self._aps_int(data, cnt2 + 15))
              power.append(self._aps_int(data, cnt2 + 17))
              voltages.append(self._aps_int(data, cnt2 + 19))
              power.append(self._aps_int(data, cnt2 + 21))
              voltages.append(self._aps_int(data, cnt2 + 23))
              power.append(self._aps_int(data, cnt2 + 25))
              inv_details = {
              "model" : "YC1000/QT2",
              "channel_qty" : 4,
              "power" : power,
              "voltage" : voltages
              }
              inv.update(inv_details)
              cnt2 = cnt2 + 27
            elif istr == '03':
              power = []
              voltages = []
              inv["frequency"] = self._aps_int(data, cnt2 + 9) / 10
              if inv["online"]:
                inv["temperature"] = self._aps_int(data, cnt2 + 11) - 100
              power.append(self._aps_int(data, cnt2 + 13))
              voltages.append(self._aps_int(data, cnt2 + 15))
              power.append(self._aps_int(data, cnt2 + 17))
              power.append(self._aps_int(data, cnt2 + 19))
              power.append(self._aps_int(data, cnt2 + 21))
              inv_details = {
              "model" : "QS1",
              "channel_qty" : 4,
              "power" : power,
              "voltage" : voltages
              }
              inv.update(inv_details)
              cnt2 = cnt2 + 23
            else:
              cnt2 = cnt2 + 9
            result.inverters[inverter_uid] = inv
          cnt1 = cnt1 + 1
        return

  def __add_error(self, error):
    ts = time.localtime()
    self._errors.append("[%04d-%02d-%02d %02d:%02d:%02d] %s" %
                       (ts.tm_year,ts.tm_mon,ts.tm_mday,
                        ts.tm_hour,ts.tm_min,ts.tm_sec, error))

  def _timestamp2epoch(self, tstamp):
    """ convert timestamp to seconds since 01/01/1970 """
    date,tm = tstamp.split(" ")
    y,m,d = date.split("-")
    h,M,s = tm.split(":")
    return time.mktime((int(y),int(m),int(d),int(h),int(M),int(s),0,-1,-1))
