import threading
from contextlib import contextmanager


_state = threading.local()


def sync_is_muted():
    return bool(getattr(_state, 'muted', False))


@contextmanager
def mute_sync():
    previous = sync_is_muted()
    _state.muted = True
    try:
        yield
    finally:
        _state.muted = previous
