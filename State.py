from machine import Pin, I2C
from utime import sleep, time, sleep_ms, ticks_ms, ticks_diff
from datetime import datetime
from math import cos, sin, pi
import random
import _thread
import os
import json

from shapeDrawer import shapeDrawer
from Light import Lights
from Locker import ConditionalLock
from TimeProfiles import Time_Profiles

import gc9a01
import tft_config
from tft_config import SCREEN_SIZE
import gc
from Animation import StatusAnimator, EMOTIONS, start_up
from Screen import Screen
from Particle import Particle_Queue

CHANGE_TIME = 4500
COLOURS = {'BLACK': 0x0000, 'WHITE': 0xFFFF, 'RED': 0xF800, 'GREEN': 0x07E0, 'BLUE': 0x001F, 'CYAN': 0x07FF, 'MAGENTA': 0xF81F, 'YELLOW': 0xFFE0}

def get_user_id(mood_data_keys, user_id):
	if len(mood_data_keys)==1:
		return mood_data_keys[0]
	else:
		for key in mood_data_keys:
			if user_id!=key:
				return key

# Class that handles the next item to be processed
# Only one item that is waiting so Queue might be a bad name.
class Queue():
	def __init__(self):
		self.__queue = {}
		self.__lock = _thread.allocate_lock()

	def add(self, data, force = True):
		with self.__lock:
			if force:
				self.__queue.update(data)
			else:
				for key in data:
					if key not in self.__queue:
						self.__queue[key] = data[key]
	
	def get(self):
		with self.__lock:
			item = self.__queue.copy()
			self.__queue = {}
			return item
		
	def check(self):
		with self.__lock:
			return self.__queue != {}

class Emotion_Manager():
	def __init__(self, State):
		self.State = State
		self.emotion = start_up(State)
	
	def update(self, emotion=None, social_value=None, tired_value=None):
		changed = False
		if self.emotion.name != emotion:
			self.emotion = EMOTIONS[emotion](self.State, self.emotion.social_value, self.emotion.tired_value)
			# print("Emotion changed")
			changed = True
		if self.emotion.social_value != social_value:
			self.emotion.social_value = social_value
			# print("Social value changed")
			changed = True
		if self.emotion.tired_value != tired_value:
			self.emotion.tired_value = tired_value
			changed = True

		if changed:
			print(f"Changed to: {self.emotion}, Social: {self.emotion.social_value}, Tired: {self.emotion.tired_value}")

class StateSync():
	def __init__(self, user_id, LEDs, state):
		self.user_id = user_id
		self.LEDs = LEDs
		self.state = state
		self.queue = Queue()

		self.time_saved = datetime(2022, 7, 10)
		self.__block_get = False
		self.__post_retry_count = 0

		self.__lock = _thread.allocate_lock()

	def set_block_get(self, block:bool=False):
		with self.__lock:
			self.__block_get = block

	def get(self, webserver):
		result = webserver.get("all/maja")
		with self.__lock:
			if not self.queue.check() and not self.__block_get:
				success_value = result.get('success')
				# if success_value:
				# 	print(get_user_id(list(result['mood_data'].keys()), self.user_id))
				if success_value and all(key in result for key in ['light_data', 'mood_data', 'screen_data']):
					if get_user_id(list(result['mood_data'].keys()), self.user_id) in result['mood_data']:
						self.__change_face(result['mood_data'][get_user_id(list(result['mood_data'].keys()), self.user_id)]) 

					if (self.state.face.is_on != result['screen_data']['screen_on']):
						self.state.face.screen_turn(result['screen_data']['screen_on'])
						
					result_time = datetime.fromisoformat(result['light_data']['time'])
					if result_time > self.time_saved:
						self.time_saved = result_time
						self.__change_light(result['light_data'], force=self.time_saved==datetime(2022, 7, 10))
					
		return result

	def post(self, webserver):
		with self.__lock: 
			queue_item = self.queue.get()
			current_state = self.state.get_final_state().copy()
			if queue_item:
				success_value = True
				current_state.update(queue_item)
				if (key in ['hue', 'saturation', 'value'] for key in queue_item.keys()):
					send = {
						'hue': current_state['hue'],
						'saturation': current_state['saturation'],
						'value': current_state['value']
					}
					result = webserver.post("light/maja", send)
					success_value = success_value and result.get('success', False)
				
				if (key in ['screen_on'] for key in queue_item.keys()):
					send = {
						'screen_on': self.state.face.is_on
					}
					result = webserver.post("screen/maja", send)
					success_value = success_value and result.get('success', False)
				
				if success_value == False and self.__post_retry_count < 5:
					print(f"Posting failed: Will try again next time! ({result['message']})")
					self.__post_retry_count += 1
					self.queue.add(queue_item, force=False)
				elif success_value == False and self.__post_retry_count >= 5:
					self.__post_retry_count = 0
					self.time_saved = datetime(2022, 7, 10) # Force get update
					self.state.reset_animation()

	def __change_light(self, result, force = False):
		state = self.state.get_final_state()
		changes = {}
		for key in ['hue', 'saturation', 'value']:
			if round(state[key],3) != round(result[key],3) or force:
				changes[key] = result[key]

		if changes != {}:
			print(f"GET changes; {changes}")
			self.state.trigger_animation(changes, CHANGE_TIME, Time_Profiles.ease_in, force=force)
		
	def __change_face(self, result):
		self.state.Emotion.update(emotion=result['mood'], social_value=result['social_value'], tired_value=result['tired_value'])


class State():
	"""
	A class for drawing and animating a face on a display.
	
	Attributes:
		tft (gc9a01): The display object.
		width (int): The width of the face.
		height (int): The height of the face.
		animator (FaceAnimator): The animator object.
		current_status (dict): The current configuration of the face.
	
	Methods:
		draw_face(): Draws the face with the current configuration.
		trigger_animation(end_config, duration, timing_profile): Triggers a new animation.
		trigger_wait_animation(duration): Triggers a wait period as an animation.
		__draw_eyes(): Draws the eyes with the current configuration.
		__draw_mouth(): Draws the mouth with the current configuration.
	"""
	
	def __init__(self, lights=Lights()):
		self.__lock = _thread.allocate_lock()
		self.face = Screen()
		self.Lights = lights

		self.__animator = StatusAnimator()
		self.__current_status = {'x': SCREEN_SIZE[0]//2, 'y': SCREEN_SIZE[1]//2,
								'eye_open': 0.1, 'eyebrow_angle': 0, 'under_eye_lid': 0.4, 'left_right': 0, 
						   		'mouth_width': 40, 'mouth_y':0, 'smile': 0, 'cheeks': 0, 'smirk': 0,
								"hue": 0, "saturation": 1, "value": 0}
		
		self.__particles_queue = Particle_Queue()
		self.update_status_lamp()

		self.Emotion = Emotion_Manager(self)
	
	def draw_state(self, status=None, dont_lock=False):
		"""
		Draws the face with the current configuration.
		"""
		new_status = status
		with ConditionalLock(self.__lock, not dont_lock):
			if status:
				self.__current_status.update(status)
			else:
				new_status = self.__animator.animate_status(self.__current_status)
				Changed = False
				for keys in new_status.keys():
					if self.__current_status[keys] != new_status[keys]:
						Changed = True
					self.__current_status[keys] = new_status[keys]
				
				if not Changed and not self.__particles_queue.running():
					return
				
			self.face.draw_face(new_status, self.__current_status, self.__particles_queue.get_particles())
			if any(key in ['hue', 'saturation', 'value'] for key in new_status.keys()):
				self.__draw_lamp(new_status)


	def is_animation_active(self):
		"""
		Returns True if an animation is active or queued, False otherwise.
		"""
		with ConditionalLock(self.__lock):
			return self.__animator.is_animation_active() or self.__particles_queue.running()

	def trigger_animation(self, end_config, duration, timing_profile=Time_Profiles.linear, force = False, dont_lock=False):
		"""
		Triggers a new animation.

		:param end_config: The target configuration of the face at the end of the animation.
		:param duration: The duration of the animation in milliseconds.
		:param timing_profile: The timing function used to interpolate the animation.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			self.__animator.trigger_animation(end_config, duration, timing_profile, force=force)

	def trigger_wait_animation(self, duration, dont_lock=False):
		"""
		Triggers a wait period as an animation.

		:param duration: The duration of the wait period in milliseconds.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			self.__animator.trigger_wait_animation(duration)

	def spawn_particle(self, particle, dont_lock=False):
		"""
		Spawns a particle on the face.

		:param particle: The particle to spawn.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			self.__particles_queue.add_particle(particle)

	def queue_particle(self, particle, time_ms, dont_lock=False):
		with ConditionalLock(self.__lock, not dont_lock):
			self.__particles_queue.queue_particle(particle, time_ms)


	def reset_animation(self):
		"""
		Resets the animation queue and active status.
		"""
		with ConditionalLock(self.__lock):
			self.__animator.reset_queue()

	def check_animation_triggers(self):
		if (self.face.is_on):
			self.Emotion.emotion.check_triggers()

	def get_current_state(self, dont_lock=False):
		"""
		Returns the current state.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			self.update_status_lamp()
			return self.__current_status

	def get_final_state(self, dont_lock=False):
		"""
		Returns the final configuration.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			self.update_status_lamp()
			return self.__animator.get_final_status(self.__current_status)
		
	def get_final_time(self, dont_lock=False):
		"""
		Returns the final time.
		"""
		with ConditionalLock(self.__lock, not dont_lock):
			return self.__animator.get_final_time()
		
	def save_state(self):
		self.update_status_lamp()
		gc.collect()
		print("Waiting")
		sleep(2)
		print(f"Test: {self.__current_status}")
		with open('state.json', 'w') as file:
			json.dump(self.__current_status, file)
		print(f"Saved state: {self.__current_status}")
	
	def load_state(self, reset=True):
		if reset:
			try:
				with open('state.json', 'r') as file:
					self.__current_status = json.load(file).copy()
					print(f"Current state: {self.__current_status}")
					self.draw_state(self.__current_status, dont_lock=True)
					print(f"Loaded state: {self.__current_status}")
			except OSError:
				print("No state file found!")
		else:
			self.__make_black = True
			EMOTIONS['happy'](self, 50, 50)

	def update_status_lamp(self, dont_lock=False):
		"""
		Updates the status of the lamp.
		"""
		colour = self.Lights.get_hsv(dont_lock=dont_lock)
		self.__current_status['hue'] = colour[0]
		self.__current_status['saturation'] = colour[1]
		self.__current_status['value'] = colour[2]

	def __draw_lamp(self, new_status={}):
		"""
		Draws the lamp with the current configuration.
		"""
		colour = self.Lights.get_hsv()

		new_colour = [new_status.get('hue', colour[0]), new_status.get('saturation', colour[1]), new_status.get('value', colour[2])]
		self.Lights.set_hsv(new_colour)

if __name__ == '__main__':
	import machine
	import random

	tft = tft_config.config(tft_config.TALL)
	tft.init()
	tft.fill(gc9a01.BLACK)
	Light = Lights(N=8, brightness=1, pin=machine.Pin(2))
	state = State(Light)
	gc.collect()
	bpp = 2