"""
Tests that ANSI colour codes do not appear in log files (issue #87).

When a TTY StreamHandler and a FileHandler are both attached to a logger,
Python caches the formatted exception text on the LogRecord.  Without the
fix the TTY handler (which runs first) stores its ANSI-coloured exc_text on
the record; the FileHandler then reuses that cached text and writes colour
codes into the log file.
"""

import io
import logging
import sys
import unittest

import better_exceptions

# A minimal ANSI escape-code pattern.
_ANSI_ESCAPE = '\x1b['


def _has_ansi(text):
    return _ANSI_ESCAPE in text


class FileHandlerColorTest(unittest.TestCase):

    def setUp(self):
        better_exceptions.hook()

    def _make_logger(self, file_stream, tty_stream=None):
        """Return a logger with a FileHandler and an optional TTY-like handler."""
        logger = logging.getLogger(self.id())
        logger.propagate = False
        logger.setLevel(logging.DEBUG)

        file_handler = logging.StreamHandler(file_stream)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(file_handler)

        if tty_stream is not None:
            tty_handler = logging.StreamHandler(tty_stream)
            tty_handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(tty_handler)

        return logger

    def test_file_handler_alone_no_color(self):
        """A plain file handler must never produce ANSI codes."""
        buf = io.StringIO()
        logger = self._make_logger(buf)
        try:
            raise ValueError('boom')
        except ValueError:
            logger.exception('error')

        output = buf.getvalue()
        self.assertIn('ValueError', output)
        self.assertFalse(_has_ansi(output),
                         'ANSI codes found in file-only handler output')

    def test_file_handler_with_tty_handler_no_color(self):
        """File handler must not receive ANSI codes even when a TTY handler
        processes the same record first (exc_text caching regression)."""

        class FakeTTY(io.StringIO):
            """Mimics a terminal: isatty() returns True."""
            def isatty(self):
                return True

        file_buf = io.StringIO()
        tty_buf = FakeTTY()

        # TTY handler is added first so it formats the record before the file
        # handler, which is the scenario that triggers the caching bug.
        logger = logging.getLogger(self.id())
        logger.propagate = False
        logger.setLevel(logging.DEBUG)

        tty_handler = logging.StreamHandler(tty_buf)
        tty_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(tty_handler)

        file_handler = logging.StreamHandler(file_buf)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(file_handler)

        try:
            raise RuntimeError('cache bug')
        except RuntimeError:
            logger.exception('error')

        file_output = file_buf.getvalue()
        self.assertIn('RuntimeError', file_output)
        self.assertFalse(_has_ansi(file_output),
                         'ANSI codes leaked from TTY handler into file handler output')

    def test_exc_text_restored_after_emit(self):
        """record.exc_text must be restored to its original value after emit
        so that code inspecting it afterwards sees a consistent state."""
        buf = io.StringIO()
        logger = self._make_logger(buf)

        record = logging.LogRecord(
            name='test', level=logging.ERROR,
            pathname='', lineno=0,
            msg='msg', args=(), exc_info=None,
        )
        pre_set_value = 'pre-formatted text'
        record.exc_text = pre_set_value

        # Manually emit through the handler.
        handler = logger.handlers[0]
        handler.emit(record)

        self.assertEqual(record.exc_text, pre_set_value,
                         'exc_text was not restored after emit')

    def test_exc_text_none_restored_after_emit(self):
        """If exc_text was None before emit it must be None afterwards."""
        buf = io.StringIO()
        logger = self._make_logger(buf)

        record = logging.LogRecord(
            name='test', level=logging.ERROR,
            pathname='', lineno=0,
            msg='msg', args=(), exc_info=None,
        )
        record.exc_text = None

        handler = logger.handlers[0]
        handler.emit(record)

        self.assertIsNone(record.exc_text,
                          'exc_text should remain None when it was None before emit')


if __name__ == '__main__':
    unittest.main()
