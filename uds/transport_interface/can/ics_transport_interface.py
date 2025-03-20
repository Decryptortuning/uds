"""
ics_transport_interface.py

Final example that:
  - Constructs CanPacketRecord with direction=TransmissionDirection.TX for send
    and direction=TransmissionDirection.RX for receive
  - No success=...
  - Provides (frame, direction, addressing_type, addressing_format, transmission_time)
  - For multi-frame UDS logic, either fallback single-frame or hardware ISO-TP
"""

import time
import logging
import threading
import ctypes
from queue import Queue, Empty
from typing import Any, Optional
import asyncio
from datetime import datetime

try:
    import ics
    ICS_AVAILABLE = True
except ImportError:
    ICS_AVAILABLE = False

# If your environment uses these libraries:
from uds.transport_interface.abstract_transport_interface import AbstractTransportInterface
from uds.packet.can.can_packet import CanPacket
from uds.packet.can.can_packet_record import CanPacketRecord
from uds.packet.can.can_packet_type import CanPacketType
from uds.segmentation.can_segmenter import CanSegmenter
from uds.can.flow_control import DefaultFlowControlParametersGenerator
from uds.can.addressing_format import CanAddressingFormat
from uds.transmission_attributes import AddressingType, TransmissionDirection
from uds.message.uds_message import UdsMessageRecord
from uds.can.addressing_information import CanAddressingInformation


class IcsTransportInterface(AbstractTransportInterface):
    """
    An example ICS-based Transport Interface implementing UDSONCAN 'style' behaviors:
     - Each raw CAN frame -> a CanPacketRecord
     - Each UDS message -> a UdsMessageRecord (hardware or fallback single-frame)
    """

    MAX_LOG_COUNT = 100

    def __init__(
        self,
        device=None,
        baudrate=500000,
        network_id=ics.NETID_HSCAN,
        enable_hw_iso_tp=False,
        hw_iso_tp_tx_id: Optional[int] = None,
        hw_iso_tp_rx_id: Optional[int] = None,
        flow_control_parameters=None,
        addressing_information=None,
        reinit_on_error: bool = False,
        periodic_status_interval: float = 0.0
    ):
        super().__init__(bus_manager=None)

        if not ICS_AVAILABLE:
            raise ImportError("python-ics not installed. Cannot use IcsTransportInterface.")

        self.logger = logging.getLogger(__name__)
        self.baudrate = baudrate
        self.network_id = network_id
        self.enable_hw_iso_tp = enable_hw_iso_tp
        self.hw_iso_tp_tx_id = hw_iso_tp_tx_id if hw_iso_tp_tx_id is not None else 0x7E0
        self.hw_iso_tp_rx_id = hw_iso_tp_rx_id if hw_iso_tp_rx_id is not None else 0x7E8
        self.reinit_on_error = reinit_on_error
        self.periodic_status_interval = periodic_status_interval

        self._log_count = 0
        self._last_status_time = 0.0

        # Default flow control config
        if flow_control_parameters is None:
            flow_control_parameters = DefaultFlowControlParametersGenerator(block_size=0, st_min=0)
        self.flow_control_params = flow_control_parameters

        if addressing_information is None:
            addressing_information = CanAddressingInformation(
                addressing_format=CanAddressingFormat.NORMAL_ADDRESSING
            )
        self.addressing_information = addressing_information

        self.device = None
        self._configure_and_open_device(device)

        self._segmenter = CanSegmenter(addressing_information=self.addressing_information)

        # Thread & queue for receiving
        self._rx_stop = threading.Event()
        self._rx_queue = Queue()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

        self.logger.info(
            f"IcsTransportInterface ready. Device={self.device}, baud={baudrate}, "
            f"netID={network_id}, hw_iso_tp={enable_hw_iso_tp}"
        )

    # --------------------------------------------------------------------------
    # region AbstractTransportInterface mandatory
    # --------------------------------------------------------------------------

    @property
    def segmenter(self) -> CanSegmenter:
        return self._segmenter

    @staticmethod
    def is_supported_bus_manager(bus_manager: Any) -> bool:
        # We do not rely on a bus_manager from python-can. So it must be None.
        return bus_manager is None

    # --------------------------------------------------------------------------
    # region Low-level: send_packet / receive_packet
    # --------------------------------------------------------------------------

    def send_packet(self, packet: CanPacket) -> CanPacketRecord:
        """
        Send one raw CAN Packet (Single Frame).
        Returns a CanPacketRecord with direction=TRANSMITTED.
        """
        if not self.device:
            self.logger.warning("No ICS device open; cannot send_packet().")

            # Build a fallback record:
            from can import Message
            dummy_frame = Message(arbitration_id=packet.can_id, data=packet.payload)
            return CanPacketRecord(
                frame=dummy_frame,
                direction=TransmissionDirection.TRANSMITTED,
                addressing_type=packet.addressing_type,
                addressing_format=packet.addressing_format,
                transmission_time=datetime.now()
            )

        # Build the ICS SpyMessage
        spy_msg = ics.SpyMessage()
        spy_msg.ArbIDOrHeader = packet.can_id
        spy_msg.NetworkID = self.network_id
        data_list = list(packet.payload)  # ICS expects a list or tuple
        spy_msg.NumberBytesData = len(data_list)
        spy_msg.Data = tuple(data_list)

        try:
            ics.transmit_messages(self.device, [spy_msg])
            self.logger.debug("Sent packet ID=0x%X Data=%r", packet.can_id, packet.payload)

            # Build python-can style "Message"
            from can import Message
            dummy_frame = Message(arbitration_id=packet.can_id, data=packet.payload)
            return CanPacketRecord(
                frame=dummy_frame,
                direction=TransmissionDirection.TRANSMITTED,
                addressing_type=packet.addressing_type,
                addressing_format=packet.addressing_format,
                transmission_time=datetime.now()
            )
        except Exception as e:
            self.logger.error("Failed to transmit CAN packet: %s", e)

            # Still return a record, but we log that send might have failed
            from can import Message
            dummy_frame = Message(arbitration_id=packet.can_id, data=packet.payload)
            return CanPacketRecord(
                frame=dummy_frame,
                direction=TransmissionDirection.TRANSMITTED,
                addressing_type=packet.addressing_type,
                addressing_format=packet.addressing_format,
                transmission_time=datetime.now()
            )

    async def async_send_packet(self, packet: CanPacket, loop=None) -> CanPacketRecord:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_packet, packet)

    def receive_packet(self, timeout: Optional[float] = None) -> CanPacketRecord:
        """
        Receives a single CanPacketRecord from the RX queue,
        or raises TimeoutError if none arrive within 'timeout' seconds.
        """
        to = timeout if timeout is not None else 1.0
        start_time = time.time()
        while time.time() - start_time < to:
            try:
                # The queue already stores a fully formed CanPacketRecord
                pkt_record = self._rx_queue.get_nowait()
                self.logger.debug("Returning queued packet ArbID=0x%X", pkt_record.can_id)
                return pkt_record
            except Empty:
                time.sleep(0.01)

        raise TimeoutError("Timeout waiting for a CAN packet in ICS transport.")

    async def async_receive_packet(self, timeout: Optional[float] = None, loop=None) -> CanPacketRecord:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.receive_packet, timeout)

    # --------------------------------------------------------------------------
    # region Higher-level: send_message / receive_message
    # --------------------------------------------------------------------------

    def send_message(self, message) -> UdsMessageRecord:
        """
        Send a multi-byte UDS message. If 'enable_hw_iso_tp' is True,
        tries ICS hardware iso15765_transmit_message. Otherwise fallback single-frame.
        """
        if not self.device:
            raise RuntimeError("send_message() failed; ICS device not open.")

        raw_payload = bytes(message.payload)

        # 1) Attempt ICS hardware ISO-TP if requested
        if self.enable_hw_iso_tp and hasattr(ics, "iso15765_transmit_message"):
            try:
                # ICS wants a large buffer
                DataArrayType = ctypes.c_ubyte * 4096
                iso_data = DataArrayType()
                for i, val in enumerate(raw_payload):
                    iso_data[i] = val

                tx_msg = ics.st_cm_iso157652_tx_message.st_cm_iso157652_tx_message()
                tx_msg.id = self.hw_iso_tp_tx_id
                tx_msg.vs_netid = self.network_id
                tx_msg.num_bytes = len(raw_payload)
                tx_msg.padding = 0xAA
                tx_msg.fc_id = self.hw_iso_tp_rx_id
                tx_msg.fc_id_mask = 0xFFF
                tx_msg.flowControlExtendedAddress = 0
                tx_msg.fs_timeout = 0x10
                tx_msg.fs_wait = 0x3000
                tx_msg.blockSize = 0
                tx_msg.stMin = 0
                tx_msg.paddingEnable = 1
                tx_msg.data = iso_data

                ics.iso15765_transmit_message(self.device, self.network_id, tx_msg, 3000)
                self.logger.info("HW ISO-TP transmit success.")
                # Return a UdsMessageRecord with your message
                return UdsMessageRecord(message)

            except Exception as e:
                self.logger.warning("HW ISO-TP transmit failed; fallback single-frame. Error=%s", e)

        # 2) Fallback single-frame if >7 bytes => truncated
        if len(raw_payload) > 7:
            self.logger.warning("Message payload >7 bytes; fallback single-frame truncated to first 7.")
            raw_payload = raw_payload[:7]

        # Construct a single-frame
        from uds.packet.can.can_packet import CanPacket
        fallback_pkt = CanPacket(
            packet_type=CanPacketType.SINGLE_FRAME,
            addressing_format=CanAddressingFormat.NORMAL_ADDRESSING,
            addressing_type=AddressingType.PHYSICAL,
            can_id=0x7E0,
            dlc=8,
            payload=list(raw_payload)
        )
        # Send that single frame
        self.send_packet(fallback_pkt)

        # Build a UdsMessageRecord to return
        return UdsMessageRecord(message)

    async def async_send_message(self, message, loop=None) -> UdsMessageRecord:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_message, message)

    def receive_message(self, timeout: Optional[float] = None) -> UdsMessageRecord:
        """
        Tries ICS iso15765_receive_message if enable_hw_iso_tp is True,
        or fallback to reading single frames from the queue.
        """
        if not self.device:
            raise TimeoutError("receive_message() failed; ICS device not open.")

        if self.enable_hw_iso_tp and hasattr(ics, 'iso15765_receive_message'):
            try:
                rx_msg = ics.st_cm_iso157652_rx_message.st_cm_iso157652_rx_message()
                rx_msg.id = self.hw_iso_tp_tx_id
                rx_msg.vs_netid = self.network_id
                rx_msg.padding = 0xAA
                rx_msg.id_mask = 0xFFF
                rx_msg.fc_id = self.hw_iso_tp_rx_id
                rx_msg.blockSize = 100
                rx_msg.stMin = 10
                rx_msg.cf_timeout = 1000
                rx_msg.enableFlowControlTransmission = 1
                rx_msg.paddingEnable = 1

                ics.iso15765_receive_message(self.device, self.network_id, rx_msg)
                time.sleep(0.5)  # ICS blocking approach

                msgs, err_count = ics.get_messages(self.device)
                if msgs:
                    # combine them
                    full_payload = b''.join(bytes(m.Data) for m in msgs)
                    self.logger.info("HW ISO-TP received message len=%d", len(full_payload))
                    return UdsMessageRecord(full_payload)
                else:
                    raise TimeoutError("No HW ISO-TP message received.")
            except Exception as e:
                self.logger.warning("HW ISO-TP receive failed; fallback to normal frames. %s", e)

        # 2) fallback approach
        rec_packet = self.receive_packet(timeout=timeout)
        # `rec_packet` is a CanPacketRecord with .raw_frame_data
        # We'll just assume it's single-frame for the fallback
        self.logger.info("Fallback single-frame read, data len=%d", len(rec_packet.raw_frame_data))
        return UdsMessageRecord(payload=rec_packet.raw_frame_data)

    async def async_receive_message(self, timeout: Optional[float] = None, loop=None) -> UdsMessageRecord:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.receive_message, timeout)

    # --------------------------------------------------------------------------
    # region ICS device handling
    # --------------------------------------------------------------------------

    def _configure_and_open_device(self, existing_device=None):
        try:
            if existing_device is None:
                devs = ics.find_devices()
                if not devs:
                    raise RuntimeError("No ICS devices found.")
                self.device = devs[0]
            else:
                self.device = existing_device

            # attempt close
            try:
                ics.close_device(self.device)
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Error closing device before open: {e}")

            self.logger.debug(f"Using ICS device: {self.device}")
            try:
                ics.open_device(self.device)
                self.logger.debug("ICS device open success.")
            except ics.ics.RuntimeError as e:
                self.logger.warning(f"open_device() error: {e}")

            # Query device info
            from uds.utilities.ics_device_interrogation import dump_device_info
            try:
                dev_info = dump_device_info(self.device)
                self.logger.info("Device Info:\n%s", dev_info)
            except Exception as e:
                self.logger.error("Error during device interrogation: %s", e)

            # Set bit rate
            try:
                ics.set_bit_rate(self.device, self.baudrate, self.network_id)
                time.sleep(0.3)
            except Exception as e:
                self.logger.error(f"set_bit_rate() failed: {e}")
                errs = ics.get_error_messages(self.device)
                self.logger.error(f"ICS Device Errors: {errs}")
                raise

           
            # If hardware ISO-TP is wanted, enable
            if self.enable_hw_iso_tp and hasattr(ics, "iso15765_enable_networks"):
                ics.iso15765_enable_networks(self.device, self.network_id)
                time.sleep(0.3)
                self.logger.debug("Hardware ISO-TP enabled on net %d", self.network_id)
                
             # go_online
            if hasattr(ics, "go_online"):
                ics.go_online(self.device)
            else:
                self.logger.debug("No go_online method found; skipping.") 
                self.enable_network_com()       

        except Exception as e:
            self.logger.error("Failed to configure/open ICS device: %s", e)
            self.device = None
            
    def enable_network_com(self, *args, **kwargs):
        """Enable network communication."""
        return ics.enable_network_com(self.device, *args, **kwargs)
    
    
    
    def close(self):
        self.logger.debug("Shutting down ICS transport.")
        self._rx_stop.set()
        self._rx_thread.join(timeout=1.0)

        if self.device:
            try:
                if hasattr(ics, 'close_device'):
                    ics.close_device(self.device)
                    self.logger.debug("ICS device closed successfully.")
            except Exception as e:
                self.logger.warning("Error closing ICS device: %s", e)
        self.logger.info("IcsTransportInterface closed.")

    # --------------------------------------------------------------------------
    # region RX thread loop
    # --------------------------------------------------------------------------

    def _rx_loop(self):
        self.logger.debug("RX thread started.")
        while not self._rx_stop.is_set():
            if not self.device:
                time.sleep(0.05)
                continue

            try:
                msgs, error_count = ics.get_messages(self.device)
                if msgs:
                    for m in msgs:
                        pkt_record = self._convert_spy_to_can_packet(m)
                        if pkt_record is not None:
                            self._rx_queue.put(pkt_record)

                if error_count > 0:
                    errs = ics.get_error_messages(self.device)
                    for em in errs:
                        self.logger.warning("ICS error: %s", em)

                if (self.periodic_status_interval > 0
                        and (time.time() - self._last_status_time) > self.periodic_status_interval):
                    self._check_and_log_status()
                    self._last_status_time = time.time()

                time.sleep(0.01)
            except ics.ics.RuntimeError as e:
                self.logger.error("ICS runtime error in RX loop: %s", e)
                if self.reinit_on_error:
                    self.logger.info("Reinit after ICS error in rx_loop.")
                    time.sleep(1.0)
                    self._configure_and_open_device(existing_device=self.device)
            except Exception as e:
                self.logger.error("Unknown error in RX loop: %s", e)
                time.sleep(0.1)

        self.logger.debug("RX thread exiting...")

    def _check_and_log_status(self):
        try:
            if hasattr(ics, 'get_device_status'):
                st = ics.get_device_status(self.device)
                self.logger.info("Periodic ICS status: %s", st)
            if hasattr(ics, 'get_error_messages'):
                errs = ics.get_error_messages(self.device)
                for em in errs:
                    self.logger.warning("Periodic ICS error: %s", em)
        except Exception as e:
            self.logger.error("check_and_log_status error: %s", e)

    # --------------------------------------------------------------------------
    # region Helpers
    # --------------------------------------------------------------------------

    def _convert_spy_to_can_packet(self, spy_msg):
        """
        Convert an ics.SpyMessage -> a CanPacketRecord with direction=RX.
        If invalid or not UDS-related, returns None.
        """
        try:
            raw_bytes = bytes(spy_msg.Data)
            self.logger.debug(
                "SpyMessage received: ArbID=0x%X, NetID=%s, Data=%s",
                spy_msg.ArbIDOrHeader, spy_msg.NetworkID, raw_bytes.hex()
            )
        except Exception as log_e:
            self.logger.error("Failed to log spy message: %s", log_e)
            return None

        # Ignore TX loopback
        if spy_msg.StatusBitField & ics.SPY_STATUS_TX_MSG:
            return None

        raw_data = tuple(spy_msg.Data)
        if not raw_data:
            return None

        nibble = (raw_data[0] >> 4) & 0xF
        do_log = (self._log_count < self.MAX_LOG_COUNT)

        if nibble == 0:   # Single-frame
            sf_dl = raw_data[0] & 0xF
            if sf_dl > 7:
                if do_log:
                    self.logger.debug("Skipping invalid SF with sf_dl=%d (raw=%s)", sf_dl, raw_data)
                self._increment_log_count()
                return None
            ptype = CanPacketType.SINGLE_FRAME
        elif nibble == 1:
            ptype = CanPacketType.FIRST_FRAME
        elif nibble == 2:
            ptype = CanPacketType.CONSECUTIVE_FRAME
        elif nibble == 3:
            ptype = CanPacketType.FLOW_CONTROL
        else:
            if do_log:
                self.logger.debug("Skipping non-UDS nibble=0x%X data=%s", nibble, raw_data)
            self._increment_log_count()
            return None

        # create python-can style "Message" for logging
        from can import Message
        dummy_frame = Message(arbitration_id=spy_msg.ArbIDOrHeader, data=raw_data)

        try:
            record = CanPacketRecord(
                frame=dummy_frame,
                direction=TransmissionDirection.RECEIVED,
                addressing_type=AddressingType.PHYSICAL,
                addressing_format=CanAddressingFormat.NORMAL_ADDRESSING,
                transmission_time=datetime.now()
            )
            return record
        except Exception as e:
            if do_log:
                self.logger.error(
                    "Failed building CanPacketRecord: %s. nibble=0x%X data=%s", e, nibble, raw_data
                )
            self._increment_log_count()
            return None

    def _increment_log_count(self):
        self._log_count += 1
        if self._log_count == self.MAX_LOG_COUNT:
            self.logger.info(f"Hit log limit of {self.MAX_LOG_COUNT}; further logs suppressed.")
