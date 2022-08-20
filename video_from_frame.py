import numpy as np
import skvideo.io

import cv2

cap = cv2.VideoCapture('odliczanie.mp4')

id = 0
ind = 0
images = []
out_frames = 0

while(cap.isOpened()):

  ret, frame = cap.read()
  if ret:
    id += 1
    print(id)
    if id % 2 == 0:
      if id < 235 and id >20:
        out_frames += 1
        images.append(frame)

  else:
    break

print(id)

images = np.array(images)

cv2.imwrite("smile.png", cv2.resize(images[-1], (1050, 1680)))

skvideo.io.vwrite("odliczanie_reduced.mp4", images)

print(out_frames)

# out_video = np.empty([5, height, width, 3], dtype=np.uint8)
# out_video = out_video.astype(np.uint8)
#
# # Writes the the output image sequences in a video file
# skvideo.io.vwrite("video.mp4", out_video)