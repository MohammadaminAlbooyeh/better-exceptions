from __future__ import absolute_import

import sys

from logging import Logger, StreamHandler


def patch():
    import logging
    from . import format_exception

    colored_format_exception = lambda exc_info: u''.join(format_exception(*exc_info))

    # Python's logging module caches the formatted exception text on
    # LogRecord.exc_text.  When a TTY handler formats a record first, the
    # cached ANSI-colored text is reused by every subsequent handler
    # (e.g. FileHandler), causing color escape codes to appear in log files.
    #
    # Fix: wrap Handler.emit so that exc_text is reset to None before each
    # handler processes the record, forcing each handler's formatter to
    # recompute the exception text independently using its own formatException.
    # The original value is restored afterwards so that callers who inspect
    # exc_text after logging.handle() still observe consistent behaviour.
    _orig_emit = logging.Handler.emit

    def _isolated_emit(handler_self, record):
        saved = record.exc_text
        record.exc_text = None
        try:
            _orig_emit(handler_self, record)
        finally:
            record.exc_text = saved

    logging.Handler.emit = _isolated_emit

    # Patch formatException only on existing stderr (TTY) handlers so they
    # produce colourised output.  Non-TTY handlers (e.g. FileHandler) keep
    # Python's default plain-text formatException.
    # Note: logging._handlerList stores weakrefs; dereference each ref once.
    for ref in logging._handlerList:
        handler = ref() if callable(ref) else ref
        if handler is None:
            continue
        if not isinstance(handler, StreamHandler):
            continue
        if getattr(handler, 'stream', None) is not sys.stderr:
            continue
        if handler.formatter is None:
            continue
        handler.formatter.formatException = colored_format_exception


class BetExcLogger(Logger):
    def __init__(self, *args, **kwargs):
        super(BetExcLogger, self).__init__(*args, **kwargs)
        patch()
