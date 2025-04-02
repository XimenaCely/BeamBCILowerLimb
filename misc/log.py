import logging
from logging import DEBUG, ERROR, INFO, WARNING
from typing import cast, Optional

from colorama import Fore, Style, init

from misc.timing import clock

# Define custom log level
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

LOGGER_BASENAME = "BeamBCI"

# Initialize colorama
init(autoreset=True)

# Defines in which color the log levels should be displayed
LogColors = {
    DEBUG: Fore.BLACK,
    INFO: Fore.BLUE,
    SUCCESS: Fore.GREEN,
    WARNING: Fore.YELLOW,
    ERROR: Fore.RED,
}

LogHexColors = {
    DEBUG: "#000000",
    SUCCESS: "#3BB273",
    INFO: "#000000",
    WARNING: "#E1BC29",
    ERROR: "#E15554"
}


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        log_color = LogColors.get(record.levelno, Fore.BLACK)
        levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        record.levelname = levelname
        return super().format(record)


class BeamBciLogHandler(logging.StreamHandler):
    # This is a custom StreamHandler which collects the LogRecords coming from all instances
    # For proper display of the time in which a log arrived it needs to know a starting time (supplied by MainProgram)
    def __init__(self, start_clock):
        super().__init__()
        self.start_clock = start_clock
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        # Receives a LogRecord, adds a time (how long pythonbci has been running (in [s])) and appends it to the records
        record.time = clock() - self.start_clock
        self.records.append(record)
        super().emit(record)

    def get_records(self):
        # Returns the list of new records since last query
        records = self.records.copy()
        self.records = []
        return records

class BeamBciLogger(logging.Logger):

    # Add a method to log at the SUCCESS level
    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, message, args, **kwargs)



def initialize_logger(start_clock, level=logging.DEBUG) -> Optional[BeamBciLogHandler]:
    # Configure a logger instance which can be found by all modules
    # It is started with the base name, each module should create its own subname
   
    if logging.getLoggerClass() is BeamBciLogger:
        logger = logging.getLogger(LOGGER_BASENAME)
        handlers = logger.handlers
        for handler in handlers:
            if isinstance(handler, BeamBciLogHandler):
                return handler
        raise Exception("Log Handler is missing!!")

    logging.setLoggerClass(BeamBciLogger)
    logger = logging.getLogger(LOGGER_BASENAME)
    logger.setLevel(level=level)

    # Add our StreamHandler which collects the log messages for display in the GUI
    pbciLogHandler = BeamBciLogHandler(start_clock=start_clock)
    pbciLogHandler.setLevel(level)
    pbciLogHandler.setFormatter(
        ColoredFormatter(
            "%(asctime)s %(name)s - %(levelname)s: %(funcName)s - %(message)s"
        )
    )
    logger.addHandler(pbciLogHandler)

    return pbciLogHandler


def getLogger(name) -> BeamBciLogger:
    if logging.getLoggerClass() is not BeamBciLogger:
        initialize_logger(clock())
    return cast(BeamBciLogger, logging.getLogger(f"{LOGGER_BASENAME}.{name}"))
