# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .session_history_service import (
        SessionHistoryService,
        InMemorySessionHistoryService,
    )
    from .redis_session_history_service import RedisSessionHistoryService
    from .tablestore_session_history_service import (
        TablestoreSessionHistoryService,
    )
    from .session_history_service_factory import SessionHistoryServiceFactory

install_lazy_loader(
    globals(),
    {
        "SessionHistoryService": ".session_history_service",
        "InMemorySessionHistoryService": ".session_history_service",
        "RedisSessionHistoryService": ".redis_session_history_service",
        "TablestoreSessionHistoryService": ".tablestore_session_history_service",  # noqa
        "SessionHistoryServiceFactory": ".session_history_service_factory",
    },
)
