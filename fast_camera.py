from picamera.array import PiRGBArray
from picamera import PiCamera
from threading import Thread
import cv2
import time


class PiVideoStream:
	def __init__(self, resolution=(720, 480), framerate=32):
		# initialize the camera and stream
		self.camera = PiCamera()
		self.camera.resolution = resolution
		self.camera.framerate = framerate
		self.rawCapture = PiRGBArray(self.camera, size=resolution)
		self.stream = self.camera.capture_continuous(self.rawCapture,
			format="bgr", use_video_port=True)
		# initialize the frame and the variable used to indicate
		# if the thread should be stopped
		self.frame = None
		self.stopped = False
		self.new_frame = False

	def start(self):
		# start the thread to read frames from the video stream
		Thread(target=self.update, args=()).start()
		return self
	def update(self):
		# keep looping infinitely until the thread is stopped
		for f in self.stream:
			# grab the frame from the stream and clear the stream in
			# preparation for the next frame
			self.frame = f.array
			self.new_frame = True
			self.rawCapture.truncate(0)

			# if the thread indicator variable is set, stop the thread
			# and resource camera resources
			if self.stopped:
				self.stream.close()
				self.rawCapture.close()
				self.camera.close()
				return
	def read(self):
		# return the frame most recently read
		return self.frame
	def stop(self):
		# indicate that the thread should be stopped
		self.stopped = True


vs = PiVideoStream().start()


start = time.time()
id =0
# loop over some frames
# if...this time using the threaded stream
while id < 200:
	# grab the frame from the threaded video stream and resize it
	# to have a maximum width of 400 pixels
	if vs.new_frame:
		frame = vs.read()
		# update the FPS counter
		id +=1
		vs.new_frame = False
# stop the timer and display FPS information
elapsed = time.time() - start
print("[INFO] elasped time: {:.2f}".format(elapsed))
print("[INFO] approx. FPS: {:.2f}".format(200 / elapsed))