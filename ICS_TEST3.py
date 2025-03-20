#!/usr/bin/env python
import time
import logging
import threading

# If you installed colorlog, uncomment this import:
import colorlog

# ICS library
import ics

# Our refactored ICS TransportInterface (with single-frame fallback)
from uds.transport_interface.can.ics_transport_interface import IcsTransportInterface

# Our UdsClient code
from uds.transport_interface.uds_client_server.uds_client import UdsClient


def configure_color_logging(level=logging.DEBUG):
    """
    Configure colorized logging via colorlog.
    Call this before using logging in your script.
    """
    # Create a console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Define a colorlog formatter
    formatter = colorlog.ColoredFormatter(
        fmt=(
            "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s "
            "%(white)s%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    )
    handler.setFormatter(formatter)

    # Get root logger and set level
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove any existing handlers if needed
    logger.handlers.clear()
    logger.addHandler(handler)

    # Example test message
    logging.debug("Color log configured with level=%s", logging.getLevelName(level))


def send_tester_present(client, interval=2.0, stop_event=None):
    """Periodically sends Tester Present (0x3E)."""
    while not (stop_event and stop_event.is_set()):
        logging.debug("Sending Tester Present (0x3E).")
        client.tester_present()
        time.sleep(interval)


def main():
    # 1) Configure color logging at DEBUG level
    configure_color_logging(level=logging.DEBUG)

    # 2) Optionally reduce ICS logs if you want fewer messages from python-ics:
    # logging.getLogger('ics').setLevel(logging.WARNING)

    logging.debug("Initializing ICS-based UDS Client...")

    client = None
    tester_present_thread = None
    stop_tester_present_evt = threading.Event()

    try:
        # Create the UdsClient that uses IcsTransportInterface (HW ISO-TP + fallback)
        client = UdsClient(
            transport_type='ics',
            ics_baudrate=500000,
            ics_network_id=ics.NETID_HSCAN,
            enable_hw_iso_tp=True
        )
        logging.info("UDS Client initialized successfully via ICS.")

        # 3) Enter Extended Diagnostic Session
        logging.info("Requesting Extended Diagnostic Session (0x10, Subfunction 0x03)...")
        session_resp = client.enter_session(0x03)
        if not session_resp:
            logging.warning("Failed or no response to enter_extended_diagnostic_session")

        # 4) Start Tester Present keep-alive in the background
        tester_present_thread = threading.Thread(
            target=send_tester_present,
            args=(client, 1.5, stop_tester_present_evt),
            daemon=True
        )
        tester_present_thread.start()

        # 5) Example: Read Memory By Address
        logging.info("Attempting ReadMemoryByAddress(0x23)...")
        readmem_resp = client.send_request(0x23, bytes([0x41, 0x00, 0x01, 0x00, 0x10]))  # example
        if readmem_resp:
            logging.debug(f"ReadMemory response payload: {readmem_resp.payload}")
        else:
            logging.warning("No valid response to ReadMemoryByAddress")

        # 6) Example: Read VIN
        logging.info("Reading VIN (DID 0xF190)...")
        vin_data = client.read_data_by_identifier(0xF190)
        if vin_data:
            try:
                vin_str = vin_data.decode('ascii')
                logging.info(f"VIN: {vin_str}")
            except UnicodeDecodeError:
                logging.warning(f"VIN data is not ASCII decodable: {vin_data}")
        else:
            logging.warning("Failed to read VIN or no response.")

        # 7) ECU Reset
        logging.info("Requesting ECU Reset (service 0x11, sub 0x01)...")
        reset_resp = client.reset_ecu(0x01)
        if reset_resp:
            logging.info(f"ECU reset response: {reset_resp.payload}")
        else:
            logging.warning("No response to ECU reset")

        logging.info("Demo complete, pausing briefly...")
        time.sleep(3.0)

    except Exception as e:
        logging.exception("An unexpected error occurred in main:")
    finally:
        logging.debug("Cleaning up resources...")

        # Stop keep-alive thread
        if tester_present_thread and tester_present_thread.is_alive():
            stop_tester_present_evt.set()
            tester_present_thread.join(timeout=5.0)

        if client:
            client.close()

        logging.debug("Cleanup complete.")


if __name__ == '__main__':
    main()
