"""
MOH TIME OS - Notifier Module

Direct notification delivery to user without AI intermediary.
Supports multiple channels (push, email) with rate limiting.
"""

from .engine import NotificationEngine

__all__ = ["NotificationEngine"]
