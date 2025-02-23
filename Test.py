import network
import time
import _thread
import rp2
from secrets import SSID, PASSWORD
import machine

import senko
from Locker import ConditionalLock

OTA = senko.Senko(
  user="coencoensmeets",
  repo="Maja-Pico-code",
  branch="feature/OTA",
  files = ["Test.py"],
  debug = True,
  working_dir = None
)

country = "NL"

rp2.country(country)
network.country(country)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

def connect_normal():
	print("Connecting to network")

	start_time = time.time()
	while not wlan.isconnected() and time.time() - start_time < 100:
		print("Waiting for connection...")
		time.sleep(2)

	if wlan.isconnected():
		print("Connected to network")
	else:
		print("Failed to connect to network")
	print('network config:', wlan.ifconfig())

	if OTA.update():
		print("Updated to the latest version! Rebooting...")
		# machine.reset()
	time.sleep(2)
	wlan.disconnect()

def main_thread():
	connect_normal()

def second_thread():
	for (i) in range(10):
		print("Second thread-")
		time.sleep(2)

class test_lock():
	def __init__(self):
		self.lock = _thread.allocate_lock()

	def first_thread(self):
		with ConditionalLock(self.lock, timeout=5000) as aquired:
			if not aquired:
				return
			for (i) in range(6):
				print("First thread-")
				time.sleep(2)
		print("First thread done")

	def second_thread(self):
		with ConditionalLock(self.lock, timeout=5000) as aquired:
			if not aquired:
				print("First thread failed to aquire lock")
				return
			for (i) in range(5):
				print("Second thread-")
				time.sleep(2)
		print("Second thread done")

test = test_lock()
_thread.start_new_thread(test.first_thread, ())
time.sleep(1)
test.second_thread()
time.sleep(10)
# _thread.start_new_thread(second_thread, ())
# main_thread()