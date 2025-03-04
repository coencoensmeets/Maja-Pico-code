import _thread
from time import ticks_ms, sleep, sleep_ms, ticks_diff
import machine
import gc
import json
import os
import micropython
import senko

from DHT_Sensor import climate_sensor
from Touch_Sensor import TouchManager
from Light import Lights
from Timers import WatchDog, Periodic
from State import State, StateSync, Emotion_Manager
from TimeProfiles import Time_Profiles
from Webserver import Webserver, Secrets, Local_Server

import tft_config

TOGGLE_TIME = 1500
VERSION = "1.1.7"

def file_exists(filepath):
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False

class main_system():
	def __init__(self, safety_switch=True):
		gc.collect()
		micropython.alloc_emergency_exception_buf(100)
		self.LEDS = Lights(N=8, brightness=1, pin=machine.Pin(12))
		self.state = State(self.LEDS)

		self.safety_switch = safety_switch
		gc.collect()
		self.dht20 = climate_sensor(scl=1, sda=0, rolling_avg_factor=1e3)
		self.WD = WatchDog(30e3, stop_routine=self.stop_routine)

		gc.collect()
		USER_ID, SSID, PASSWORD = Secrets().get_secrets()
		if None in (USER_ID, SSID, PASSWORD):
			print("No secrets found! Using local server!")
			self.state.load_state(reset=False)
			self.state.draw_state()
			Local_Server(self.LEDS)
		self.ws = Webserver(user_id=USER_ID, ssid = SSID, password=PASSWORD, base = "https://thomasbendington.pythonanywhere.com", version = VERSION)

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
			self.WD.update_WDT()
			print("Start save state")
			print(f"Memory: {micropython.mem_info(0)}")
			self.state.save_state()
			self.WD.update_WDT()
			print("Ended safe state\n Start set reset")
			print(f"Memory: {micropython.mem_info(1)}")
			print(f"Killing all threads! (wait 2s)")
			sleep_ms(2000)
			if self.safety_switch:
				machine.reset()
			# sleep_ms(2000*1000)

	def __startup(self):
		# print("--- Startup ---")
		gc.collect()
		reset = file_exists("state.json")
		print(f"Reset: {reset}\n")
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

		print("Startup complete!\n----------------\n")

	def __update(self):
		OTA = senko.Senko(
			user="coencoensmeets",
			repo="Maja-Pico-code",
			branch="feature/Bug_fixes",
			files = ["main_system.py", "Animation.py", "Particle.py", "Screen.py", "State.py", "tft_config.py"],
			debug = True,
			working_dir = None
		)
		if OTA.update():
			print("Updated to the latest version! Rebooting...")
			self.WD.kill()
		else:
			print("No updates found!")

	def __still_up(self):
		print("Sensor thread still running!")

	def __sensor_thread(self):
		print("Start sensor thread")
		touch_manager = TouchManager()
		up_periodic = Periodic(func=self.__still_up, freq=1/10)
		Hue_Changing = False
		touch_state = {"left": 0, "right": 0}  # Initialize with 0 for none

		while self.WD.running():
			t_start = ticks_ms()
			up_periodic.call_func()
			self.WD.update('sensor')
			touch_manager.update_and_manage_state(touch_state)

			if Hue_Changing and touch_state['left'] < 1000:
				Hue_Changing = False
				colour = self.LEDS.get_hsv()
				self.state.draw_state({'hue': colour[0], 'saturation': colour[1], 'value': colour[2]})
				self.state_sync.queue.add({'hue': colour[0], 'saturation': colour[1], 'value': colour[2]})
				self.state_sync.set_block_get(False)
				self.state.save_status = True

			if self.state.is_animation_active():
				self.state.draw_state()

			if touch_state['left'] == -2: #State: toggle light (Double touch right)
				print("Light action: Toggle")
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
				self.state.save_status = True
			elif touch_state['left'] > 1000: #State: Change colour (Hold right)
				print("Light action: Change colour")
				if not Hue_Changing:
					Hue_Changing = True
					self.state_sync.set_block_get(True)
					colour = self.LEDS.get_hsv()
					if colour[1] != 1 or colour[2] != 1:
						self.state.trigger_animation({"saturation": 1, "value": 1}, TOGGLE_TIME, Time_Profiles.ease_in, force=True)
				self.LEDS.increase_hue(360/4)
			elif touch_state['right'] == -2: #State: Change screen (Double touch Left)
				print("Light action: Change screen")
				self.state.face.screen_toggle()
				self.state_sync.queue.add({'screen_on': 0})
				self.state.save_status = True
			elif touch_state['right'] == -5: #State: Reset (Coding) (Hold left)
				print("Resetting secrets!")
				Secrets().reset_secrets()
				print(f"Secrets reset! Restarting in 2s")
				sleep(2)
				self.WD.kill()
			elif touch_state['left'] == -5: #State: Reset (Double tap left)
				print("Resetting state!")
				gc.collect()
				sleep(2)
				print("Start renaming boot.py")
				os.rename("boot.py", "_boot.py")
				Lights(N=8, brightness=1, pin=machine.Pin(2)).set_hsv((0,1,1))
				self.WD.kill()
			
			if (ticks_diff(ticks_ms(), t_start) > 100):
				print(f"Time taken (Sensor loop): {ticks_diff(ticks_ms(), t_start)}")

		print("Sensor thread is going to kill the server thread!")
		self.WD.kill()

	def __server_thread(self):
		# print("Start server thread")
		dht20_periodic = Periodic(func=self.dht20.update_server, freq=1/(60), webserver=self.ws)
		light_periodic = Periodic(func=self.state_sync.get, freq=1, webserver=self.ws)
		animation_periodic = Periodic(func=self.state.check_animation_triggers, freq=1/2)
		garbage_periodic = Periodic(func=gc.collect, freq=1/5)
		update_periodic = Periodic(func=self.__update, freq=1/(60*10))
		save_state_periodic = Periodic(func=self.state.check_save_state, freq=1/(10))

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
			
			update_periodic.call_func()

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

			animation_periodic.call_func()
			save_state_periodic.call_func()

			t_end = ticks_ms()
			if (ticks_diff(t_end, t_start) > 200):
				print(f"Time taken (Server loop): {ticks_diff(t_end, t_start)}")
		print("Server thread is going to kill the sensor thread!")
		self.WD.kill()

	def __Test():
		print("Memory allocated:", gc.mem_alloc(), "bytes")
		print("Memory free:", gc.mem_free(), "bytes")

if __name__ == '__main__':
	system = main_system(safety_switch=False)
	system.start_threads()