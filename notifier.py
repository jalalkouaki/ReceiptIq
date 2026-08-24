from logger import log_event

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:  # pragma: no cover
    PLYER_AVAILABLE = False


def send_notification(title: str, message: str):
    """Send a desktop notification using plyer."""
    log_event("server", f"Notification: {title} - {message}", level="INFO")
    if PLYER_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="ReceiptIQ",
                timeout=5
            )
        except Exception as e:
            log_event("error", f"Failed to send desktop notification: {e}", level="WARNING")
