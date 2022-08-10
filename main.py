import sys
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.uic import loadUi
import cv2
import time

# import RPi.GPIO as gpio

class ImageReader(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def run(self):
        self.ThreadActive = True
        cap = cv2.VideoCapture(0)
        id = 0
        last_time = time.time()
        while self.ThreadActive:
            ret, frame = cap.read()
            # ret = True
            # frame = cv2.imread("0.jpg")
            if ret:
                if time.time() - last_time > 1:
                    print(id)
                    id =0
                    last_time = time.time()
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

        self.image_reader = ImageReader()
        self.image_reader.ImageUpdate.connect(self.ImageViewUpdate)
        self.image_reader.start()

    def ImageViewUpdate(self, Image):
        self.image_view.setPixmap(QPixmap.fromImage(Image))


app = QApplication(sys.argv)
widget = FotoBudka()
widget.show()
sys.exit(app.exec_())
