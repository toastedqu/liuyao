"""Errors raised by the deterministic calendar module."""

from __future__ import annotations


class CalendarError(ValueError):
    """Base class for calendar-module errors."""


class InvalidGregorianDateTimeError(CalendarError):
    """Raised when the supplied Gregorian year/month/day/hour is not real."""


class ConfigurationError(CalendarError):
    """Raised when a calendar configuration value (e.g. zi-hour boundary) is invalid."""
