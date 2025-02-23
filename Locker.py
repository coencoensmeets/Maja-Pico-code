import _thread
from time import ticks_ms, ticks_diff, sleep_ms

class ConditionalLock:
    """
    A context manager for conditional locking.

    This class is designed to manage a lock conditionally, based on a given condition. It can be used to control access to a shared resource only under certain conditions, thereby providing more flexibility than a standard lock.

    Attributes:
        lock (_thread.lock): The lock object to be managed.
        condition (bool): The condition that determines whether the lock should be acquired or released.
        timeout (int): The timeout for acquiring the lock in milliseconds.

    Methods:
        __enter__():
            Acquires the lock if the condition is True. This method is automatically called when entering the context managed by this class.
        __exit__(exc_type, exc_val, exc_tb):
            Releases the lock if it was acquired. This method is automatically called when exiting the context.
    """

    def __init__(self, lock, condition=True, timeout=10000):
        """
        Initializes the ConditionalLock with a lock, a condition, and a timeout.

        Parameters:
            lock (_thread.lock): The lock object to be managed.
            condition (bool): The condition that determines whether the lock should be acquired or released. Defaults to True.
            timeout (int): The timeout for acquiring the lock in milliseconds. Defaults to 10000 milliseconds (10 seconds).
        """
        self.lock = lock
        self.condition = condition
        self.timeout = timeout
        self.acquired = False

    def __enter__(self):
        """
        Acquires the lock if the condition is True.

        This method is automatically called when entering the context managed by this class.
        """
        if self.condition:
            start_time = ticks_ms()
            while self.lock.locked():
                if ticks_diff(ticks_ms(), start_time) > self.timeout:
                    return False
            self.lock.acquire()
            self.acquired = True
        return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Releases the lock if it was acquired.

        This method is automatically called when exiting the context. It ensures that the lock is released if it was acquired, regardless of whether an exception occurred within the context.

        Parameters:
            exc_type: The type of the exception that caused the context to be exited, if any.
            exc_val: The value of the exception, if any.
            exc_tb: The traceback of the exception, if any.
        """
        if self.condition and self.acquired:
            self.lock.release()
            self.acquired = False