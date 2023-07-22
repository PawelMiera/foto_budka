import cv2
import numpy as np

win = cv2.namedWindow("win", cv2.WND_PROP_FULLSCREEN)
cv2.moveWindow("win", 0, 0)
cv2.setWindowProperty("win", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

frame = cv2.imread("img.png")
cv2.imshow("win", frame)
cv2.waitKey(0)
# win = cv2.imshow()
# cvNamedWindow("main_win", CV_WINDOW_AUTOSIZE);
# cvMoveWindow("main_win", 0, 0);
# cvSetWindowProperty("main_win", CV_WINDOW_FULLSCREEN, CV_WINDOW_FULLSCREEN);
#
# cvShowImage("main_win", cv_img);