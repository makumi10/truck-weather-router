class PlanningError(Exception):
    """A problem we can explain to the user (bad location, upstream outage...)."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status
