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

""" class EcuReader - public visible interface class """

import time

from ._apsystems import APSYSTEMS_UPD_INTERVAL, APSystemsData, APSystemsSocket

class EcuReader:
  """ interface class for APSystems ECU-x inverters """

  # --- constructor   --------------------------------------------------------

  def __init__(self,host,pool,port=8899,debug=False,auto_update=True):
    """ constructor """

    # settings
    self._host = host
    self._port = port
    self._pool = pool
    self._debug = debug
    self._auto_update = auto_update
    self._inverter = APSystemsSocket(host,port,pool,debug)
    self._data = APSystemsData()

  # --- update data from inverter   ------------------------------------------

  def update(self, force=False):
    """ update data """

    if force or (self._auto_update and time.time() - self.next_update() > 0):
      self._inverter.read(self._data)

  # --- return data as dictionary   ------------------------------------------

  def asdict(self):
    """ data as dictionary """
    self.update()
    return {
      "last_update": self._data.last_update,
      "timestamp": self._data.timestamp,
      "ecu_id": self._data.ecu_id,
      "inverters": self._data.inverters,
      "lifetime_energy": self._data.lifetime_energy,
      "current_power": self._data.current_power,
      "today_energy": self._data.today_energy,
      "qty_of_inverters": self._data.qty_of_inverters,
      "qty_of_online_inverters": self._data.qty_of_online_inverters,
      "firmware": self._data.firmware,
      }

  # --- time of expected next update   ---------------------------------------

  def next_update(self) -> int:
    """ time of next expected data-update """
    return self._data.last_update + APSYSTEMS_UPD_INTERVAL

  # --- properties   ---------------------------------------------------------

  @property
  def last_update(self) -> int:
    """ timestamp of last update (seconds since epoch)"""
    return self._data.last_update

  @property
  def timestamp(self) -> str:
    """ timestamp of last update (human readable YYYY-mm-DD HH:MM:SS)"""
    self.update()
    return self._data.timestamp

  @property
  def ecu_id(self) -> str:
    """ ID of system """
    self.update()
    return self._data.ecu_id

  @property
  def inverters(self) -> dict:
    """ inverter data """
    self.update()
    return self._data.inverters

  @property
  def lifetime_energy(self) -> float:
    """ lifetime energy """
    self.update()
    return self._data.lifetime_energy

  @property
  def current_power(self) -> float:
    """ current power """
    self.update()
    return self._data.current_power


  @property
  def today_energy(self) -> float:
    """ today's energy """
    self.update()
    return self._data.today_energy

  @property
  def qty_of_inverters(self) -> int:
    """ number of configured inverters """
    self.update()
    return self._data.qty_of_inverters

  @property
  def qty_of_online_inverters(self) -> int:
    """ number of online inverters """
    self.update()
    return self._data.qty_of_online_inverters

  @property
  def firmware(self) -> str:
    """ firmware version """
    self.update()
    return self._data.firmware
