from _thread import allocate_lock
from time import ticks_ms, ticks_diff
from machine import reset, WDT
from Locker import ConditionalLock

class Periodic():
	"""
	A class to execute a function periodically based on a specified frequency.

	Attributes:
		func (callable): The function to be executed periodically.
		freq (int): The frequency at which the function should be executed.
		default: The default value to return if the function is not called. This can be any type.
		args (tuple): The arguments to pass to the function.
		kwargs (dict): The keyword arguments to pass to the function.
		last_update (int): The timestamp (in milliseconds) of the last time the function was executed.

	Methods:
		call_func(): Executes the function with the specified arguments if the specified frequency time has elapsed since the last execution.
					 Returns the result of the function call or the default value if the function is not executed.
	"""

	def __init__(self, func, freq, default=None, *args, **kwargs):
		"""
		Initializes the Periodic instance with the function to be executed, its execution frequency, an optional default return value,
		and any arguments or keyword arguments to pass to the function.

		Parameters:
			func (callable): The function to be executed periodically.
			freq (int): The frequency at which the function should be executed. (Hz)
			default: The default value to return if the function is not called. This can be any type.
			*args: Optional positional arguments to pass to the function.
			**kwargs: Optional keyword arguments to pass to the function.
		"""
		self.func = func
		self.freq = freq
		self.default = default
		self.args = args
		self.kwargs = kwargs
		self.last_update = ticks_ms()
		self.bypass_timing = False

	def call_func(self, *args, **kwargs):
		"""
		Executes the function with the specified arguments if the specified frequency time has elapsed since the last execution.
		Updates the last execution timestamp and returns the result of the function call.
		If the frequency time has not elapsed, returns the default value.

		The method now combines `self.args` (arguments stored during initialization) with `args` (arguments passed directly to this method).

		Returns:
			The result of the function call if executed, otherwise returns the default value.
		"""
		current_time = ticks_ms()
		result = self.default
		if (self.bypass_timing) or (ticks_diff(current_time, self.last_update) > 1/self.freq*1000):
			combined_args = self.args + args
			combined_kwargs = self.kwargs.copy()
			combined_kwargs.update(kwargs)
			result = self.func(*combined_args, **combined_kwargs)
			self.last_update = current_time
			self.bypass_timing = False
		return result

class WatchDog():
	"""
	A class to implement a watchdog timer for multiple threads. It helps in monitoring the activity of threads
	and can terminate them if they become unresponsive based on a specified timeout.

	Attributes:
		timeout (int): The timeout value in milliseconds after which a thread is considered unresponsive.
		last_updates (dict): A dictionary to track the last update time of each thread. The keys are thread identifiers,
							 and the values are the last update timestamps.
		__lock (_thread.lock): A lock to ensure thread-safe updates to the last_updates dictionary.

	Methods:
		kill(): Marks the first thread in the last_updates dictionary as killed by setting its last update time to -1.
		update(thread_id): Updates the last update time for the specified thread to the current time.
		running(): Checks if any thread has exceeded the timeout period without updating. Returns False if any have,
				   True otherwise.
	"""

	def __init__(self, timeout:int, stop_routine=None):
		"""
		Initializes the WatchDog instance with a specified timeout and an empty dictionary for tracking thread updates.

		Parameters:
			timeout (int): The timeout value in milliseconds.
		"""
		self.timeout = timeout
		self.stop_routine = stop_routine
		self.last_updates = {}  # Dictionary to track last update per thread
		self.__lock = allocate_lock()
		self.wdt = WDT(timeout = 8388)

	def kill(self):
		"""
		Marks the first thread in the last_updates dictionary as killed by setting its last update time to -1.
		This method is thread-safe.
		"""
		with ConditionalLock(self.__lock) as aquired:
			if not aquired:
				return
			if self.last_updates.keys():
				first_key = next(iter(self.last_updates.keys()))
				self.last_updates[first_key] = -1
			if self.stop_routine:
				self.stop_routine()
		reset()

	def update(self, thread_id):
		"""
		Updates the last update time for the specified thread to the current time. If the thread is already marked
		as killed, it does nothing.

		Parameters:
			thread_id: The identifier of the thread to update.
		This method is thread-safe.
		"""
		with ConditionalLock(self.__lock) as aquired:
			if not aquired:
				return
			if self.last_updates.get(thread_id, 0) >= 0:
				self.last_updates[thread_id] = ticks_ms()
			self.wdt.feed()

	def update_WDT(self):
		self.wdt.feed()

	def running(self):
		"""
		Checks if any thread has exceeded the timeout period without updating. If a thread's last update time
		is more than the timeout value ago, it is considered unresponsive, and this method returns False.
		Otherwise, it returns True.

		Returns:
			bool: False if any thread is unresponsive, True otherwise.
		This method is thread-safe.
		"""
		with ConditionalLock(self.__lock) as aquired:
			if not aquired:
				return False
			current_time = ticks_ms()
			for key in self.last_updates.keys():
				if ticks_diff(current_time, self.last_updates.get(key, current_time)) > self.timeout:
					return False
		return True