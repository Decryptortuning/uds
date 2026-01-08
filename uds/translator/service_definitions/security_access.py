"""Translation for SecurityAccess (SID 0x27) service."""

__all__ = ["SECURITY_ACCESS"]

from uds.message import NRC, RequestSID

from ..data_record_definitions import (
    CONDITIONAL_SECURITY_ACCESS_REQUEST,
    CONDITIONAL_SECURITY_ACCESS_RESPONSE,
    SECURITY_ACCESS_SUB_FUNCTION,
)
from ..service import Service

SECURITY_ACCESS = Service(
    request_sid=RequestSID.SecurityAccess,
    request_structure=(SECURITY_ACCESS_SUB_FUNCTION, CONDITIONAL_SECURITY_ACCESS_REQUEST),
    response_structure=(SECURITY_ACCESS_SUB_FUNCTION, CONDITIONAL_SECURITY_ACCESS_RESPONSE),
    supported_nrc=(
        NRC.SubFunctionNotSupported,
        NRC.IncorrectMessageLengthOrInvalidFormat,
        NRC.ConditionsNotCorrect,
        NRC.RequestSequenceError,
        NRC.RequestOutOfRange,
        NRC.InvalidKey,
        NRC.ExceedNumberOfAttempts,
        NRC.RequiredTimeDelayNotExpired,
        NRC.SubFunctionNotSupportedInActiveSession,
        NRC.ServiceNotSupportedInActiveSession,
    ))
"""Default translator for :ref:`SECURITY_ACCESS <knowledge-base-service-security-access>` service."""
