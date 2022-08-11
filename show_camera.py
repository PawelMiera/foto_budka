# import the necessary packages
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import cv2

camera = PiCamera()
camera.resolution = (1080, 607)
camera.framerate = 32
rawCapture = PiRGBArray(camera, size=(1080, 607))
# allow the camera to warmup
time.sleep(0.1)
# capture frames from the camera

last_time = time.time()
id=0
for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
	start = time.time()
	image = frame.array
	# show the frame
	cv2.imshow("Frame", image)
	key = cv2.waitKey(1) & 0xFF
	# clear the stream in preparation for the next frame
	rawCapture.truncate(0)
	if time.time() - last_time > 1:
		last_time = time.time()
		print(id)
		id = 0
	id +=1
	
	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break
