"""Translation for TransferData (SID 0x36) service."""

__all__ = ["TRANSFER_DATA"]

from uds.message import NRC, RequestSID

from ..data_record_definitions import BLOCK_SEQUENCE_COUNTER, TRANSFER_REQUEST_PARAMETER, TRANSFER_RESPONSE_PARAMETER
from ..service import Service

TRANSFER_DATA = Service(request_sid=RequestSID.TransferData,
                        request_structure=(BLOCK_SEQUENCE_COUNTER,
                                           TRANSFER_REQUEST_PARAMETER),
                        response_structure=(BLOCK_SEQUENCE_COUNTER,
                                            TRANSFER_RESPONSE_PARAMETER),
                        supported_nrc=(
                            NRC.IncorrectMessageLengthOrInvalidFormat,
                            NRC.RequestSequenceError,
                            NRC.RequestOutOfRange,
                            NRC.TransferDataSuspended,
                            NRC.GeneralProgrammingFailure,
                            NRC.WrongBlockSequenceCounter,
                        ))
"""Default translator for :ref:`TransferData <knowledge-base-service-transfer-data>` service."""
