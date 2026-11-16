import structlog


def configure_logging(log_level: str) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level, #Adds "level": "info" (or "warning", "error", etc.) to the event dict
            structlog.processors.TimeStamper(fmt="iso", utc=True), #Adds a "timestamp" key
            structlog.dev.ConsoleRenderer(), #Renders the event dict as a human-readable string for console output
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )
