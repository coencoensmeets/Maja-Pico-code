import network
import time
import json
import gc
import urequests as rq
import socket
from Light import Lights
import machine

MAX_DELTA_T = 20
SLEEP_TIME = 2
RETRY_INTERVAL = 1

class Webserver():
	"""
	A class to manage WiFi connections and HTTP requests for a specific user.

	Attributes:
		__base_url (str): The base URL for the webserver to which HTTP requests are sent.
		__user_id (str): The unique identifier for the user.
		__wlan (network.WLAN): The WLAN interface for managing WiFi connections.
		__ssid (str): The SSID of the WiFi network to connect to.
		__password (str): The password for the WiFi network.

	Methods:
		__init__(self, user_id, ssid, password, base): Initializes a new Webserver instance.
		isconnected(self): Checks if the device is currently connected to a WiFi network.
		connect(self): Attempts to connect to the specified WiFi network.
		disconnect(self): Disconnects from the currently connected WiFi network.
		get(self, subdomain): Placeholder for a method to perform GET requests.
		post(self, subdomain, data): Initiates a POST request to a specified subdomain with given data.
	"""

	def __init__(self, user_id, ssid, password, base = 'http://coencoensmeets.pythonanywhere.com/Send/'):
		"""
		Initializes a new Webserver instance with user credentials and WiFi settings.

		Parameters:
			user_id (str): The unique identifier for the user.
			ssid (str): The SSID of the WiFi network to connect to.
			password (str): The password for the WiFi network.
			base (str, optional): The base URL for the webserver. Defaults to 'http://coencoensmeets.pythonanywhere.com/Send/'.
		"""
		self.__base_url = base
		self.__user_id = user_id
		self.__wlan = network.WLAN(network.STA_IF)
		self.__ssid = ssid
		self.__password = password

	def isconnected(self):
		"""
		Checks if the device is currently connected to a WiFi network.

		Returns:
			bool: True if connected, False otherwise.
		"""
		return self.__wlan.isconnected()

	def connect(self):
		"""
		Attempts to connect to the specified WiFi network.

		Returns:
			bool: True if the connection was successful, False otherwise.
		"""
		t_start = time.time()

		self.__wlan.active(True)
		if self.__wlan.isconnected():
			self.__wlan.disconnect()
			time.sleep(SLEEP_TIME)
		time.sleep_ms(500)
		for i in range(0,5):
			try:
				self.__wlan.connect(self.__ssid, self.__password)
				break
			except:
				if i == 4:
					print("Failed to connect to network")
					return False
					# raise Exception("Failed to connect to network")
				time.sleep(RETRY_INTERVAL)
		self.__wlan.config(pm=0xa11140)
		while not (self.__wlan.isconnected()) and (time.time()-t_start<MAX_DELTA_T):
			print(f"Connecting to network: {time.time()-t_start}/20s", end="\r")
			time.sleep(1)
		print("")
	
		del t_start
		is_connected = self.__wlan.isconnected()
		if is_connected:
			print("Connection successful")
			print("IP address:", self.__wlan.ifconfig()[0])
		else:
			print("Connection failed")
		time.sleep(SLEEP_TIME)
		return is_connected

	def disconnect(self):
		"""
		Disconnects from the currently connected WiFi network.
		"""
		self.__wlan.disconnect()
		self.__wlan.active(False)
		print("Wifi disconnected")

	def get(self, subdomain:str, data:dict=None):
		"""
		Initiates a POST (to get data) request to a specified subdomain with optional data.

		Parameters:
			subdomain (str): The subdomain to append to the base URL for the POST request.
			data (dict, optional): Additional data to be sent with the POST request. Defaults to None.
		"""
		url = self.__base_url + f"/api/v1/{subdomain}/get"
		headers = {'Content-Type': 'application/json'}
		if data is not None:
			data['user_id'] = self.__user_id
		else:
			data = {'user_id': self.__user_id}
		# todo: Replace with version number
		data['Sender'] = 'Lamp'
		# print(f"(GET) url: {url}, data: {data}")
		try:
			gc.collect()
			# print(f'Data left: {gc.mem_free()}')
			response = rq.post(url, json=data, headers=headers)
			if response is None:
				print("Failed to get data: No response")
				return_data = {'success': False, 'message': 'No response'}
			elif response.status_code < 200 or response.status_code >= 300:
				print(f"Failed to get data: HTTP {response.status_code}")
				return_data = {'success': False, 'message': f'HTTP {response.status_code}'}
			else:
				return_data = response.json()
			response.close()
		except Exception as e:
			# print(f"Error: {e}")
			# if not('ENOMEM' in str(e)):
			# 	print(f"Failed to get data: {e}")
			return_data = {'success': False, 'message': str(e)}

		return return_data
		
	def post(self, subdomain:str, data:dict)->dict:
		"""
		Initiates a POST request to a specified subdomain with given data.

		Parameters:
			subdomain (str): The subdomain to append to the base URL for the POST request.
			data (dict): The data to be sent in the POST request.
		"""
		url = self.__base_url + f"/api/v1/{subdomain}/post"
		headers = {'Content-Type': 'application/json'}
		data['user_id'] = self.__user_id  # Add 'user_id' to the data
		# todo: Replace with version number
		data['Sender'] = 'Lamp'
		try:
			gc.collect()
			response = rq.post(url, json=data, headers=headers)  # Make POST request
			if response is None:
				print("Failed to post data: No response")
				return_data = {'success': False, 'message': 'No response'}
			elif response.status_code < 200 or response.status_code >= 300:
				print(f"Failed to post data: HTTP {response.status_code}")
				return_data = {'success': False, 'message': f'HTTP {response.status_code}'}
			else:
				return_data =  response.json()
			response.close()
		except Exception as e:
			return_data = {'success': False, 'message': str(e)}

		return return_data

	def test_connection(self):
		"""
		Tests the device's ability to connect to the internet by making a GET request to a known website.

		This method attempts to connect to "http://www.example.com" and checks if the HTTP status code of the response is 200, indicating a successful connection. If the connection is successful, it prints a success message and returns True. If the connection fails or an error occurs, it prints an error message and returns False.

		Returns:
			bool: True if the connection test is successful, False otherwise.
		"""
		try:
			response = rq.get("http://www.example.com", timeout=4)
			if response.status_code == 200:
				print("Connection test successful")
				return True
			else:
				print("Connection test failed")
				return False
		except Exception as err:
			print("Error testing connection:", err)
			return False
		
html_success = """<!DOCTYPE html>
<html>
<head>
	<title>Maja</title>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<style>
		body {
			font-family: Arial, sans-serif;
			margin: 0;
			padding: 0;
			background-color: #C0F9B3FF;
		}
		.container {
			width: 80%;
			margin: 0 auto;
			padding: 20px;
			background-color: #fff;
			border-radius: 5px;
			box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
			margin-top: 50px;
		}
	</style>
</head>
<body>
	<div class="container">
		<h1>Data has been passed to Maja</h1>
		<p>Maja will now try to connect. It will blink green if it worked. If it didn't connect correctly, it will blink red.</p>
	</div>
</body>
</html>
"""

html_fail = """<!DOCTYPE html>
<html>
<head>
	<title>Maja</title>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<style>
		body {
			font-family: Arial, sans-serif;
			margin: 0;
			padding: 0;
			background-color: #E49696FF;
		}
		.container {
			width: 80%;
			margin: 0 auto;
			padding: 20px;
			background-color: #fff;
			border-radius: 5px;
			box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
			margin-top: 50px;
		}
	</style>
</head>
<body>
	<div class="container">
		<h1>Connection failed</h1>
		<p>Something went wrong. Try again in a bit.</p>
	</div>
</body>
</html>
"""

class Local_Server():
	"""
	A class to manage the local server for the lamp to setup the WiFi connection.
	"""

	def __init__(self, Lights=None):
		"""
		Initializes a new Local_Server instance.
		"""
		self.Lights = Lights

		self.setup_network()
		self.website()

	def remove_network(self):
		ap = network.WLAN(network.AP_IF)
		ap.active(False)
		print("AP Mode Is Deactivated")

	def setup_network(self):
		ap = network.WLAN(network.AP_IF)
		ap.config(essid='Maja', security=0)
		ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
		time.sleep_ms(500)
		ap.active(True)

		while ap.active() == False:
			pass
		print('AP Mode Is Active, You can Now Connect')
		print('IP Address To Connect to:: ' + ap.ifconfig()[0])

	def blink(self, colour, N=0.3, T=4):
		if self.Lights is not None:
			self.Lights.blink(colour, n=N, T=T)

	def website(self):
		"""
		Displays a simple HTML webpage with a welcome message.
		"""
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.bind(('', 80))
		s.listen(5)

		if self.Lights:
			self.Lights.set_hsv((230, 1, 1))

		while True:
			conn, addr = s.accept()
			print('Got a connection from %s' % str(addr))
			request = conn.recv(1024)
			request = str(request)
			print(f"Content = {request}")

			start = request.find('?apply=') + len('?apply=')
			end = request.find('?end')
			if start == -1 or end == -1:
				self.show_page(conn, html_fail)
			else:
				json_string = request[start:end]
				print(f"json_string: {json_string}")
				try:
					json_dict = json.loads(json_string.replace("%22", '"'))
				except ValueError:
					json_dict = None

				if json_dict is None:
					print("Failed to parse JSON")
					self.show_page(conn, html_fail)
				else:
					user_id = json_dict.get('user_id', None)
					ssid = json_dict.get('ssid', None)
					password = json_dict.get('password', None)
					print(f"user_id: {user_id}, SSID: {ssid}, Password: {password}")

					if user_id is None or ssid is None or password is None:
						self.show_page(conn, html_fail)
					else:
						self.show_page(conn, html_success)
						ws = Webserver(user_id=user_id, ssid=ssid, password=password)
						ws.connect()
						if ws.isconnected():
							print("Connected successfully")
							Secrets().save_secrets(json_dict)
							self.blink(120)
							machine.reset()
							break
						else:
							print("Failed to connect")
							self.blink(0)

	def show_page(self, conn, html):
		"""
		Sends an HTML page to the client.

		Parameters:
			conn (socket): The socket connection to the client.
			html (str): The HTML content to send to the client.
		"""
		response = 'HTTP/1.1 200 OK\n'
		response += 'Content-Type: text/html\n'
		response += '\n'
		response += html
		conn.send(response)
		conn.close()

	def parse_query_string(self, query_string):
		"""
		Parses the query string into a dictionary.
		"""
		params = {}
		pairs = query_string.split('&')
		for pair in pairs:
			if '=' in pair:
				key, value = pair.split('=')
				params[key] = value
		return params

class Secrets():
	def __init__(self, file_name='secrets.json'):
		self.file_name = file_name
	
	def get_secrets(self):
		secrets = self.load_secrets()
		return secrets.get('user_id', None), secrets.get('ssid', None), secrets.get('password', None)

	def load_secrets(self):
		try:
			with open(self.file_name, 'r') as file:
				secrets = json.load(file)
		except OSError:
			secrets = {}
		return secrets
	
	def save_secrets(self, secrets):
		with open(self.file_name, 'w') as file:
			json.dump(secrets, file)

	def reset_secrets(self):
		self.save_secrets({})
		machine.reset()

if __name__ == "__main__":
	# ws = Webserver(id=1, ssid = "Ziggo5483466", password="zh6vjQxpBxjt")
	# ws.connect()
	# ws.test_connection()
	# ws.disconnect()
	print(f"Secrets: {Secrets().get_secrets()}")
	Test = Local_Server(Lights(N=8, brightness=1, pin=machine.Pin(2)))