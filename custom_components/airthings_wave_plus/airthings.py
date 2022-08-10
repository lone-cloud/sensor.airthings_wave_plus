import struct
import time
from collections import namedtuple

import logging
from datetime import datetime

from bleak import BleakClient
import asyncio
from homeassistant.components import bluetooth

from uuid import UUID

_LOGGER = logging.getLogger(__name__)

# Use full UUID since we do not use UUID from bluetooth library
CHAR_UUID_MANUFACTURER_NAME = UUID('00002a29-0000-1000-8000-00805f9b34fb')
CHAR_UUID_SERIAL_NUMBER_STRING = UUID('00002a25-0000-1000-8000-00805f9b34fb')
CHAR_UUID_MODEL_NUMBER_STRING = UUID('00002a24-0000-1000-8000-00805f9b34fb')
CHAR_UUID_DEVICE_NAME = UUID('00002a00-0000-1000-8000-00805f9b34fb')
CHAR_UUID_FIRMWARE_REV = UUID('00002a26-0000-1000-8000-00805f9b34fb')
CHAR_UUID_HARDWARE_REV = UUID('00002a27-0000-1000-8000-00805f9b34fb')

CHAR_UUID_DATETIME = UUID('00002a08-0000-1000-8000-00805f9b34fb')
CHAR_UUID_TEMPERATURE = UUID('00002a6e-0000-1000-8000-00805f9b34fb')
CHAR_UUID_HUMIDITY = UUID('00002a6f-0000-1000-8000-00805f9b34fb')
CHAR_UUID_RADON_1_DAY_AVG = UUID('b42e01aa-ade7-11e4-89d3-123b93f75cba')
CHAR_UUID_RADON_LONG_TERM_AVG = UUID('b42e0a4c-ade7-11e4-89d3-123b93f75cba')
CHAR_UUID_ILLUMINANCE_ACCELEROMETER = UUID(
    'b42e1348-ade7-11e4-89d3-123b93f75cba')
CHAR_UUID_WAVE_PLUS_DATA = UUID('b42e2a68-ade7-11e4-89d3-123b93f75cba')
CHAR_UUID_WAVE_2_DATA = UUID('b42e4dcc-ade7-11e4-89d3-123b93f75cba')
CHAR_UUID_WAVE_MINI_DATA = UUID('b42e3b98-ade7-11e4-89d3-123b93f75cba')
# "Access Control Point" Characteristic
COMMAND_UUID = UUID('b42e2d06-ade7-11e4-89d3-123b93f75cba')

Characteristic = namedtuple('Characteristic', ['uuid', 'name', 'format'])

manufacturer_characteristics = Characteristic(
    CHAR_UUID_MANUFACTURER_NAME, 'manufacturer', "utf-8")
device_info_characteristics = [manufacturer_characteristics,
                               Characteristic(
                                   CHAR_UUID_SERIAL_NUMBER_STRING, 'serial_nr', "utf-8"),
                               Characteristic(
                                   CHAR_UUID_MODEL_NUMBER_STRING, 'model_nr', "utf-8"),
                               Characteristic(
                                   CHAR_UUID_DEVICE_NAME, 'device_name', "utf-8"),
                               Characteristic(
                                   CHAR_UUID_FIRMWARE_REV, 'firmware_rev', "utf-8"),
                               Characteristic(CHAR_UUID_HARDWARE_REV, 'hardware_rev', "utf-8")]


class AirthingsDeviceInfo:
    def __init__(self, manufacturer='', serial_nr='', model_nr='', device_name='', firmware_rev='', hardware_rev=''):
        self.manufacturer = manufacturer
        self.serial_nr = serial_nr
        self.model_nr = model_nr
        self.device_name = device_name
        self.firmware_rev = firmware_rev
        self.hardware_rev = hardware_rev

    def __str__(self):
        return "Manufacturer: {} Model: {} Serial: {} Device: {} Firmware: {} Hardware Rev.: {}".format(
            self.manufacturer, self.model_nr, self.serial_nr, self.device_name, self.firmware_rev, self.hardware_rev)


sensors_characteristics_uuid = [CHAR_UUID_DATETIME, CHAR_UUID_TEMPERATURE, CHAR_UUID_HUMIDITY, CHAR_UUID_RADON_1_DAY_AVG,
                                CHAR_UUID_RADON_LONG_TERM_AVG, CHAR_UUID_ILLUMINANCE_ACCELEROMETER,
                                CHAR_UUID_WAVE_PLUS_DATA, CHAR_UUID_WAVE_2_DATA, CHAR_UUID_WAVE_MINI_DATA,
                                COMMAND_UUID]

sensors_characteristics_uuid_str = [
    str(x) for x in sensors_characteristics_uuid]


class BaseDecode:
    def __init__(self, name, format_type, scale):
        self.name = name
        self.format_type = format_type
        self.scale = scale

    def decode_data(self, raw_data):
        val = struct.unpack(
            self.format_type,
            raw_data)
        if len(val) == 1:
            res = val[0] * self.scale
        else:
            res = val
        return {self.name: res}


class WavePlusDecode(BaseDecode):
    def decode_data(self, raw_data):
        val = super().decode_data(raw_data)
        val = val[self.name]
        data = {}
        data['date_time'] = str(datetime.isoformat(datetime.now()))
        data['humidity'] = val[1]/2.0
        data['radon_1day_avg'] = val[4] if 0 <= val[4] <= 16383 else None
        data['radon_long_term_avg'] = val[5] if 0 <= val[5] <= 16383 else None
        data['temperature'] = val[6]/100.0
        data['rel_atm_pressure'] = val[7]/50.0
        data['co2'] = val[8]*1.0
        data['voc'] = val[9]*1.0
        return data


class Wave2Decode(BaseDecode):
    def decode_data(self, raw_data):
        val = super().decode_data(raw_data)
        val = val[self.name]
        data = {}
        data['date_time'] = str(datetime.isoformat(datetime.now()))
        data['humidity'] = val[1]/2.0
        data['radon_1day_avg'] = val[4] if 0 <= val[4] <= 16383 else None
        data['radon_long_term_avg'] = val[5] if 0 <= val[5] <= 16383 else None
        data['temperature'] = val[6]/100.0
        return data


class WaveMiniDecode(BaseDecode):
    def decode_data(self, raw_data):
        val = super().decode_data(raw_data)
        val = val[self.name]
        data = {}
        data['date_time'] = str(datetime.isoformat(datetime.now()))
        data['temperature'] = round(val[1]/100.0 - 273.15, 2)
        data['humidity'] = val[3]/100.0
        data['voc'] = val[4]*1.0
        return data


class WaveDecodeDate(BaseDecode):
    def decode_data(self, raw_data):
        val = super().decode_data(raw_data)[self.name]
        data = {self.name: str(
            datetime(val[0], val[1], val[2], val[3], val[4], val[5]).isoformat())}
        return data


class WaveDecodeIlluminanceAccel(BaseDecode):
    def decode_data(self, raw_data):
        val = super().decode_data(raw_data)[self.name]
        data = {}
        data['illuminance'] = str(val[0] * self.scale)
        data['accelerometer'] = str(val[1] * self.scale)
        return data


class CommandDecode:
    def __init__(self, name, format_type, cmd):
        self.name = name
        self.format_type = format_type
        self.cmd = cmd

    def decode_data(self, raw_data):
        if raw_data is None:
            return {}
        cmd = raw_data[0:1]
        if cmd != self.cmd:
            _LOGGER.warning("Result for Wrong command received, expected {} got {}".format(
                self.cmd.hex(), cmd.hex()))
            return {}

        if len(raw_data[2:]) != struct.calcsize(self.format_type):
            _LOGGER.debug("Wrong length data received ({}) verses expected ({})".format(
                len(cmd), struct.calcsize(self.format_type)))
            return {}
        val = struct.unpack(
            self.format_type,
            raw_data[2:])
        res = {}
        res['illuminance'] = val[2]
        #res['measurement_periods'] =  val[5]
        res['battery'] = val[17] / 1000.0

        return res


sensor_decoders = {str(CHAR_UUID_WAVE_PLUS_DATA): WavePlusDecode(name="Plus", format_type='BBBBHHHHHHHH', scale=0),
                   str(CHAR_UUID_DATETIME): WaveDecodeDate(name="date_time", format_type='HBBBBB', scale=0),
                   str(CHAR_UUID_HUMIDITY): BaseDecode(name="humidity", format_type='H', scale=1.0/100.0),
                   str(CHAR_UUID_RADON_1_DAY_AVG): BaseDecode(name="radon_1day_avg", format_type='H', scale=1.0),
                   str(CHAR_UUID_RADON_LONG_TERM_AVG): BaseDecode(name="radon_long_term_avg", format_type='H', scale=1.0),
                   str(CHAR_UUID_ILLUMINANCE_ACCELEROMETER): WaveDecodeIlluminanceAccel(name="illuminance_accelerometer", format_type='BB', scale=1.0),
                   str(CHAR_UUID_TEMPERATURE): BaseDecode(name="temperature", format_type='h', scale=1.0/100.0),
                   str(CHAR_UUID_WAVE_2_DATA): Wave2Decode(name="Wave2", format_type='<4B8H', scale=1.0),
                   str(CHAR_UUID_WAVE_MINI_DATA): WaveMiniDecode(name="WaveMini", format_type='<HHHHHHLL', scale=1.0), }

command_decoders = {str(COMMAND_UUID): CommandDecode(
    name="Battery", format_type='<L12B6H', cmd=struct.pack('<B', 0x6d))}


class AirthingsWaveDetect:
    def __init__(self, scan_interval, mac=None):
        self.airthings_devices = [] if mac is None else [mac]
        self.sensors = []
        self.sensor_data = {}
        self.scan_interval = scan_interval
        self.last_scan = -1
        self._dev = None
        self._command_data = None

    def notification_handler(self, sender, data):
        _LOGGER.debug("Notification handler: {0}: {1}".format(sender, data))
        self._command_data = data
        self._event.set()

    async def find_devices(self, scanner, scans=2, timeout=5):
        # Search for devices, scan for BLE devices scans times for timeout seconds
        # Get manufacturer data and try to match it to airthings ID.

        _LOGGER.debug("Scanning for airthings devices")
        for _ in range(scans):
            for adv in await scanner.discover(timeout):
                # TODO: Not sure if this is the best way to identify Airthings devices
                if 820 in adv.metadata["manufacturer_data"]:
                    if adv.address not in self.airthings_devices:
                        self.airthings_devices.append(adv.address)

        _LOGGER.debug("Found {} airthings devices".format(
            len(self.airthings_devices)))
        return len(self.airthings_devices)

    async def connect(self, mac, hass, retries=10):
        _LOGGER.debug("Connecting to {}".format(mac))
        await self.disconnect()
        tries = 0
        while (tries < retries):
            tries += 1
            try:
                bleDevice = bluetooth.async_ble_device_from_address(hass, mac)
                _LOGGER.debug("Got BLEDevice {0}".format(bleDevice))
                _LOGGER.debug("XXX {}".format(str(bleDevice)))
                self._dev = BleakClient(bleDevice)
                ret = await self._dev.connect()
                if ret:
                    _LOGGER.debug("Connected to {}".format(mac))
                    break
            except Exception as e:
                if tries == retries:
                    _LOGGER.info(
                        "Not able to connect to {} because {}".format(mac, e))
                    pass
                else:
                    _LOGGER.debug("Retrying {} because {}".format(mac, e))

    async def disconnect(self):
        if self._dev is not None:
            await self._dev.disconnect()
            self._dev = None

    async def get_info(self, hass):
        # Try to get some info from the discovered airthings devices
        self.devices = {}
        for mac in self.airthings_devices:
            await self.connect(mac, hass)
            if self._dev is not None and self._dev.is_connected:
                try:
                    if self._dev is not None and self._dev.is_connected:
                        device = AirthingsDeviceInfo(serial_nr=mac)
                        for characteristic in device_info_characteristics:
                            try:
                                data = await self._dev.read_gatt_char(characteristic.uuid)
                                setattr(device, characteristic.name,
                                        data.decode(characteristic.format))
                            except Exception as e:
                                _LOGGER.exception(
                                    "Error getting info: {}".format(e))
                                self._dev = None
                    self.devices[mac] = device
                except Exception as e:
                    _LOGGER.exception(
                        "Error getting device info: {}".format(e))
                await self.disconnect()
            else:
                _LOGGER.error(
                    "Not getting device info because failed to connect to device.")
        return self.devices

    async def get_sensors(self, hass):
        self.sensors = {}
        for mac in self.airthings_devices:
            await self.connect(mac, hass)
            if self._dev is not None and self._dev.is_connected:
                sensor_characteristics = []
                services = await self._dev.get_services()
                for service in services:
                    for characteristic in service.characteristics:
                        _LOGGER.debug(characteristic)
                        if characteristic.uuid in sensors_characteristics_uuid_str:
                            sensor_characteristics.append(characteristic)
                self.sensors[mac] = sensor_characteristics
            await self.disconnect()
        return self.sensors

    async def get_sensor_data(self, hass):
        if time.monotonic() - self.last_scan > self.scan_interval or self.last_scan == -1:
            self.last_scan = time.monotonic()
            for mac, characteristics in self.sensors.items():
                await self.connect(mac, hass)
                if self._dev is not None and self._dev.is_connected:
                    try:
                        for characteristic in characteristics:
                            sensor_data = None
                            if str(characteristic.uuid) in sensor_decoders:
                                data = await self._dev.read_gatt_char(characteristic.uuid)
                                sensor_data = sensor_decoders[str(
                                    characteristic.uuid)].decode_data(data)
                                _LOGGER.debug(
                                    "{} Got sensor_data {}".format(mac, sensor_data))

                            if str(characteristic.uuid) in command_decoders:
                                _LOGGER.debug("command characteristic: {}".format(
                                    characteristic.uuid))
                                # Create an Event object.
                                self._event = asyncio.Event()
                                # Set up the notification handlers
                                await self._dev.start_notify(characteristic.uuid, self.notification_handler)
                                # send command to this 'indicate' characteristic
                                await self._dev.write_gatt_char(characteristic.uuid, command_decoders[str(characteristic.uuid)].cmd)
                                # Wait for up to one second to see if a callback comes in.
                                try:
                                    await asyncio.wait_for(self._event.wait(), 1)
                                except asyncio.TimeoutError:
                                    _LOGGER.warn(
                                        "Timeout getting command data.")
                                if self._command_data is not None:
                                    sensor_data = command_decoders[str(
                                        characteristic.uuid)].decode_data(self._command_data)
                                    self._command_data = None
                                # Stop notification handler
                                await self._dev.stop_notify(characteristic.uuid)

                            if sensor_data is not None:
                                if self.sensor_data.get(mac) is None:
                                    self.sensor_data[mac] = sensor_data
                                else:
                                    self.sensor_data[mac].update(sensor_data)
                    except Exception as e:
                        _LOGGER.exception(
                            "Error getting sensor data: {}".format(e))
                        self._dev = None

                await self.disconnect()

        return self.sensor_data
