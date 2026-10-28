class RabbitMQClientError(RuntimeError):
    """RabbitMQ metrics could not be collected."""


class RailwayClientError(RuntimeError):
    """Base error for Railway transport and GraphQL failures."""


class RailwayTransportError(RailwayClientError):
    """The request could not be completed or returned a non-GraphQL response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class RailwayGraphQLError(RailwayClientError):
    """Railway returned a GraphQL ``errors`` array."""

    def __init__(self, message: str, *, code: str | None = None, trace_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.trace_id = trace_id
