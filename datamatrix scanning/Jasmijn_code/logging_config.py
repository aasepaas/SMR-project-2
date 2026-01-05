# -*- coding: utf-8 -*-
from datetime import datetime
import logging
import os
import matplotlib


def init_environment(backend: str = "Agg") -> None:
    """Set process-wide environment and matplotlib backend.

    - Sets `OPENCV_LOG_LEVEL` to SILENT to reduce OpenCV console noise.
    - Sets the matplotlib backend (default 'Agg') to avoid GUI requirements
      when running headless or in environments without a display.
    - Ensures matplotlib's logger is reduced to WARNING level.
    """
    try:
        os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
    except Exception:
        pass
    try:
        matplotlib.use(backend)
    except Exception:
        # In some environments the backend may already be set; ignore errors
        pass
    # Reduce matplotlib debug chatter
    logging.getLogger('matplotlib').setLevel(logging.WARNING)

# --- Custom loglevels ---
PROCESS_LEVEL_NUM_APPROVED = 15
logging.addLevelName(PROCESS_LEVEL_NUM_APPROVED, "approved")

def approved(self, message, *args, **kwargs):
    if self.isEnabledFor(PROCESS_LEVEL_NUM_APPROVED):
        self._log(PROCESS_LEVEL_NUM_APPROVED, message, args, **kwargs)

logging.Logger.approved = approved # type: ignore

PROCESS_LEVEL_NUM_DENIED = 25
logging.addLevelName(PROCESS_LEVEL_NUM_DENIED, "denied")

def denied(self, message, *args, **kwargs):
    if self.isEnabledFor(PROCESS_LEVEL_NUM_DENIED):
        self._log(PROCESS_LEVEL_NUM_DENIED, message, args, **kwargs)
logging.Logger.denied = denied # type: ignore


# --- Custom Formatter ---
class CustomFormatter(logging.Formatter):
    reset               = "\033[0m"
    bold                = "\033[1m"
    back_ground_red     = "\033[41m"
    back_ground_green   = "\033[42m"
    back_ground_yellow  = "\033[43m"
    back_ground_blue    = "\033[44m"

    red         = "\033[31m"
    green       = "\033[32m"
    yellow      = "\033[33m"
    blue        = "\033[34m"
    magenta     = "\033[35m"
    cyan        = "\033[36m"
    light_gray  = "\033[37m"
    dark_gray   = "\033[90m"
    light_red   = "\033[91m"
    light_green = "\033[92m"
    light_yellow= "\033[93m"
    light_blue  = "\033[94m"
    orange      = "\033[38;5;208m"

    # log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_format = "%(asctime)s - %(message)s"
    log_format_time = "%(asctime)s"
    log_format_data = " - %(message)s"

    FORMATS = {
        logging.DEBUG: magenta + log_format + reset,
        # PROCESS_LEVEL_NUM_APPROVED: back_ground_green + log_format_time + reset + green + log_format_data + reset,
        PROCESS_LEVEL_NUM_APPROVED: green + log_format + reset,
        logging.INFO: blue + log_format + reset,
        # PROCESS_LEVEL_NUM_DENIED: back_ground_red + log_format_time + reset + red + log_format_data + reset,
        PROCESS_LEVEL_NUM_DENIED: red + log_format + reset,
        logging.WARNING: back_ground_green + log_format + reset,
        logging.ERROR: back_ground_yellow + log_format + reset,
        logging.CRITICAL: back_ground_red + log_format + reset
    }

    def formatTime(self, record, datefmt=None):
        """Format time with microseconds"""
        ct = datetime.fromtimestamp(record.created)
        return ct.strftime("%H:%M:%S.%f")

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.log_format)
        formatter = logging.Formatter(log_fmt)
        formatter.formatTime = self.formatTime  # Use our microsecond formatter
        return formatter.format(record)


# ---------- Logger setup ----------
def set_up_loger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # voorkom dubbele logs in Spyder/Jupyter
    if logger.hasHandlers():
        logger.handlers.clear()

    # Handler + formatter toevoegen
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    
    # Suppress external library logging (matplotlib, etc.)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)


# --- Test voorbeeld ---
if __name__ == "__main__":
    set_up_loger()
    logger = logging.getLogger()

    logger.debug("Dit is een DEBUG message")
    logger.approved("Dit is een APPROVED message") # type: ignore
    logger.info("Dit is een INFO message")
    logger.denied("Dit is een DENIED message") # type: ignore
    logger.warning("Dit is een WARNING message")
    logger.error("Dit is een ERROR message")
    logger.critical("Dit is een CRITICAL message")
