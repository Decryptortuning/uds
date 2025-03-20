"""
ics_device_interrogation.py

Provides functions to interrogate an ICS device: retrieve settings, firmware info,
status, error messages, and other configuration details for enhanced debugging.
"""

import logging
try:
    import ics
except ImportError:
    ics = None

def dump_device_info(device) -> str:
    """
    Interrogate the ICS device and return a string summary of its settings, firmware,
    and status.
    """
    logger = logging.getLogger(__name__)
    info_lines = []
    try:
        info_lines.append(f"Device: {device}")
        serial = getattr(device, 'SerialNumber', 'N/A')
        info_lines.append(f"Serial Number: {serial}")
        if hasattr(ics, 'get_dll_version'):
            dll_ver = ics.get_dll_version()
            info_lines.append(f"ICS DLL Version: {dll_ver}")
        else:
            info_lines.append("ICS DLL Version: Not available")
        if hasattr(ics, 'get_hw_firmware_info'):
            fw_info = ics.get_hw_firmware_info(device)
            info_lines.append(f"Firmware Info: {fw_info}")
        else:
            info_lines.append("Firmware Info: Not available")
        if hasattr(ics, 'get_device_settings'):
            settings = ics.get_device_settings(device)
            info_lines.append("Device Settings:")
            info_lines.append(str(settings))
        else:
            info_lines.append("Device Settings: Not available")
        if hasattr(ics, 'get_device_status'):
            status = ics.get_device_status(device)
            info_lines.append("Device Status:")
            info_lines.append(str(status))
        else:
            info_lines.append("Device Status: Not available")
        if hasattr(ics, 'get_error_messages'):
            errors = ics.get_error_messages(device)
            if errors:
                info_lines.append("Error Messages:")
                for error in errors:
                    info_lines.append(str(error))
            else:
                info_lines.append("Error Messages: None")
        else:
            info_lines.append("Error Messages: Not available")
    except Exception as e:
        logger.error("Error during device interrogation: %s", e)
        info_lines.append(f"Error: {e}")
    return "\n".join(info_lines)
