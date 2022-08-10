import cv2
import time


images_count = 70
t = 5 / 70
print(t)

images = []

for i in range(images_count):
    frame = cv2.imread("countdown/" + str(i) + ".jpg")

    frame_2 = cv2.resize(frame,(1080, 607))

    cv2.imwrite("countdown/" + str(i) + ".jpg", frame_2)

    images.append(frame)

start = time.time()

for i in range(len(images)):
    s = time.time()
    cv2.imshow("IMG", images[i])
    cv2.waitKey(1)

    elapsed = time.time() - s

    print(elapsed)

    delta = t - elapsed

    print(delta)

    if delta > 0:
        time.sleep(delta)

print("ALL ", time.time() - start)