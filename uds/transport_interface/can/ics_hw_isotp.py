"""
ics_hw_isotp.py

Helper for ICS hardware-based ISO-15765 functionalities.
"""

import logging
import ics

def enable_iso_tp(device, net_id, tx_id, rx_id, extended=False):
    # call ics.iso15765_enable_networks, etc.
    pass

def send_hw_isotp(device, net_id, data, tx_id, rx_id):
    # call ics.iso15765_transmit_message
    pass

def receive_hw_isotp(device, net_id, timeout=1.0):
    # poll ics.iso15765_receive_message or similar 
    pass
