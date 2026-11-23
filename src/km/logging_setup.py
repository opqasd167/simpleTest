import logging


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Third-party libraries are noisy at INFO
    for noisy in ("httpx", "chromadb", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
