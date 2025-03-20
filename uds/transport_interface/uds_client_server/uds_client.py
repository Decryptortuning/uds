#!/usr/bin/env python
import logging
import time
import threading

try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

import ics
from uds.transport_interface.can.ics_transport_interface import IcsTransportInterface
from uds.can import CanAddressingInformation, CanAddressingFormat
from uds.can.flow_control import DefaultFlowControlParametersGenerator
from uds.message import UdsMessage
from uds.transmission_attributes import AddressingType


class UdsClient:
    """
    A UDS Client that can use either python-ics (IcsTransportInterface) or python-can.
    """

    def __init__(
        self,
        transport: IcsTransportInterface = None,
        transport_type: str = "ics",
        ics_baudrate: int = 500000,
        ics_network_id=None,
        enable_hw_iso_tp: bool = False,
    ):
        """
        :param transport: Optional external IcsTransportInterface instance.
        :param transport_type: 'ics' or 'neovi'.
        :param ics_baudrate: ICS device CAN baudrate.
        :param ics_network_id: ICS.NETID_HSCAN, ICS.NETID_HSCAN2, etc.
        :param enable_hw_iso_tp: If True, use hardware ISO-TP on ICS.
        """

        self.network_id = ics_network_id if ics_network_id is not None else ics.NETID_HSCAN
        self.tx_id = 0x7E0
        self.rx_id = 0x7E8

        # Basic addressing info
        self.addressing_info = CanAddressingInformation(
            addressing_format=CanAddressingFormat.NORMAL_ADDRESSING,
            tx_physical={"can_id": self.tx_id},
            rx_physical={"can_id": self.rx_id},
            tx_functional={"can_id": 0x7DF},
            rx_functional={"can_id": 0x7EF}
        )

        # Flow Control
        self.flow_control_gen = DefaultFlowControlParametersGenerator(
            block_size=0,
            st_min=0
        )

        # If transport not provided, create a new ICS Transport
        if transport:
            self.transport = transport
            logging.info("Using externally provided ICS transport interface.")
        else:
            if transport_type == "ics":
                self._init_ics_transport(
                    baudrate=ics_baudrate,
                    network_id=self.network_id,
                    hw_iso_tp=enable_hw_iso_tp
                )
            else:
                raise ValueError("Unsupported transport type. Use 'ics'.")

        logging.info(
            f"UDS Client initialized with TX=0x{self.tx_id:X}, RX=0x{self.rx_id:X}, "
            f"transport='{transport_type}', hw_iso_tp={enable_hw_iso_tp}"
        )

    def _init_ics_transport(self, baudrate, network_id, hw_iso_tp):
        self.transport = IcsTransportInterface(
            device=None,
            baudrate=baudrate,
            network_id=network_id,
            enable_hw_iso_tp=hw_iso_tp,
            addressing_information=self.addressing_info
        )
        logging.debug(
            "Initialized ICS Transport at %d bps, NetID=%s, HW_ISO_TP=%s",
            baudrate, network_id, hw_iso_tp
        )

    def send_request(self, service_id: int, data: bytes, timeout=2.0):
        """
        Sends a UDS request at 0x7E0, waits for response from 0x7E8, up to 'timeout'.
        """
        payload = [service_id] + list(data)
        request = UdsMessage(payload, AddressingType.PHYSICAL)

        logging.info(f"Sending UDS Request: {request}")
        try:
            self.transport.send_message(request)
        except RuntimeError as e:
            # Device was not open
            logging.error(f"send_message() device not open: {e}")
            return None
        except TimeoutError:
            logging.warning("No ACK observed (TimeoutError). Continuing anyway...")
            return None
        except Exception as e:
            logging.exception("Error sending UDS request:")
            return None

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response_record = self.transport.receive_message(timeout=0.1)
                if response_record:
                    if response_record.payload and response_record.payload[0] == 0x7F:
                        # Negative Response
                        if len(response_record.payload) >= 3:
                            nrc = response_record.payload[2]
                            logging.error(f"Negative response NRC=0x{nrc:02X}")
                        else:
                            logging.error("Negative response but no NRC byte.")
                        return None

                    logging.info(f"Positive response: {response_record}")
                    return response_record
            except TimeoutError:
                logging.debug("Waiting for response (TimeoutError). Retrying...")
            except Exception as e:
                logging.exception("Error receiving UDS response:")
                return None

        logging.warning("No response received (timeout).")
        return None

    def enter_session(self, session_type: int):
        """Send a 0x10 request for session_type (0x01 Default, 0x03 Extended, etc.)."""
        return self.send_request(0x10, bytes([session_type]))

    def read_data_by_identifier(self, did: int):
        """Send 0x22 to read the specified DID."""
        resp = self.send_request(0x22, did.to_bytes(2, 'big'))
        if resp and len(resp.payload) > 3:
            return resp.payload[3:]
        return None

    def tester_present(self, subfunction: int = 0x00):
        """Sends 0x3E (Tester Present)."""
        return self.send_request(0x3E, bytes([subfunction]))

    def reset_ecu(self, reset_type: int = 0x01):
        """Sends 0x11 (ECU Reset)."""
        return self.send_request(0x11, bytes([reset_type]))

    def close(self):
        """
        Close ICS transport if used.
        """
        if getattr(self, "transport", None):
            try:
                self.transport.close()
                logging.debug("ICS transport closed successfully.")
            except Exception as e:
                logging.warning("Error closing ICS transport: %s", e)

        logging.info("UDS Client shut down.")
