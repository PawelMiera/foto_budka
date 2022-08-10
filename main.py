import sys
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.uic import loadUi
import cv2
import time
import platform
import yaml

if platform.architecture()[0] != '64bit':
    import picamera
    import RPi.GPIO as gpio
    from picamera.array import PiRGBArray


class ImageReader(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def __init__(self, width, height, camera_flip, camera_rotation):
        super().__init__()
        self.camera_rotation = camera_rotation
        self.camera_flip = camera_flip
        self.height = height
        self.current_frame = None
        self.width = width

    def run(self):
        self.ThreadActive = True

        if platform.architecture()[0] != '64bit':
            camera = picamera.PiCamera()
            camera.rotation = self.camera_rotation
            camera.annotate_text_size = 80
            camera.resolution = (self.width, self.height)
            camera.hflip = self.camera_flip
            cap = PiRGBArray(camera)

        id = 0
        last_time = time.time()
        while self.ThreadActive:
            if platform.architecture()[0] != '64bit':
                camera.capture(cap, format="bgr")
                frame = cap.array
            else:
                frame = cv2.imread("0.jpg")
                ret = True

            if frame is not None:
                self.current_frame = frame
                if time.time() - last_time > 1:
                    print(id)
                    id =0
                    last_time = time.time()
                    print(frame.shape)
                id +=1
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                img_qt = ConvertToQtFormat.scaled(1280, 720, Qt.KeepAspectRatio)
                self.ImageUpdate.emit(img_qt)

    def stop(self):
        self.ThreadActive = False
        self.quit()


class FotoBudka(QDialog):
    def __init__(self):
        super(FotoBudka, self).__init__()
        loadUi('fotobudka.ui', self)

        self.setWindowTitle('Fotobudka')

        self.showFullScreen()

        self.image_reader = ImageReader(1280, 720, 0, 0)
        self.image_reader.ImageUpdate.connect(self.ImageViewUpdate)
        self.image_reader.start()

        print(platform.architecture())



    def ImageViewUpdate(self, Image):
        self.image_view.setPixmap(QPixmap.fromImage(Image))


app = QApplication(sys.argv)
widget = FotoBudka()
widget.show()
sys.exit(app.exec_())
