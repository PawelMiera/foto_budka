import cv2
import time

cap = cv2.VideoCapture('odliczanie.mp4')

id = 0
ind = 0

while(cap.isOpened()):

  ret, frame = cap.read()


  last_time = time.time()
  t = 1/15
  if ret == True:
    print(frame.shape)
    id += 1

    cv2.imshow('Frame', frame)
    cv2.waitKey(1)
    # if id > 450:
    #     print(id)
    # # Display the resulting frame
    #
    #     if id % 3 ==0:
    #
    #         cv2.imshow('Frame', frame)
    #
    #         cv2.imwrite("countdown/" + str(ind) + ".jpg", frame)
    #         ind += 1
    #
    #         if cv2.waitKey(1) & 0xFF == ord('q'):
    #           break

  # Break the loop
  else:
    print("OOO")


print(id)

# When everything done, release the video capture object
cap.release()

# Closes all the frames
cv2.destroyAllWindows()