import _thread
from time import ticks_ms, sleep, sleep_ms, ticks_diff
import machine
import gc
import json
import os
import micropython

from DHT_Sensor import climate_sensor
from Touch_Sensor import TouchManager
from Light import Lights
from Timers import WatchDog, Periodic
from State import State, StateSync, Emotion_Manager
from TimeProfiles import Time_Profiles
from Webserver import Webserver

import tft_config
from secrets import USER_ID, SSID, PASSWORD

TOGGLE_TIME = 1500

class ResetDetector():
	def __init__(self):
		self.reset = False
	
	def check(self):
		try:
			with open('reset.json', 'r') as file:
				file_result = json.load(file).copy()
				self.reset = file_result.get('reset', False)
				os.remove('reset.json')
		except OSError:
			pass
		return self.reset

	def set_reset(self):
		with open('reset.json', 'w') as file:
			json.dump({'reset': True}, file)
		print("Hard reset set!")

class main_system():
	def __init__(self, safety_switch=True):
		gc.collect()
		self.LEDS = Lights(N=8, brightness=1, pin=machine.Pin(2))
		self.state = State(self.LEDS)

		self.safety_switch = safety_switch
		gc.collect()
		self.dht20 = climate_sensor(scl=1, sda=0, rolling_avg_factor=1e3)
		self.WD = WatchDog(30e3, stop_routine=self.stop_routine)

		gc.collect()
		self.ws = Webserver(user_id=USER_ID, ssid = SSID, password=PASSWORD, base = "https://thomasbendington.pythonanywhere.com")

		self.state_sync = StateSync(USER_ID, self.LEDS, self.state)

		self.__lock = _thread.allocate_lock()

		if self.safety_switch:
			try:
				self.__startup()
			except Exception as e:
				print("Error during startup:", e)
		else:
			print("Safety switch disabled!")
			self.__startup()

	def start_threads(self):
		_thread.start_new_thread(self.__sensor_thread, ())
		if self.safety_switch:
			try:
				self.__server_thread()
			except Exception as e:
				print("Error during startup:", e)
				self.stop_routine()
		else:
			print("Safety switch disabled!")
			self.__server_thread()
		
	def stop_routine(self):
		with self.__lock:
			print("Start disconnecting")
			self.ws.disconnect()
			print("Start save state")
			self.state.save_state()
			print("Ended safe state\n Start set reset")
			print(f"Memory: {micropython.mem_info(1)}")
			ResetDetector().set_reset()
			print(f"Killing all threads! (wait 2s)")
			sleep_ms(2000)
			if self.safety_switch:
				machine.reset()
			# sleep_ms(2000*1000)

	def __startup(self):
		# print("--- Startup ---")
		gc.collect()
		reset = ResetDetector().check()
		# print(f"Reset (Not putting cable in!): {reset}\n")
		self.state.load_state(reset=reset)
		if not reset:
			self.state.draw_state()
		print("Test state loaded")

		if self.safety_switch:
			try:
				os.rename("_boot.py", "boot.py")
			except OSError:
				pass
			print("\nRebooting turned on!\n")

		print(micropython.mem_info(1))

		print("Startup complete!\n----------------\n")

	def __still_up(self):
		print("Sensor thread still running!")

	def __sensor_thread(self):
		print("Start sensor thread")
		touch_manager = TouchManager()
		up_periodic = Periodic(func=self.__still_up, freq=1/10)
		Hue_Changing = False

		while self.WD.running():
			up_periodic.call_func()
			self.WD.update('sensor')
			touch_state = touch_manager.update_and_manage_state()

			if Hue_Changing and touch_state['left'] < 1000:
				Hue_Changing = False
				colour = self.LEDS.get_hsv()
				self.state.draw_state({'hue': colour[0], 'saturation': colour[1], 'value': colour[2]})
				self.state_sync.queue.add({'hue': colour[0], 'saturation': colour[1], 'value': colour[2]})
				self.state_sync.set_block_get(False)

			if self.state.is_animation_active():
				self.state.draw_state()

			if touch_state['left'] == -2: #State: toggle light (Double touch right)
				colour = self.LEDS.get_hsv()
				print(f"Colour: {colour}")
				if colour[2] == 0:
					print("Light action: Turn on")
					self.state.trigger_animation({"value": 1}, TOGGLE_TIME, Time_Profiles.ease_out, force=True)
					self.state_sync.queue.add({'value': 1})
				else:
					print("Light action: Turn off")
					self.state.trigger_animation({"value": 0}, TOGGLE_TIME, Time_Profiles.ease_out, force=True)
					self.state_sync.queue.add({'value': 0})
			elif touch_state['left'] > 1000: #State: Change colour (Hold right)
				if not Hue_Changing:
					Hue_Changing = True
					self.state_sync.set_block_get(True)
					colour = self.LEDS.get_hsv()
					if colour[1] != 1 or colour[2] != 1:
						self.state.trigger_animation({"saturation": 1, "value": 1}, TOGGLE_TIME, Time_Profiles.ease_in, force=True)
				self.LEDS.increase_hue(360/4)

			elif touch_state['right'] == -2: #State: Change brightness (Double tap right)
				self.state.face.screen_toggle()
				self.state_sync.queue.add({'screen_on': 0})
			elif touch_state['right'] > 3000: #State: Reset (Coding) (Hold left)
				self.WD.kill()

			elif touch_state['left'] == -5: #State: Reset (Double tap left)
				gc.collect()
				sleep(2)
				print("Start renaming boot.py")
				os.rename("boot.py", "_boot.py")
				Lights(N=8, brightness=1, pin=machine.Pin(2)).set_hsv((0,1,1))
				self.WD.kill()
			
			# if (ticks_diff(ticks_ms(), t_start) > 20):
			# 	print(f"Time taken (Sensor loop): {ticks_diff(ticks_ms(), t_start)}")

		print("Sensor Thread Stopped!\nKilling all threads!")
		self.WD.kill()

	def __server_thread(self):
		# print("Start server thread")
		dht20_periodic = Periodic(func=self.dht20.update_server, freq=1/(60), webserver=self.ws)
		light_periodic = Periodic(func=self.state_sync.get, freq=1, webserver=self.ws)
		animation_periodic = Periodic(func=self.state.check_animation_triggers, freq=1)
		garbage_periodic = Periodic(func=gc.collect, freq=1/5)
		Test_periodic = Periodic(func=self.__Test, freq=1)

		get_failed_count = 0

		while self.WD.running():
			t_start = ticks_ms()
			self.WD.update('main')
			self.dht20.measure()
			garbage_periodic.call_func()

			if not self.ws.isconnected():
				Success = self.ws.connect()
				if not Success:
					self.WD.kill()

			server_return = dht20_periodic.call_func(force_update=dht20_periodic.bypass_timing)
			if server_return:
				success_value = server_return.get('success')
				if success_value == False:
					dht20_periodic.bypass_timing = True
					print("Run next time!")
				print(f"(Main): {server_return}")

			gc.collect()
			server_return = light_periodic.call_func()
			if server_return:
				if server_return.get('success') == False:
					get_failed_count += 1
					gc.collect()
					print(f"Memory free: {gc.mem_free()} fail counter: {get_failed_count} - {server_return.get('message', '')}")
					if get_failed_count == 5:
						print(f"GET failed 5 times: Restarting Wifi: {server_return.get('message', '')}")
						print(f"Memory: {micropython.mem_info(1)}")
						self.ws.disconnect()
						sleep(2)
					elif get_failed_count > 10:
						print(f"GET failed 10 times: Doing a restart!")
						self.WD.kill()
				elif get_failed_count > 0:
					get_failed_count = 0

			if self.state_sync.queue.check():
				self.state_sync.post(webserver=self.ws)

			# Test_periodic.call_func()

			animation_periodic.call_func()

			t_end = ticks_ms()
			if (ticks_diff(t_end, t_start) < 2000):
				sleep_ms(2000-ticks_diff(t_end, t_start))
			# print(f"Time taken (Server loop): {ticks_diff(t_end, t_start)}")
		print("Server thread is going to kill the sensor thread!")
		self.WD.kill()

	def __Test():
		print("Memory allocated:", gc.mem_alloc(), "bytes")
		print("Memory free:", gc.mem_free(), "bytes")

if __name__ == '__main__':
	system = main_system(safety_switch=False)
	system.start_threads()