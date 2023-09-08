import logging
from typing import List, Optional


class BeeperLogger:
    def __init__(self,
                 level: int = logging.INFO):
        self.log_buffer: List[str] = []
        self.setup(level)

    def setup(self,
              level: int = logging.INFO):
        self.logger = logging.getLogger("beeper_logger")
        self.logger.setLevel(level)

    def get_formatted(self,
                      msg: str,
                      level: str,
                      *args) -> str:
        formatted = f"{level}: {msg}"
        if len(args) > 0:
            formatted = formatted.format(*args)

        return formatted

    def debug(self,
              msg: str,
              *args):
        self.log_buffer.append(
            self.get_formatted(msg, "DEBUG", *args))
        self.logger.debug(msg, *args)

    def info(self,
             msg: str,
             *args):
        self.log_buffer.append(
            self.get_formatted(msg, "INFO", *args))
        self.logger.info(msg, *args)

    def warn(self,
             msg: str,
             *args):
        self.log_buffer.append(
            self.get_formatted(msg, "WARN", *args))
        self.logger.warn(msg, *args)

    def error(self,
              msg: str,
              exc: Optional[Exception] = None,
              *args):
        self.log_buffer.append(
            self.get_formatted(msg, "ERROR", *args))
        self.logger.error(msg, *args, exc_info=exc)


log = BeeperLogger()
