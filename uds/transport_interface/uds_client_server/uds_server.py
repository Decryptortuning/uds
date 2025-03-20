import logging
import threading
import can
from uds.transport_interface import PyCanTransportInterface
from uds.can import CanAddressingInformation, CanAddressingFormat
from uds.message import UdsMessage

class UdsServer:
    """
    Simulated UDS ECU that listens for physically addressed requests and responds.
    """

    def __init__(self, can_interface='neovi', ecu_address=0x7E0):
        """
        Initializes the UDS server with a fixed physical address.

        :param can_interface: The CAN interface.
        :param ecu_address: The ECU's physical request ID.
        """
        self.tx_physical_id = ecu_address + 8  # Response ID = Request ID + 8
        self.rx_physical_id = ecu_address  # Listen for requests on this ID

        # Initialize CAN Bus
        self.bus = can.Bus(interface=can_interface, channel=1, bitrate=500000, receive_own_messages=True)

        # Configure UDS Transport
        addressing_info = CanAddressingInformation(
            addressing_format=CanAddressingFormat.NORMAL_ADDRESSING,
            tx_physical={"can_id": self.tx_physical_id},
            rx_physical={"can_id": self.rx_physical_id},
            tx_functional={"can_id": 0x7DF},
            rx_functional={"can_id": self.rx_physical_id}
        )

        self.transport = PyCanTransportInterface(can_bus_manager=self.bus, addressing_information=addressing_info)
        self.running = True
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()

        logging.info(f"UDS Server started on ECU Address: 0x{self.rx_physical_id:X}")

    def listen(self):
        """Listens for incoming UDS requests and responds."""
        while self.running:
            msg = self.bus.recv()
            if msg and msg.arbitration_id == self.rx_physical_id:
                response = self.handle_request(msg.data)
                if response:
                    self.send_response(response)

    def handle_request(self, data):
        """Processes UDS requests and returns responses."""
        service_id = data[0]

        if service_id == 0x10:  # Diagnostic Session Control
            return bytes([0x50, data[1]])  # Positive Response

        elif service_id == 0x22:  # ReadDataByIdentifier
            did = int.from_bytes(data[1:3], 'big')
            return bytes([0x62]) + data[1:3] + b"TEST_DATA"  # Example data

        return bytes([0x7F, service_id, 0x11])  # Service Not Supported

    def send_response(self, response):
        """Sends a response to the tester."""
        msg = can.Message(arbitration_id=self.tx_physical_id, data=response, is_extended_id=False)
        self.bus.send(msg)

    def stop(self):
        """Stops the server."""
        self.running = False
        self.thread.join()
        self.bus.shutdown()
