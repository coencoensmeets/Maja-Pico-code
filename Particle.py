from math import sin, cos, pi
from utime import ticks_ms, ticks_diff
import random

def manhattan_distance(point_1, point_2):
	return (abs(point_1[0]-point_2[0]) + abs(point_1[1]-point_2[1]))

def distance(point_1, point_2):
	return ((point_1[0]-point_2[0])**2 + (point_1[1]-point_2[1])**2)**0.5


class Particle_Queue():
	def __init__(self):
		self.__particles = []
		self.__particle_queue = {}

	def get_particles(self):
		self.__check_queue()
		return self.__particles

	def add_particle(self, particle):
		self.__particles.append(particle)

	def queue_particle(self, particle, time_ms):
		self.__particle_queue[particle] = {'time': time_ms, 'start_time': ticks_ms()}

	def running(self):
		self.__check_queue()
		return len(self.__particles)>0

	def __check_queue(self):
		for particle, time_dict in self.__particle_queue.items():
			if ticks_diff(ticks_ms(), time_dict['start_time'])>=time_dict['time']:
				particle.reset_time()
				self.__particles.append(particle)
				self.__particle_queue.pop(particle, None)
		

class Particle():
	def __init__(self, spawn, center, points, radii, colour=1):
		"""
		spawn: (x, y, orientation)
		center: (x, y)
		points: list of points
		radii: list of radii
		"""

		self.points = list(points)
		self.__points_org = list(points)
		self.radii = list(radii)
		self.__radii_org = list(radii)
		self.__colour = colour

		self.__scale = 1
		self.__center = center
		self.__location = spawn[0:2]
		self.__orientation = spawn[2]  # Initial orientation in radians
		self.velocities = (lambda t: 40, lambda t: sin(t*4))  # (forward_velocity, angular_velocity)

		self.__saved_time = ticks_ms()
		self.bounding = ((0,0), (1,1))

	def scale(self, scale):
		for i in range(len(self.__points_org)):
			# Calculate the vector from the center to the point
			vector = (self.__points_org[i][0] - self.__center[0], self.__points_org[i][1] - self.__center[1])
			scaled_vector = (vector[0] * scale, vector[1] * scale)

			self.points[i] = (int(self.__center[0] + scaled_vector[0]), int(self.__center[1] + scaled_vector[1]))
			self.radii[i] = int(self.__radii_org[i] * scale)
			self.__scale = scale

	def save_bounding(self, bounding):
		self.bounding = bounding

	def get_bounding(self):
		return self.bounding

	def reset_time(self):
		self.__saved_time = ticks_ms()

	def get_particle(self):
		time_diff = ticks_diff(ticks_ms(), self.__saved_time)
		self.__saved_time = ticks_ms()

		self.__orientation += self.velocities[1](ticks_ms()/1000) * time_diff / 1000

		dx = self.velocities[0](ticks_ms()/1000) * cos(self.__orientation) * time_diff / 1000
		dy = self.velocities[0](ticks_ms()/1000) * sin(self.__orientation) * time_diff / 1000
		self.__location = (self.__location[0] + dx, self.__location[1] + dy)

		return ((int(self.__location[0] - self.__center[0] * self.__scale), int(self.__location[1] - self.__center[1] * self.__scale)), self.points, self.radii, self.__colour)

class Heart(Particle):
	def __init__(self, spawn):
		points = ((0,0), (int(0.34*30), int(-0.93*30)), 
				(int(0.8*30), int(0.2*30)), (0, int(1*30)), 
				(int(-0.8*30), int(0.2*30)), (int(-0.34*30), int(-0.93*30)))
		radii = (0, 10, 15, 0, 15, 10)
		super().__init__(spawn, (30,30), points, radii, colour=2)

class Tear(Particle):
	def __init__(self, spawn):
		points = ((15,0), (int(1*15+15), int(1.8*15)), 
				(int(15), int(2.5*15)), (0, int(1.8*15)))
		radii = (0, 10, 5, 10)
		super().__init__(spawn, (15, 2.5/2*15), points, radii)
		self.velocities = (lambda t: 60, lambda t: sin(t*4+random.choice([0, pi])))
