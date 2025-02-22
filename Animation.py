from machine import Pin, I2C
from utime import sleep, time, sleep_ms, ticks_ms, ticks_diff
import random
import _thread
from math import pi

from shapeDrawer import shapeDrawer
from Light import Lights
from Locker import ConditionalLock
from TimeProfiles import Time_Profiles

import gc9a01
import tft_config
import gc
from Particle import Tear, Heart
from Light import Lights

def weighted_choice(options, weights):
	total = sum(weights)
	cumulative_weights = []
	cumulative_sum = 0
	for weight in weights:
		cumulative_sum += weight
		cumulative_weights.append(cumulative_sum)
	
	r = random.uniform(0, total)
	for option, cumulative_weight in zip(options, cumulative_weights):
		if r < cumulative_weight:
			return option

class StatusAnimator:
	"""
	Manages animations for facial expressions by queuing and executing animations with specified timing profiles.

	Attributes:
		animation_queue (list): A queue of animations to be executed.
		active_animations (list): List of currently active animations.
	"""

	def __init__(self):
		self.animation_queue = []
		self.active_animations = {}
		self.time_animation_done = ticks_ms()

	def get_final_status(self, current_status):
		"""
		Returns the status of the State after all queued animations are completed.
		
		:param current_status: The current status of the State.
		:return: The status of the State after all queued animations are completed.
		"""
		status = current_status.copy()
		for item in self.active_animations.values():
			if 'end_config' in item:
				end_config = item['end_config']
				status.update(end_config)
		for item in self.animation_queue:
			end_config, duration, timing_profile, start_time = item
			status.update(end_config)
		return status
	
	def get_final_time(self):
		"""
		Returns the duration of all queued animations.
		"""
		time = 0
		for item in self.active_animations.values():
			if 'duration' in item:
				time += item['duration']
		for item in self.animation_queue:
			time += item[1]
		return time
	
	def reset_queue(self):
		"""
		Resets the animation queue and active animations.
		"""
		self.animation_queue = []
		self.active_animations = []

	def is_animation_active(self):
		"""
		Returns True if an animation is active or queued, False otherwise.
		"""
		return len(self.active_animations) > 0 or len(self.animation_queue) > 0

	def trigger_animation(self, end_config, duration, timing_profile=Time_Profiles.linear, force=False):
		"""
		Queues a new animation.
		
		:param end_config: The target configuration of the State at the end of the animation.
		:param duration: The duration of the animation in milliseconds.
		:param timing_profile: The timing function used to interpolate the animation.
		"""
		self.__update_time_animation_done()
		for prop, value in end_config.items():
			self.animation_queue.append(({prop: value}, duration, timing_profile, ticks_ms() if force else self.time_animation_done))
		self.time_animation_done += duration
	def trigger_wait_animation(self, duration):
		"""
		Queues a wait period as an animation with the last configuration.
		
		:param duration: The duration of the wait period in milliseconds.
		"""
		self.__update_time_animation_done()
		if self.animation_queue:
			self.time_animation_done += duration

	def animate_status(self, current_status):
		"""
		Updates the State configuration based on the current animation and time, allowing
		for independent animation of each property.
		
		:param current_status: The current configuration of the State.
		:return: The updated configuration of the State.
		"""
		current_time = ticks_ms()

		# Move animations from queue to active, per property
		for end_config, duration, timing_profile, start_time in list(self.animation_queue):
			if ticks_diff(current_time, start_time) >= 0:
				for prop, value in end_config.items():
					start_config = {prop: current_status.get(prop, 0)}
					end_config = {prop: value}
					end_time = start_time + duration

					if prop not in self.active_animations.keys():
						self.active_animations[prop] = {}

					if end_config == self.active_animations[prop].get(end_config):
						self.animation_queue.remove((end_config, duration, timing_profile, start_time))
						continue
					self.active_animations[prop] = {
						'start_config': start_config,
						'end_config': end_config,
						'start_time': start_time,
						'end_time': end_time,
						'duration': duration,
						'timing_profile': timing_profile
					}
					self.animation_queue.remove((end_config, duration, timing_profile, start_time))

		new_status = {}
		completed_animations = []

		# Update active animations per property
		for prop, animation in self.active_animations.items():
			if animation:
				elapsed_time = ticks_diff(current_time, animation['start_time'])
				duration = animation['duration']
				start_config = animation['start_config']
				end_config = animation['end_config']
				timing_profile = animation['timing_profile']

				if ticks_diff(current_time, animation['end_time']) >= 0:
					elapsed_time = duration
					completed_animations.append((prop, animation))

				start_value = start_config[prop]
				end_value = end_config[prop]
				interpolated_value = timing_profile(start_value, end_value, elapsed_time, duration)
				new_status[prop] = interpolated_value

		# Remove completed animations
		for prop, animation in completed_animations:
			self.active_animations.pop(prop)

		return new_status
	
	def __update_time_animation_done(self):
		"""
		Updates the time of the last completed animation to the current time.
		"""
		if ticks_diff(ticks_ms(), self.time_animation_done) >= 0:
			self.time_animation_done = ticks_ms()

class AnimationBank():
	"""
	A collection of static methods for triggering pre-defined facial animations.

	Methods:
		blink(State): Triggers a blink animation.
		wink(State, left_right): Triggers a wink animation.
		falling_asleep(State): Triggers a falling asleep animation.
	"""

	@staticmethod
	def blink(State):
		saved_state = State.get_final_state(dont_lock=True)
		State.trigger_animation({'eye_open': 0.0}, 200, Time_Profiles.ease_in, dont_lock=True)
		State.trigger_animation({'eye_open': saved_state['eye_open']}, 200, Time_Profiles.ease_out, dont_lock=True)

	@staticmethod
	def wink(State, left_right:int=None):
		if left_right is None:
			left_right = random.choice([-1,1])

		State.trigger_animation({'left_right': left_right}, 250, Time_Profiles.ease_in, dont_lock=True)
		State.trigger_animation({'left_right': 0}, 250, Time_Profiles.ease_out, dont_lock=True)

	@staticmethod
	def shake_yes(State, amount=None):
		saved_state = State.get_final_state(dont_lock=True)
		if amount is None:
			amount = random.randint(1,3)
		for i in range(amount):
			State.trigger_animation({'y': 140}, 400, Time_Profiles.ease_in_out, dont_lock=True)
			State.trigger_animation({'y': 100}, 400, Time_Profiles.ease_in_out, dont_lock=True)
		State.trigger_animation({'y': saved_state['y']}, 400, Time_Profiles.ease_out, dont_lock=True)

	@staticmethod
	def shake_no(State, amount=None):
		saved_state = State.get_final_state(dont_lock=True)
		if amount is None:
			amount = random.randint(1,3)
		for i in range(amount):
			State.trigger_animation({'x': 140}, 400, Time_Profiles.ease_in_out, dont_lock=True)
			State.trigger_animation({'x': 100}, 400, Time_Profiles.ease_in_out, dont_lock=True)
		State.trigger_animation({'x': saved_state['x']}, 400, Time_Profiles.ease_out, dont_lock=True)
		
	@staticmethod
	def dancing(State, amount=None):
		saved_state = State.get_final_state(dont_lock=True)
		if amount is None:
			amount = random.randint(2,5)
		for i in range(amount):
			State.trigger_animation({'x': 140, 'y': 100, 'value': saved_state['value']*0.4}, 400, Time_Profiles.ease_in_out, dont_lock=True)
			State.trigger_animation({'x': 120, 'y': 140, 'value': saved_state['value']}, 400, Time_Profiles.ease_in_out, dont_lock=True)
			State.trigger_animation({'x': 100, 'y': 100, 'value': saved_state['value']*0.4}, 400, Time_Profiles.ease_in_out, dont_lock=True)
			State.trigger_animation({'x': 120, 'y': 140, 'value': saved_state['value']}, 400, Time_Profiles.ease_in_out, dont_lock=True)
		State.trigger_animation({'x': saved_state['x'], 'y': saved_state['y'], 'value': saved_state['value']}, 600, Time_Profiles.ease_out, dont_lock=True)

	@staticmethod
	def kiss(State):
		saved_state = State.get_final_state(dont_lock=True)
		heart = Heart((saved_state['x'], saved_state['y']+45, pi/4))
		heart.scale(0.75)
		State.queue_particle(heart, State.get_final_time()+200, dont_lock=True)
		State.trigger_animation({'mouth_width': 10}, 200, Time_Profiles.ease_in_out, dont_lock=True)
		State.trigger_animation({'mouth_width': saved_state['mouth_width']}, 200, Time_Profiles.ease_in_out, dont_lock=True)

	@staticmethod
	def eye_brows_raise(State, amount=2):
		saved_state = State.get_final_state(dont_lock=True)
		for i in range(amount):
			State.trigger_animation({'eye_open': 1.0, 'eyebrow_angle': 0.0}, 200, Time_Profiles.ease_in, dont_lock=True)
			State.trigger_animation({'eye_open': saved_state['eye_open'], 'eyebrow_angle': saved_state['eyebrow_angle']}, 200, Time_Profiles.ease_out, dont_lock=True)

	@staticmethod
	def yawn(State):
		saved_state = State.get_final_state(dont_lock=True)
		State.trigger_animation({'mouth_width': 0, 'yawn': 0.8, 'eye_open': 0.2, 'under_eye_lid': 0.5}, 1200, Time_Profiles.ease_in, dont_lock=True)
		State.trigger_animation({'mouth_width': 0, 'yawn': 1, 'eye_open': 0.1, 'under_eye_lid': 0.7}, 800, Time_Profiles.ease_out, dont_lock=True)
		State.trigger_animation({'mouth_width': saved_state['mouth_width'], 'yawn': 0, 'eye_open': saved_state['eye_open'], 'under_eye_lid': saved_state['under_eye_lid']}, 800, Time_Profiles.ease_in_out, dont_lock=True)

	@staticmethod
	def falling_asleep(State, amount = None):
		saved_state = State.get_final_state(dont_lock=True)
		if amount is None:
			amount = random.randint(1,3)
		for i in range(amount):
			State.trigger_animation({'eye_open': random.randint(0,4)//10, 'y': saved_state['y']+20,"value": 0.1}, random.randint(1500,3000), Time_Profiles.ease_in)
			State.trigger_animation({'eye_open': saved_state['eye_open'], 'y': saved_state['y'], "value": saved_state['value']}, 100, Time_Profiles.ease_out)
			if (i+1) < amount:
				State.trigger_wait_animation(random.randint(500, 1500))

class Trigger:
	"""
	A class used to manage and execute triggers for animations based on time and random chance.

	Attributes:
		State (State): The current state of the animation.
		trigger_function (str): The name of the function to be triggered.
		change_function (function): A function that determines the probability of the trigger occurring based on time.
		__trigger_time (float): The last time the trigger was executed.

	Methods:
		check_trigger(): Checks if the trigger should be executed based on the change function.
		trigger(): Executes the trigger function.
	"""

	def __init__(self, State, trigger_function:str, change_function=lambda t: 0):
		self.__State = State
		self.trigger_function = trigger_function
		self.change_function = change_function
		self.__trigger_time = time()

	def check_trigger(self):
		"""
		Checks if the trigger should be executed based on the change function.
		If the trigger condition is met, it updates the trigger time and executes the trigger.
		"""
		if self.__do_trigger():
			self.__trigger_time = time()
			self.trigger()

	def trigger(self):
		"""
		Executes the trigger function if it exists in the current emotion.
		"""
		if hasattr(self.__State.Emotion.emotion, f'_trigger_{self.trigger_function}') and callable(getattr(self.__State.Emotion.emotion, f'_trigger_{self.trigger_function}')):
			getattr(self.__State.Emotion.emotion, f'_trigger_{self.trigger_function}')()
		else:
			getattr(self.__State.Emotion.emotion, f'trigger_{self.trigger_function}')()

	def __do_trigger(self):
		"""
		Determines if the trigger should be executed based on the change function.
		
		Returns:
			bool: True if the trigger should be executed, False otherwise.
		"""
		return random.random() < self.change_function(time()-self.__trigger_time+0.001)


class Emotion:
	"""
	A base class for managing different emotional states and their associated triggers.

	Attributes:
		State (State): The current state of the animation.
		social_value (int): A value representing the social aspect of the emotion.
		tired_value (int): A value representing the tiredness aspect of the emotion.
		name (str): The name of the emotion.
		triggers (dict): A dictionary of triggers associated with the emotion.

	Methods:
		update_parameters(): Updates the parameters for the emotion's triggers.
		check_triggers(): Checks and executes triggers based on their change functions.
		trigger_blink(): Triggers a blink animation.
		trigger_face_move(): Triggers a face move animation.
		trigger_background(): Triggers a background animation.
	"""

	def __init__(self, State, social_value=50, tired_value=50):
		self.social_value = social_value
		self.tired_value = tired_value
		self.name = None

		self.State = State
		
		self.triggers = {}
		self.triggers['blink'] = Trigger(self.State, 'blink', None)
		self.triggers['face_move'] = Trigger(self.State, 'face_move', None)
		self.triggers['background'] = Trigger(self.State, 'background', None)
		self.triggers['tired'] = Trigger(self.State, 'tired', None)

		self.update_parameters()

	def update_parameters(self):
		"""
		Updates the parameters for the emotion's triggers.
		"""
		self.triggers['blink'].change_function = lambda t: 10**(-2)*t**2
		self.triggers['face_move'].change_function = lambda t: 10**(-3.5)*t**2+1*t**(-1)
		self.triggers['background'].change_function = lambda t: 10**(-2.8)*t**2
		self.triggers['tired'].change_function = lambda t:  10**(-2.8-(1-(self.tired_value/100)**2)*3)*t**2

		if hasattr(self, f'_update_parameters') and callable(getattr(self, f'_update_parameters')):
			getattr(self, f'_update_parameters')()

	def check_triggers(self):
		"""
		Checks and executes triggers based on their change functions.
		"""
		for trigger in self.triggers.values():
			trigger.check_trigger()

	def trigger_blink(self):
		"""
		Triggers a blink animation.
		"""
		AnimationBank.blink(self.State)

	def trigger_face_move(self):
		"""
		Triggers a face move animation.
		"""
		self.State.trigger_animation({'x': random.randint(100, 140), 'y': random.randint(100, 140)}, random.randint(500,1500), Time_Profiles.ease_in_out, dont_lock=True)

	def trigger_background(self):
		"""
		Triggers a background animation.
		"""
		pass

	def trigger_tired(self):
		"""
		Triggers a tired animation.
		"""
		if (self.tired_value <0.5):
			pass
		elif (self.tired_value < 0.8):
			AnimationBank.yawn(self.State)
		else:
			Options = {'yawn': 1.0, 'falling_asleep': 0}
			choice = weighted_choice(list(Options.keys()), weights=Options.values())
			if choice == 'yawn':
				AnimationBank.yawn(self.State)
			elif choice == 'falling_asleep':
				AnimationBank.falling_asleep(self.State)



	
class Happy(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "happy"

		self.State.trigger_animation({'y': 120, 'eye_open': 1, 'eyebrow_angle': 0.0, 'under_eye_lid': 0.0, 
								'smile': 1, 'smirk': 0, 'cheeks': 0, 'mouth_width': 40, 'yawn': 0,
								"hue": 50, "saturation": 1, "value": 1}, 3000, Time_Profiles.ease_in_out)

	def _trigger_background(self):
		Options = {'wink': 0.4, 'shake_yes': 0.4, 'dance': 0.2}
		choice = weighted_choice(list(Options.keys()), weights=Options.values())
		print(f"Happy background animation: {choice}")
		if choice == 'wink':
			AnimationBank.wink(self.State)
		elif choice == 'shake_yes':
			AnimationBank.shake_yes(self.State, amount=random.randint(2,4))
		elif choice == 'dance':
			AnimationBank.dancing(self.State, amount=random.randint(2,5))
		

class Angry(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "angry"

		self.State.trigger_animation({'eye_open': 0.8, 'eyebrow_angle': 1.0, 'under_eye_lid': 0.3, 
								'cheeks' : 0, 'smile': -1, 'smirk': 0, 'mouth_width': 40, 'yawn': 0,
								"hue": 0, "saturation": 1, "value": 1}, 3000, Time_Profiles.ease_in_out)

	def _trigger_face_move(self):
		self.State.trigger_animation({'x': random.randint(100, 140), 'y': random.randint(100, 130)}, random.randint(500,1000), Time_Profiles.ease_in_out, dont_lock=True)

	def _trigger_background(self):
		Options = {'shake_no': 1}
		choice = weighted_choice(list(Options.keys()), weights=Options.values())

		if choice == 'shake_no':
			saved_state = self.State.get_final_state(dont_lock=True)
			for i in range(random.randint(1,2)):
				self.State.trigger_animation({'x': 140}, 100, Time_Profiles.ease_in_out, dont_lock=True)
				self.State.trigger_wait_animation(200, dont_lock=True)
				self.State.trigger_animation({'x': 100}, 100, Time_Profiles.ease_in_out, dont_lock=True)
			self.State.trigger_animation({'x': saved_state['x']}, 200, Time_Profiles.ease_out, dont_lock=True)

class Sad(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "sad"

		self.State.trigger_animation({'y': 140, 'eye_open': 0.65, 'eyebrow_angle': -1.0, 'under_eye_lid': 0.0, 
								'cheeks' : 0, 'smile': -1, 'smirk': 0, 'mouth_width': 40, 'yawn': 0, 
								"hue": 240, "saturation": 1, "value": 1}, 3000, Time_Profiles.ease_in_out)
		self.update_parameters()

	def _update_parameters(self):
		self.triggers['background'].change_function = lambda t: 1e-2*t**2

	def _trigger_face_move(self):
		self.State.trigger_animation({'x': random.randint(100, 140), 'y': random.randint(125, 150)}, random.randint(500,1000), Time_Profiles.ease_in_out, dont_lock=True)

	def _trigger_background(self):
		Options = {'shake_no': 0.25, 'tear': 0.5, 'crying': 0.25}
		choice = weighted_choice(list(Options.keys()), weights=Options.values())

		if choice == 'shake_no':
			AnimationBank.shake_no(self.State, amount=random.randint(2,4))
		elif choice == 'tear':
			status = self.State.get_current_state(dont_lock=True)
			under_y = self.State.face.eye_height-status['under_eye_lid']*self.State.face.eye_height/2+status['y']-65

			tear = Tear((status['x']+45*random.choice([-1, 1]), under_y+5, pi/2))
			tear.scale(0.75)
			self.State.spawn_particle(tear, dont_lock=True)
		elif choice == 'crying':
			status = self.State.get_current_state(dont_lock=True)
			under_y = self.State.face.eye_height-status['under_eye_lid']*self.State.face.eye_height/2+status['y']-65

			self.State.trigger_animation({'y': 140}, 250, Time_Profiles.ease_in_out, force=True,  dont_lock=True)
			for i in range(0, random.randint(3, 6)):
				self.State.trigger_animation({'y': 120}, 500, Time_Profiles.ease_in_out, dont_lock=True)
				self.State.trigger_animation({'y': 140}, 250, Time_Profiles.ease_in_out, dont_lock=True)

				for side in [-1, 1]:
					tear = Tear((status['x']+45*side, under_y+5, pi/2))
					tear.scale(0.75)
					self.State.queue_particle(tear, 750*i, dont_lock=True)
				
			self.State.trigger_animation({'y': status['y']}, 200, Time_Profiles.ease_out, dont_lock=True)
			for side in [-1, 1]:
					tear = Tear((status['x']+45*side, under_y+5, pi/2))
					tear.scale(0.75)
					self.State.queue_particle(tear, 750*(i+1), dont_lock=True)

class Okay(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "okay"

		self.State.trigger_animation({'eye_open': 1, 'eyebrow_angle': 0.0, 'under_eye_lid': 0.4, 
								'smile': 0,'cheeks' : 0, 'smirk': 0, 'mouth_width': 55, 'yawn': 0,
								"hue": 120, "saturation": 1, "value": 0}, 3000, Time_Profiles.ease_in_out)

class Horny(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "horny"

		self.State.trigger_animation({'eye_open': 0.7, 'eyebrow_angle': 0.3, 'under_eye_lid': 0.2, 
									'smile': 1, 'smirk': random.choice([-1,1]), 'cheeks' : 0, 'mouth_width': 60, 
									"hue": 275, "saturation": 1, "value": 1}, 3000, Time_Profiles.ease_in_out)

	def _trigger_background(self):
		Options = {'wink': 0.2, 'shake_yes': 0.05, 'dance': 0.05, 'eye_brows_raise': 0.3, 'fast_blinking': 0.2, 'kiss': 0.2}
		choice = weighted_choice(list(Options.keys()), weights=Options.values())
		print(f"Happy background animation: {choice}")
		if choice == 'wink':
			AnimationBank.wink(self.State)
		elif choice == 'shake_yes':
			AnimationBank.shake_yes(self.State, amount=random.randint(2,4))
		elif choice == 'dance':
			AnimationBank.dancing(self.State, amount=random.randint(2,5))
		elif choice == 'eye_brows_raise':
			AnimationBank.eye_brows_raise(self.State, amount=random.randint(2,5))
		elif choice == 'fast_blinking':
			for i in range(random.randint(4, 6)):
				AnimationBank.blink(self.State)
		elif choice == 'kiss':
			AnimationBank.kiss(self.State)

class Love(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "love"

		self.State.trigger_animation({'eye_open': 1.0, 'eyebrow_angle': 0.0, 'under_eye_lid': 0.5, 
								'smile': 1, 'cheeks' : 1, 'smirk': 0, 'mouth_width': 40, 'yawn': 0, 
								"hue": 300, "saturation": 1, "value": 1}, 3000, Time_Profiles.ease_in_out)

	def _trigger_background(self):
		Options = {'fast_blinking': 0.2, 'wink': 0.2, 'kiss': 0.25, 'shake_yes': 0.1, 'dance': 0.1, 'hearts_flying': 0.25}
		choice = weighted_choice(list(Options.keys()), weights=Options.values())

		print(f"Happy background animation: {choice}")
		if choice == 'wink':
			AnimationBank.wink(self.State)
		elif choice == 'fast_blinking':
			for i in range(random.randint(4, 6)):
				AnimationBank.blink(self.State)
		elif choice == 'kiss':
			AnimationBank.kiss(self.State)
		elif choice == "shake_yes":
			AnimationBank.shake_yes(self.State, amount=random.randint(2,4))
		elif choice == "dance":
			AnimationBank.dancing(self.State, amount=random.randint(2,5))
		elif choice == 'hearts_flying':
			for i in range(random.randint(10, 50)):
				heart = Heart((random.randint(60, 180), random.randint(40, 80), random.uniform(-3*pi/4, -pi/4)))
				heart.scale(0.45)
				self.State.queue_particle(heart, (i**1.4)*100, dont_lock=True)
				del heart
		

class start_up(Emotion):
	def __init__(self, State, social_value=50, tired_value=50):
		super().__init__(State, social_value, tired_value)
		self.name = "start_up"

EMOTIONS = {'happy': Happy, 'angry': Angry, 'sad': Sad, 'okay': Okay, 'love': Love, 'horny': Horny}