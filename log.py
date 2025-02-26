import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger_chan = logging.StreamHandler()
logger_chan.setLevel(logging.INFO)
logger_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s](%(name)s:%(lineno)d) %(message)s"
)
logger_chan.setFormatter(logger_formatter)
logger.addHandler(logger_chan)
