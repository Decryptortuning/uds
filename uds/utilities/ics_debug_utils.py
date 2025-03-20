"""
ics_debug_utils.py

Utility functions to provide enhanced debugging for ICS devices.
Includes functions to log performance parameters, status, and bus voltage if available.
"""

import logging
try:
    import ics
except ImportError:
    ics = None

def log_device_status(device):
    logger = logging.getLogger(__name__)
    try:
        if hasattr(ics, 'get_device_status'):
            status = ics.get_device_status(device)
            logger.info("ICS Device Status: %s", status)
        else:
            logger.warning("get_device_status not available in python-ics.")
    except Exception as e:
        logger.error("Failed to retrieve device status: %s", e)

def log_error_messages(device):
    logger = logging.getLogger(__name__)
    try:
        if hasattr(ics, 'get_error_messages'):
            errors = ics.get_error_messages(device)
            if errors:
                for error in errors:
                    logger.warning("ICS Error: %s", error)
            else:
                logger.info("No ICS errors reported.")
        else:
            logger.warning("get_error_messages not available in python-ics.")
    except Exception as e:
        logger.error("Failed to retrieve error messages: %s", e)

def log_performance_parameters(device):
    logger = logging.getLogger(__name__)
    try:
        if hasattr(ics, 'get_performance_parameters'):
            params = ics.get_performance_parameters(device)
            logger.info("Performance Parameters: %s", params)
        else:
            logger.warning("get_performance_parameters not available in python-ics.")
    except Exception as e:
        logger.error("Failed to retrieve performance parameters: %s", e)

def log_bus_voltage(device):
    logger = logging.getLogger(__name__)
    try:
        if hasattr(ics, 'get_bus_voltage'):
            voltage = ics.get_bus_voltage(device, reserved=0)
            logger.info("Bus Voltage: %d mV", voltage)
        else:
            logger.warning("get_bus_voltage not available in python-ics.")
    except Exception as e:
        logger.error("Failed to retrieve bus voltage: %s", e)
