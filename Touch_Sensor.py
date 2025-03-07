from machine import Pin
from utime import ticks_ms, sleep_ms

class TouchButton:
	"""
	A class to manage touch button inputs on a specified pin.

	Attributes:
		button (Pin): The pin object associated with the touch button.
		last_touch_time (int): The last time (in milliseconds) the button was touched.
		touch_count (int): The number of times the button has been touched.
		reset_time (int): The time (in milliseconds) to wait before resetting the touch count.
		hold_time (int): The time (in milliseconds) to consider a press as a hold.
		last_button_state (int): The last state of the button (0 for not pressed, 1 for pressed).

	Methods:
		update_state():
			Updates the state of the touch button based on the current and previous readings.
			Returns an integer representing the button's state:
				0 for no action,
				a positive integer for the duration of a hold in milliseconds,
				-1 for a single tap,
				-2 for a double tap.

		reset():
			Resets the touch count and last touch time to their default values.

		get_state():
			Returns the current state of the button by calling update_state().
	"""

	def __init__(self, pin_number):
		"""
		Initializes the TouchButton with a specific pin.

		Parameters:
			pin_number (int): The GPIO pin number where the touch button is connected.
		"""
		self.button = Pin(pin_number, Pin.IN, Pin.PULL_DOWN)
		self.last_touch_time = 0
		self.touch_count = 0
		self.reset_time = 300  # Time to wait before resetting touch count
		self.hold_time = 500  # Time to consider a press as hold
		self.last_button_state = 0
		self.current_button_state = 0
		self.state = 0

	def update_state(self):
		"""
		Updates the state of the touch button based on the current and previous readings.
		"""
		current_time = ticks_ms()
		self.current_button_state = self.button.value()
		self.state = 0  # Default state unless a press is detected

		if self.current_button_state != self.last_button_state:
			if self.current_button_state == 1:
				self.touch_count += 1
				self.last_touch_time = current_time
			self.last_button_state = self.current_button_state
		elif self.current_button_state == 1 and (current_time - self.last_touch_time) >= self.hold_time:
			self.state = current_time - self.last_touch_time  # Time it has been holding for
			self.touch_count = 0
		elif self.current_button_state == 0:
			if (current_time - self.last_touch_time) >= self.reset_time:
				self.state = -self.touch_count
				self.reset()
			if (current_time - self.last_touch_time) >= self.hold_time:
				self.reset()

	def reset(self):
		"""
		Resets the touch count and last touch time to their default values.
		"""
		self.touch_count = 0
		self.last_touch_time = ticks_ms()

	def get_state(self):
		"""
		Returns the current state of the button.

		Returns:
			int: The state of the button:
				0 for no action,
				a positive integer for the duration of a hold in milliseconds,
				-1 for a single tap,
				-2 for a double tap.
		"""
		self.update_state()
		return self.state

class TouchManager:
	"""
	A class to manage multiple touch buttons and their states, specifically designed for handling left and right touch buttons.

	Attributes:
		left_button (TouchButton): An instance of TouchButton for the left button.
		right_button (TouchButton): An instance of TouchButton for the right button.
		was_holding_both (bool): A flag to track if both buttons were being held simultaneously in the previous state.

	Methods:
		update_and_manage_state():
			Updates the state of both touch buttons and manages combined states, such as detecting simultaneous holds.
			Returns a dictionary with the state of the left and right buttons.
	"""

	def __init__(self):
		"""
		Initializes the TouchManager with two touch buttons, one for the left and one for the right.
		"""
		self.left_button = TouchButton(17)  # Initialize left button
		self.right_button = TouchButton(19)  # Initialize right button
		self.was_holding_both = False  # Track if previously holding both

	def update_and_manage_state(self, state_dict):
		"""
		Updates the state of both touch buttons and manages combined states, such as detecting simultaneous holds.

		inputs:
			state_dict (dict): A dictionary with keys 'left' and 'right', representing the state of the left and right buttons, respectively.
							   The state values are integers, where 0 indicates no action, a positive integer indicates the duration of a hold in milliseconds,
							   -1 indicates a single tap, and -2 indicates a double tap.
		"""
		self.left_button.get_state()
		self.right_button.get_state()
		state_dict['left'] = 0
		state_dict['right'] = 0

		# Check if previously holding both and now one of the sides is not holding
		if self.was_holding_both and (self.left_button.state <= 0 or self.right_button.state <= 0):
			self.left_button.reset()  # Reset left button state
			self.right_button.reset()  # Reset right button state
			self.was_holding_both = False  # Update the flag since we reset the states
			state_dict['left'] = 0
			state_dict['right'] = 0
			return state_dict

		if self.left_button.state > 0 and self.right_button.state > 0:
			self.was_holding_both = True  # Update the flag to indicate we are now holding both
			state_dict["left"] = self.left_button.state
			state_dict["right"] = self.right_button.state
		else:
			self.was_holding_both = False  # Ensure the flag is false if not holding both
			if self.left_button.state != 0:
				state_dict["left"] = self.left_button.state
			if self.right_button.state != 0:
				state_dict["right"] = self.right_button.state

# Usage
if __name__ == "__main__":
	touch_manager = TouchManager()
	state_message = {"left": 0, "right": 0}  # Initialize with 0 for none

	while True:
		touch_manager.update_and_manage_state(state_message)
		if state_message['left'] != 0 or state_message['right'] != 0:  # Only print if there's a state message
			print(state_message)
		sleep_ms(100)