import tft_config
from math import cos, sin, pi
from shapeDrawer import shapeDrawer
import gc
import micropython as mp
from tft_config import SCREEN_SIZE
from Particle import *
from time import sleep

COLOURS = {'BLACK': 0x0000, 'WHITE': 0xFFFF, 'RED': 0xF800, 'GREEN': 0x07E0, 'BLUE': 0x001F, 'CYAN': 0x07FF, 'MAGENTA': 0xF81F, 'YELLOW': 0xFFE0, 'PINK': 0xF810}

def bound_to_rect(bound):
	# TODO: add_bound in c function draw_boundary
	return (clamp_coordinates(bound[0][0]-2, bound[0][1]-2), (min(bound[1][0]-bound[0][0]+4, SCREEN_SIZE[0]-bound[0][0]+1), min(bound[1][1]-bound[0][1]+4, SCREEN_SIZE[1]-bound[0][1]+1)))

def clamp_coordinates(x, y):
	return (max(min(x, SCREEN_SIZE[0]-1), 0), max(min(y, SCREEN_SIZE[1]-1), 0))

def calculate_bound(points, offset = (0,0)):
	min_x = int(min(points, key=lambda x: x[0])[0]+offset[0])
	min_y = int(min(points, key=lambda x: x[1])[1]+offset[1])
	max_x = int(max(points, key=lambda x: x[0])[0]+offset[0])
	max_y = int(max(points, key=lambda x: x[1])[1]+offset[1])
	return ((min_x, min_y), (max_x, max_y))

class Screen():
	def __init__(self, eye_size = (30,90), mouth_size = (60,40)):
		self.eye_height = eye_size[1]
		self.eye_width = eye_size[0]
		self.mouth_height = mouth_size[1]
		self.mouth_width = mouth_size[0]
		
		self.tft = tft_config.config(tft_config.TALL)
		#Todo: Make sure init does not produce white noise but black screen!
		self.tft.init()
		self.tft.rotation(2)
		self.is_on = True

		print(f"Memory left: {gc.mem_free()} (Pre)")
		self.__screen_drawer = shapeDrawer(SCREEN_SIZE, 2)
		self.bitmap = self.__screen_drawer.get_bitmap((COLOURS['BLACK'], COLOURS['WHITE'], COLOURS['PINK'], COLOURS['BLUE']))
		
		self.__bounding = {}
		self.__make_black = True
		print(f"Memory left: {gc.mem_free()} (Post)\n\n")

	def make_black(self):
		self.__make_black = True

	def screen_turn(self, on):
		if on:
			self.tft.on()
			self.is_on = True
		else:
			self.tft.off()
			self.is_on = False

	def screen_toggle(self):
		if self.is_on:
			self.screen_turn(False)
		else:
			self.screen_turn(True)

	def draw_face(self, newstatus, status, particles):
		Count = 0
		if (not self.__make_black and 
				len(particles) == 0 and 
				not any(key in newstatus.keys() for key in ['left_eye', 'right_eye', 'mouth', 'x', 'y', 
															'eye_open', 'left_right', 'eyebrow_angle', 'under_eye_lid', 
															'mouth_width', 'mouth_y', 'smile', 'cheeks'])):
			return

		# todo: The face is always updated. Not only when the face changes. This is not optimal.
		# self.__bounding = self.__screen_drawer.get_boundaries()
		self.__screen_drawer.reset_bounding_boxes()

		for key in ('left_eye', 'right_eye', 'mouth', 'particle', 'cheeks'):
			if key in self.__bounding:
				Count = 1
				for bound in self.__bounding[key]:
					self.__screen_drawer.draw_rect(*bound_to_rect(bound), 0, key='black')

		self.__bounding = {}

		if self.__make_black:
			self.__screen_drawer.draw_circle((SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2), SCREEN_SIZE[0]//2, 0, key='black')
			self.__make_black = False

		if True or any(key in ['eye_open', 'eyebrow_angle', 'under_eye_lid', 'left_right', 'x', 'y'] for key in newstatus.keys()):
			self.__draw_eyes(status)
	
			
		if True or any(key in ['x', 'y', 'mouth_width', 'mouth_y', 'smile', 'smirk'] for key in newstatus.keys()):
			self.__draw_mouth(status)

		if True or any('cheeks' in newstatus.keys()):
			self.__draw_cheeks(status)
			
		if len(particles)>0:
			self.__draw_particles(particles)

		# gc.collect()
		try:
			self.bitmap = self.__screen_drawer.get_bitmap((COLOURS['BLACK'], COLOURS['WHITE'], COLOURS['PINK'], COLOURS['BLUE']))
			# print(f"Bitmap: {len(self.bitmap['BOUNDING'])}")
			if len(self.bitmap['BOUNDING']) > 0:
				self.tft.pbitmap(self.bitmap, 1)
				Count += 1
		except Exception as e:
			print(f"Error during drawing ({gc.mem_free()}): {e}")

		if Count < 2:
			print("\n\n---- No bounding box painted\n\n")

	def __draw_eyes(self, status):
		gc.collect()
		under_y = self.eye_height-status['under_eye_lid']*self.eye_height/2

		if (status['eye_open']>0):
			height_eye = under_y-status['eye_open']*(self.eye_height-status['under_eye_lid']*self.eye_height/2)
			rounded_corners = round(min((under_y-height_eye)/2,15))
			angle_eyebrow = min(max((under_y-height_eye-2*rounded_corners)/(1-10/45),0),45)/45*-status['eyebrow_angle']

			left_eye_coord = [	(0, round(max(height_eye+max(angle_eyebrow*45,0), -min(status['left_right'], 0)*self.eye_height/2))), 
					(self.eye_width, round(max(height_eye+max(-angle_eyebrow*45,0), -min(status['left_right'], 0)*self.eye_height/2))), 
					(self.eye_width, round(min(under_y, self.eye_height+min(status['left_right'], 0)*self.eye_height/2))), 
					(0, round(min(under_y, self.eye_height+min(status['left_right'], 0)*self.eye_height/2)))]
			
			self.__screen_drawer.draw_polygon_rounded(((status['x']-45)-self.eye_width//2,(status['y']-65)), 
				left_eye_coord, 
				[	int(max(rounded_corners-abs(max(angle_eyebrow*15,-10)),0)*(-((min(status['left_right'],0)-0.5)**2+(min(status['left_right'],0)-0.5)+0.25)+1)),
	 				int(max(rounded_corners-abs(min(angle_eyebrow*15,10)),0)*(-((min(status['left_right'],0)-0.5)**2+(min(status['left_right'],0)-0.5)+0.25)+1)), 
					int(rounded_corners*(-((min(status['left_right'],0)-0.5)**2+(min(status['left_right'],0)-0.5)+0.25)+1)), 
					int(rounded_corners*(-((min(status['left_right'],0)-0.5)**2+(min(status['left_right'],0)-0.5)+0.25)+1))], 
					1, key='left_eye')

			self.__bounding['left_eye'] = [calculate_bound(left_eye_coord, offset = ((status['x']-45)-self.eye_width//2,(status['y']-65)))]
			
			right_eye_coord = [(0, round(max(height_eye+max(-angle_eyebrow*45,0), max(status['left_right'], 0)*self.eye_height/2))), 
	 				(self.eye_width, round(max(height_eye+max(angle_eyebrow*45,0), max(status['left_right'], 0)*self.eye_height/2))), 
					(self.eye_width, round(min(under_y, self.eye_height-max(status['left_right'], 0)*self.eye_height/2))), 
					(0, round(min(under_y, self.eye_height-max(status['left_right'], 0)*self.eye_height/2)))]
			
			
			self.__screen_drawer.draw_polygon_rounded(((status['x']+45)-self.eye_width//2,(status['y']-65)),
				right_eye_coord, 
				[int(max(rounded_corners-abs(min(angle_eyebrow*15,10)),0)*(-((max(status['left_right'],0)-0.5)**2+(max(status['left_right'],0)-0.5)+0.25)+1)),
	 			int(max(rounded_corners-abs(max(angle_eyebrow*15,-10)),0)*(-((max(status['left_right'],0)-0.5)**2+(max(status['left_right'],0)-0.5)+0.25)+1)), 
					int(rounded_corners*(-((max(status['left_right'],0)-0.5)**2+(max(status['left_right'],0)-0.5)+0.25)+1)), 
					int(rounded_corners*(-((max(status['left_right'],0)-0.5)**2+(max(status['left_right'],0)-0.5)+0.25)+1))], 
					1, key='right_eye')
			
			self.__bounding['right_eye'] = [calculate_bound(right_eye_coord, offset = ((status['x']+45)-self.eye_width//2,(status['y']-65)))]
			
	def __draw_mouth(self, status):
		mouth_coord = [(round(self.mouth_width//2-(status['mouth_width']//2)*(1-status['smirk']*0.5)), round(status['mouth_y']*self.mouth_height//2)), 
				 (round(self.mouth_width//2+(status['mouth_width']//2)*(1+status['smirk']*0.5)), round(status['mouth_y']*self.mouth_height//2)), 
				 (round(self.mouth_width//2+(status['mouth_width']//2)*(1+status['smirk']*0.5)), round(self.mouth_height//2+status['mouth_y']*self.mouth_height//2)), 
				 (round(self.mouth_width//2-status['mouth_width']//2*(1-status['smirk']*0.5)), round(self.mouth_height//2+status['mouth_y']*self.mouth_height//2))]
		
		mouth_radii = [round(min(status['mouth_width']/2,max(self.mouth_height//4-(status['smile']*self.mouth_height//4)*(1-status['smirk']),0))),
				round(min(status['mouth_width']/2,max(self.mouth_height//4-status['smile']*self.mouth_height//4*(1+status['smirk']),0))),
				round(min(status['mouth_width']/2,max(self.mouth_height//4+status['smile']*self.mouth_height//4*(1+min(status['smirk'],0))-max(status['smirk'],0),0))), 
				round(min(status['mouth_width']/2,max(self.mouth_height//4+status['smile']*self.mouth_height//4*(1-max(status['smirk'],0))+min(status['smirk'],0),0)))]

		self.__screen_drawer.draw_polygon_rounded((round(status['x']-self.mouth_width//2), status['y']+45),
				mouth_coord, 
				mouth_radii, 
				1, key='mouth')
		
		self.__bounding['mouth'] = [calculate_bound(mouth_coord, offset=(round(status['x']-self.mouth_width//2), status['y']+45))]

	def __draw_cheeks(self, status):
		if status['cheeks'] > 0:
			x_offset = 60
			y_offset = 25
			radius = 13*status['cheeks'] 
			self.__screen_drawer.draw_circle((round(status['x']-x_offset), round(status['y'])+y_offset), round(radius), 2, key='cheeks')
			self.__screen_drawer.draw_circle((round(status['x']+x_offset), round(status['y'])+y_offset), round(radius), 2, key='cheeks')
			self.__bounding['cheeks'] = [[(round(status['x']-x_offset-radius), round(status['y']+y_offset-radius)), (round(status['x']-x_offset+radius), round(status['y']+y_offset+radius))], 
								[(round(status['x']+x_offset-radius), round(status['y']+y_offset-radius)), (round(status['x']+x_offset+radius), round(status['y']+y_offset+radius))]]

	def __draw_particles(self, particles):
		"""
		Draws the particles with the current configuration.
		"""
		self.__bounding['particle'] = []
		new_particles = []
		for particle in particles:
			particle_data = particle.get_particle()
			if distance(particle_data[0], (120, 120)) <= 150:
				new_particles.append(particle)
				self.__bounding['particle'].append(calculate_bound(particle_data[1], offset=particle_data[0]))
				self.__screen_drawer.draw_polygon_rounded(*particle_data, key='Particle')
			del particle_data
		particles[:] = new_particles  # Update the original list with the filtered particles
		gc.collect()