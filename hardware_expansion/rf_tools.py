"""
HK-47 OS :: hardware_expansion/rf_tools.py
Interface for the Texas Instruments CC1101 sub-1GHz transceiver via SPI
(default /dev/spidev0.0). Configured for 433.92MHz ASK/OOK/FSK sniff and
capture. Degrades to simulation mode when SPI hardware is absent.
"""

import json
import logging
import time

try:
    import spidev
    _SPIDEV_AVAILABLE = True
except ImportError:
    spidev = None
    _SPIDEV_AVAILABLE = False

try:
    import config
    _DEFAULT_SPI_DEV = getattr(config, "RF_SPI_DEV", "/dev/spidev0.0")
    _DEFAULT_FREQ = getattr(config, "RF_DEFAULT_FREQ_MHZ", 433.92)
except ImportError:
    _DEFAULT_SPI_DEV = "/dev/spidev0.0"
    _DEFAULT_FREQ = 433.92

logger = logging.getLogger("hk47.rf")

# ---------------------------------------------------------------------------
# CC1101 Register Addresses
# ---------------------------------------------------------------------------
IOCFG2 = 0x00
IOCFG1 = 0x01
IOCFG0 = 0x02
FIFOTHR = 0x03
SYNC1 = 0x04
SYNC0 = 0x05
PKTLEN = 0x06
PKTCTRL1 = 0x07
PKTCTRL0 = 0x08
ADDR = 0x09
CHANNR = 0x0A
FSCTRL1 = 0x0B
FSCTRL0 = 0x0C
FREQ2 = 0x0D
FREQ1 = 0x0E
FREQ0 = 0x0F
MDMCFG4 = 0x10
MDMCFG3 = 0x11
MDMCFG2 = 0x12
MDMCFG1 = 0x13
MDMCFG0 = 0x14
DEVIATN = 0x15
MCSM2 = 0x16
MCSM1 = 0x17
MCSM0 = 0x18
FOCCFG = 0x19
BSCFG = 0x1A
AGCCTRL2 = 0x1B
AGCCTRL1 = 0x1C
AGCCTRL0 = 0x1D
WOREVT1 = 0x1E
WOREVT0 = 0x1F
WORCTRL = 0x20
FREND1 = 0x21
FREND0 = 0x22
FSCAL3 = 0x23
FSCAL2 = 0x24
FSCAL1 = 0x25
FSCAL0 = 0x26

# Command strobes
SRES = 0x30
SFSTXON = 0x31
SXOFF = 0x32
SCAL = 0x33
SRX = 0x34
STX = 0x35
SIDLE = 0x36
SFRX = 0x3A
SFTX = 0x3B

# Status / FIFO registers (burst bit 0x40 must be set for status registers)
PARTNUM = 0x30 | 0xC0
VERSION = 0x31 | 0xC0
FREQEST = 0x32 | 0xC0
LQI = 0x33 | 0xC0
RSSI = 0x34 | 0xC0
MARCSTATE = 0x35 | 0xC0
PKTSTATUS = 0x38 | 0xC0
RXBYTES = 0x3B | 0xC0
FIFO = 0x3F

# Crystal oscillator frequency (standard 26MHz crystal)
FXOSC_HZ = 26_000_000


class CC1101:
    """SPI driver for CC1101 sub-1GHz transceiver."""

    def __init__(self, spi_dev: str = _DEFAULT_SPI_DEV, freq_mhz: float = _DEFAULT_FREQ):
        self.spi_dev_path = spi_dev
        self.freq_mhz = freq_mhz
        self.spi = None

        if _SPIDEV_AVAILABLE:
            try:
                # Parse /dev/spidev<bus>.<device>
                base = spi_dev.replace("/dev/spidev", "")
                parts = base.split(".")
                bus = int(parts[0]) if len(parts) > 0 else 0
                device = int(parts[1]) if len(parts) > 1 else 0

                self.spi = spidev.SpiDev()
                self.spi.open(bus, device)
                self.spi.max_speed_hz = 5_000_000
                self.spi.mode = 0
                logger.info("CC1101 opened on %s.", spi_dev)
                self.initialize()
            except Exception as exc:
                logger.warning("CC1101 SPI open failed on %s (%s); simulation mode.",
                               spi_dev, exc)
                self.spi = None
        else:
            logger.warning("spidev not installed; CC1101 running in simulation mode.")

    # -----------------------------------------------------------------------
    # Low-level SPI operations
    # -----------------------------------------------------------------------
    def _cmd_strobe(self, strobe: int) -> int:
        if not self.spi:
            return 0
        try:
            resp = self.spi.xfer2([strobe & 0xFF])
            return resp[0]
        except Exception as exc:
            logger.debug("SPI strobe failed: %s", exc)
            return 0

    def _write_reg(self, reg: int, value: int):
        if not self.spi:
            return
        try:
            self.spi.xfer2([reg & 0x3F, value & 0xFF])
        except Exception as exc:
            logger.debug("SPI write reg failed: %s", exc)

    def _read_reg(self, reg: int) -> int:
        if not self.spi:
            return 0
        try:
            resp = self.spi.xfer2([(reg & 0x3F) | 0x80, 0x00])
            return resp[1]
        except Exception as exc:
            logger.debug("SPI read reg failed: %s", exc)
            return 0

    def _read_status(self, reg: int) -> int:
        if not self.spi:
            return 0
        try:
            resp = self.spi.xfer2([reg & 0xFF, 0x00])
            return resp[1]
        except Exception as exc:
            logger.debug("SPI read status failed: %s", exc)
            return 0

    # -----------------------------------------------------------------------
    # High-level transceiver control
    # -----------------------------------------------------------------------
    def initialize(self):
        """Reset and configure for 433.92MHz ASK/OOK packet capture."""
        if not self.spi:
            return
        self._cmd_strobe(SRES)
        time.sleep(0.005)

        # Baseline SmartRF configuration for 433.92MHz OOK / variable packet length
        self._write_reg(IOCFG0, 0x06)    # GDO0: sync word / packet RX
        self._write_reg(FIFOTHR, 0x47)
        self._write_reg(PKTLEN, 0x3F)    # Max 63-byte packets
        self._write_reg(PKTCTRL1, 0x04)  # Append status (RSSI+LQI)
        self._write_reg(PKTCTRL0, 0x01)  # Variable packet length mode
        self._write_reg(FSCTRL1, 0x06)
        self._write_reg(MDMCFG4, 0xF7)   # Filter bandwidth 100kHz
        self._write_reg(MDMCFG3, 0x32)   # Data rate ~4.8kbps
        self._write_reg(MDMCFG2, 0x30)   # 30/32 sync word, ASK/OOK modulation
        self._write_reg(MDMCFG1, 0x22)
        self._write_reg(MDMCFG0, 0xF8)
        self._write_reg(MCSM0, 0x18)     # Auto-calibrate when going idle->RX/TX
        self._write_reg(FOCCFG, 0x16)
        self._write_reg(AGCCTRL2, 0x43)
        self._write_reg(FSCAL3, 0xE9)
        self._write_reg(FSCAL2, 0x2A)
        self._write_reg(FSCAL1, 0x00)
        self._write_reg(FSCAL0, 0x1F)

        self.set_frequency(self.freq_mhz)

    def set_frequency(self, freq_mhz: float):
        """Program FREQ2, FREQ1, FREQ0 for the requested carrier frequency."""
        self.freq_mhz = freq_mhz
        freq_word = int(round((freq_mhz * 1_000_000 * (2 ** 16)) / FXOSC_HZ))
        f2 = (freq_word >> 16) & 0xFF
        f1 = (freq_word >> 8) & 0xFF
        f0 = freq_word & 0xFF
        self._write_reg(FREQ2, f2)
        self._write_reg(FREQ1, f1)
        self._write_reg(FREQ0, f0)

    def receive_packet(self, timeout=5.0) -> bytes:
        """Enter RX mode and wait up to `timeout` seconds for a packet."""
        if not self.spi:
            time.sleep(min(timeout, 0.1))
            return None

        self._cmd_strobe(SIDLE)
        self._cmd_strobe(SFRX)
        self._cmd_strobe(SRX)

        deadline = time.time() + timeout
        while time.time() < deadline:
            rxbytes = self._read_status(RXBYTES) & 0x7F
            if rxbytes > 0:
                # Read length byte first, then the remaining bytes.
                length = self._read_reg(FIFO)
                if 0 < length <= 63:
                    data = [length]
                    for _ in range(min(length, rxbytes - 1)):
                        data.append(self._read_reg(FIFO))
                    self._cmd_strobe(SIDLE)
                    return bytes(data)
                # Flush invalid FIFO state.
                self._cmd_strobe(SIDLE)
                self._cmd_strobe(SFRX)
                self._cmd_strobe(SRX)
            time.sleep(0.02)

        self._cmd_strobe(SIDLE)
        return None

    def scan_frequencies(self, freq_list: list, dwell_ms: int = 100) -> dict:
        """Dwell on each frequency and count received packets."""
        results = {}
        for freq in freq_list:
            self.set_frequency(freq)
            pkt = self.receive_packet(timeout=dwell_ms / 1000.0)
            results[freq] = 1 if pkt else 0
        return results

    def sniff_433(self, duration: int = 30, vault=None) -> list:
        """Listen on 433.92MHz for `duration` seconds, capturing packets."""
        captures = []
        self.set_frequency(433.92)
        deadline = time.time() + duration

        while time.time() < deadline:
            pkt = self.receive_packet(timeout=1.0)
            if pkt:
                cap = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "freq_mhz": 433.92,
                    "length": len(pkt),
                    "hex": pkt.hex(),
                }
                captures.append(cap)

        if vault is not None and captures:
            try:
                raw = vault.retrieve("rf_captures")
                history = json.loads(raw) if raw else []
                history.extend(captures)
                vault.store("rf_captures", json.dumps(history[-100:]))
            except Exception as exc:
                logger.debug("Vault RF store failed: %s", exc)

        return captures

    def close(self):
        if self.spi:
            try:
                self._cmd_strobe(SIDLE)
                self.spi.close()
            except Exception:
                pass
            self.spi = None
