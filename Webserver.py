import network
import time
import json
import gc
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
		__version (int): The version number of the software.

	Methods:
		__init__(self, user_id, ssid, password, base): Initializes a new Webserver instance.
		isconnected(self): Checks if the device is currently connected to a WiFi network.
		connect(self): Attempts to connect to the specified WiFi network.
		disconnect(self): Disconnects from the currently connected WiFi network.
		get(self, subdomain): Placeholder for a method to perform GET requests.
		post(self, subdomain, data): Initiates a POST request to a specified subdomain with given data.
	"""

	def __init__(self, user_id, ssid, password, base='https://thomasbendington.pythonanywhere.com', version="-1"):
		"""
		Initializes a new Webserver instance with user credentials and WiFi settings.

		Parameters:
			user_id (str): The unique identifier for the user.
			ssid (str): The SSID of the WiFi network to connect to.
			password (str): The password for the WiFi network.
			base (str, optional): The base URL for the webserver. Defaults to 'https://thomasbendington.pythonanywhere.com'.
		"""
		self.__base_url = base
		self.__user_id = user_id
		self.__wlan = network.WLAN(network.STA_IF)
		self.__ssid = ssid
		self.__password = password
		self.__version = version

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
		for i in range(0, 5):
			try:
				self.__wlan.connect(self.__ssid, self.__password)
				break
			except:
				if i == 4:
					print("Failed to connect to network")
					return False
				time.sleep(RETRY_INTERVAL)
		self.__wlan.config(pm=0xa11140)
		while not (self.__wlan.isconnected()) and (time.time() - t_start < MAX_DELTA_T):
			print(f"Connecting to network: {time.time() - t_start}/20s", end="\r")
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

	def get(self, subdomain: str, data: dict = None):
		"""
		Initiates a POST (to get data) request to a specified subdomain with optional data using raw sockets.

		Parameters:
			subdomain (str): The subdomain to append to the base URL for the POST request.
			data (dict, optional): Additional data to be sent with the POST request. Defaults to None.
		"""
		url = self.__base_url
		host = url.replace("http://", "").replace("https://", "").split("/")[0]  # Extract domain
		path = f"/api/v1/{subdomain}/get"
		port = 80  # Change to 443 for HTTPS (MicroPython lacks native TLS)

		if data is None:
			data = {}
		data['user_id'] = self.__user_id
		data['version'] = self.__version
		json_data = json.dumps(data)

		request = (
			f"POST {path} HTTP/1.1\r\n"
			f"Host: {host}\r\n"
			f"Content-Type: application/json\r\n"
			f"Content-Length: {len(json_data)}\r\n"
			f"Connection: close\r\n\r\n"
			f"{json_data}"
		)

		sock = None
		try:
			gc.collect()

			# Open socket connection
			addr = socket.getaddrinfo(host, port)[0][-1]
			sock = socket.socket()
			sock.settimeout(10)
			sock.connect(addr)
			sock.send(request.encode())


			response = b""
			while True:
				chunk = sock.recv(1024)
				if not chunk:
					break
				response += chunk

			response_str = response.decode()
			headers, body = response_str.split("\r\n\r\n", 1)

			# Check HTTP status code
			status_line = headers.split("\r\n")[0]
			status_code = int(status_line.split(" ")[1])
			if status_code < 200 or status_code >= 300:
				print(f"Failed to get data: HTTP {status_code}")
				return {'success': False, 'message': f'HTTP {status_code}'}
			
			return json.loads(body)

		except Exception as e:
			print(f"Failed to get data: {e}")
			return {'success': False, 'message': str(e)}

		finally:
			if sock and isinstance(sock, socket.socket):
				sock.close()
				del sock
			gc.collect()

	def post(self, subdomain: str, data: dict) -> dict:
		"""
		Initiates a POST request to a specified subdomain with given data using raw sockets.

		Parameters:
			subdomain (str): The subdomain to append to the base URL for the POST request.
			data (dict): The data to be sent in the POST request.

		Returns:
			dict: The response from the server in JSON format or an error message.
		"""
		url = self.__base_url
		host = url.replace("http://", "").replace("https://", "").split("/")[0]  # Extract domain
		path = f"/api/v1/{subdomain}/post"
		port = 80  # Change to 443 for HTTPS (MicroPython lacks native TLS)

		# Add required fields
		data['user_id'] = self.__user_id
		data['version'] = self.__version
		json_data = json.dumps(data)

		request = (
			f"POST {path} HTTP/1.1\r\n"
			f"Host: {host}\r\n"
			f"Content-Type: application/json\r\n"
			f"Content-Length: {len(json_data)}\r\n"
			f"Connection: close\r\n\r\n"
			f"{json_data}"
		)

		sock = None
		try:
			gc.collect()

			addr = socket.getaddrinfo(host, port)[0][-1]
			sock = socket.socket()
			sock.settimeout(10)
			sock.connect(addr)

			sock.send(request.encode())

			response = b""
			while True:
				chunk = sock.recv(1024)
				if not chunk:
					break
				response += chunk

			response_str = response.decode()
			headers, body = response_str.split("\r\n\r\n", 1)

			status_line = headers.split("\r\n")[0]
			status_code = int(status_line.split(" ")[1])
			if status_code < 200 or status_code >= 300:
				print(f"Failed to post data: HTTP {status_code}")
				return {'success': False, 'message': f'HTTP {status_code}'}

			return json.loads(body)

		except Exception as e:
			print(f"Failed to post data: {e}")
			return {'success': False, 'message': str(e)}

		finally:
			if sock and isinstance(sock, socket.socket):
				sock.close()
				del sock
			gc.collect()

	def test_connection(self):
		"""
		Tests the device's ability to connect to the internet by making a GET request to a known website.

		This method attempts to connect to "http://www.example.com" and checks if the HTTP status code of the response is 200, indicating a successful connection. If the connection is successful, it prints a success message and returns True. If the connection fails or an error occurs, it prints an error message and returns False.

		Returns:
			bool: True if the connection test is successful, False otherwise.
		"""
		try:
			time_start = time.ticks_ms()
			response = self.get("all/maja")
			print(f"Time to get: {time.ticks_ms() - time_start}")
			if response.get('success', False):
				print(f"Response: {response}")
				print("Connection test successful")
				return True
			else:
				print("Connection test failed")
				return False
		except Exception as e:
			print(f"Connection test failed: {e}")
			return False
		finally:
			gc.collect()
		
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

			start = request.find('?input=') + len('?input=')
			end = request.find('?end')
			if start == -1 or end == -1:
				self.show_page(conn, html_fail)
			else:
				json_string = request[start:end]
				print(f"json_string: {json_string}")
				try:
					print(json_string.replace("%22", '"').replace("%20", ""))
					json_dict = json.loads(json_string.replace("%22", '"').replace("%20", ""))
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
						Secrets().save_secrets(json_dict)
						machine.reset()

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
	ws = Webserver(user_id=1, ssid = "Ziggo5483466", password="zh6vjQxpBxjt")
	ws.connect()
	ws.test_connection()
	ws.disconnect()
	# print(f"Secrets: {Secrets().get_secrets()}")
	# Test = Local_Server(Lights(N=8, brightness=1, pin=machine.Pin(2)))