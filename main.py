import sys
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal, Qt, QEvent, QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.uic import loadUi
import cv2
import time
import platform
import yaml
import os
import random

if platform.architecture()[0] != '64bit':
    import picamera
    import RPi.GPIO as gpio
    from picamera.array import PiRGBArray


class CountdownShower(QThread):
    ImageUpdate = pyqtSignal(QImage)
    EndSignal = pyqtSignal()

    def __init__(self, width, height, images_count):
        super().__init__()

        self.height = height
        self.width = width
        self.last_dir_id = 0

        self.t = 5 / images_count

        self.start_countdown = False

        self.images = []

        for i in range(images_count):
            frame = cv2.imread("countdown/" + str(i) + ".jpg")
            self.images.append(frame)

    def start_counting(self):
        self.start_countdown = True

    def stop_counting(self):
        self.start_countdown = False

    def run(self):
        self.ThreadActive = True

        while self.ThreadActive:

            if self.start_countdown:
                for i in range(len(self.images)):
                    if not self.start_countdown:
                        break

                    s = time.time()
                    img = cv2.cvtColor(self.images[i], cv2.COLOR_BGR2RGB)

                    ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                    img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)
                    self.ImageUpdate.emit(img_qt)

                    elapsed = time.time() - s
                    delta = self.t - elapsed

                    if delta > 0:
                        loop = QEventLoop()
                        QTimer.singleShot(int(delta * 1000), loop.quit)
                        loop.exec_()
                self.EndSignal.emit()

                self.start_countdown = False

            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec_()

    def stop(self):
        self.ThreadActive = False
        self.quit()


class ImageReader(QThread):
    ImageUpdate = pyqtSignal(QImage)

    def __init__(self, camera_width, camera_height, width, height, camera_flip, camera_rotation, save_dir):
        super().__init__()
        self.camera_height = camera_height
        self.camera_width = camera_width
        self.camera_rotation = camera_rotation
        self.camera_flip = camera_flip
        self.height = height
        self.width = width

        self.current_frame = None
        self.save_dir = save_dir

        self.show = False

        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None
        self.background = cv2.imread("background.png")

        self.output_image = None
        self.output_image_path = ""

        self.img_id = 0

        self.last_dir_id = 0

        os.makedirs(self.save_dir, exist_ok=True)

        while True:

            if not os.path.isdir(os.path.join(self.save_dir, str(self.last_dir_id))):
                break
            self.last_dir_id += 1

        self.save_all_frames()

    def start_showing(self):
        self.show = True

    def stop_showing(self):
        self.show = False

    def capture(self):
        print("ca[ture")
        if self.current_frame is not None:
            if self.img_id == 0:
                self.frame_1 = self.current_frame.copy()
                self.img_id += 1
            elif self.img_id == 1:
                self.frame_2 = self.current_frame.copy()
                self.img_id += 1
            elif self.img_id == 2:
                self.frame_3 = self.current_frame.copy()
                self.img_id += 1
        else:
            print("Missing camera image!")

        if self.img_id >= 3:
            self.img_id = 0

    def save_all_frames(self):
        current_dir = os.path.join(self.save_dir, str(self.last_dir_id))
        os.makedirs(current_dir, exist_ok=True)

        if self.frame_1 is not None:
            cv2.imwrite(os.path.join(current_dir, "1.png"), self.frame_1)
        if self.frame_2 is not None:
            cv2.imwrite(os.path.join(current_dir, "2.png"), self.frame_2)
        if self.frame_3 is not None:
            cv2.imwrite(os.path.join(current_dir, "3.png"), self.frame_3)
        if self.output_image is not None:
            self.output_image_path = os.path.join(current_dir, "razem.png")
            cv2.imwrite(self.output_image_path, self.output_image)
        else:
            self.output_image_path = None

        self.last_dir_id += 1

    def get_output_image(self):
        self.output_image = self.background.copy()

        f1 = cv2.resize(self.frame_1, (520, 293))
        f2 = cv2.resize(self.frame_2, (520, 293))
        f3 = cv2.resize(self.frame_3, (520, 293))

        self.output_image[251:251 + 293, 47:47 + 520] = f1
        self.output_image[629:629 + 293, 47:47 + 520] = f2
        self.output_image[1013:1013 + 293, 47:47 + 520] = f3

        return self.output_image.copy()

    def run(self):
        self.ThreadActive = True

        id = 0
        last_time = time.time()

        if platform.architecture()[0] != '64bit':
            camera = picamera.PiCamera()
            camera.rotation = self.camera_rotation
            camera.annotate_text_size = 80
            camera.resolution = (self.camera_width, self.camera_height)
            camera.hflip = self.camera_flip
            cap = PiRGBArray(camera)

            while self.ThreadActive:
                if self.show:
                    for frame_picamera in camera.capture_continuous(cap, format="bgr", use_video_port=True):

                        frame = frame_picamera.array

                        self.current_frame = frame

                        if time.time() - last_time > 1:
                            print("FPS:", id)
                            id = 0
                            last_time = time.time()

                        if frame is not None:
                            id += 1
                            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                            img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)

                            self.ImageUpdate.emit(img_qt)
                        cap.truncate(0)

                        if not self.show or not self.ThreadActive:
                            break
                else:
                    loop = QEventLoop()
                    QTimer.singleShot(100, loop.quit)
                    loop.exec_()

        else:
            while self.ThreadActive:
                if self.show:
                    frame = cv2.imread("0.jpg")

                    if time.time() - last_time > 1:
                        print("FPS:", id)
                        id = 0
                        last_time = time.time()

                    if frame is not None:
                        self.current_frame = frame
                        id += 1
                        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                        img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)
                        self.ImageUpdate.emit(img_qt)
                else:
                    loop = QEventLoop()
                    QTimer.singleShot(100, loop.quit)
                    loop.exec_()

    def stop(self):
        self.ThreadActive = False
        self.quit()


class FotoBudka(QDialog):
    def __init__(self):
        super(FotoBudka, self).__init__()
        loadUi('fotobudka.ui', self)

        self.setWindowTitle('Fotobudka')

        self.showFullScreen()

        self.img_width = 1080
        self.img_height = 607

        self.output_image_display_width = 460
        self.output_image_display_height = 1310

        self.fotobudka = cv2.imread("fotobudka.png")
        self.black = cv2.imread("black.png")

        self.current_state = 0

        self.image_reader = ImageReader(1280, 720, self.img_width, self.img_height, 0, 0, "saved_images")
        self.image_reader.ImageUpdate.connect(self.ImageViewUpdate)
        self.image_reader.start()

        self.countdown_shower = CountdownShower(self.img_width, self.img_height, 20)
        self.countdown_shower.ImageUpdate.connect(self.CountdownUpdate)
        self.countdown_shower.EndSignal.connect(self.countdown_end)
        self.countdown_shower.start()

        self.top_texts = ["Rewelacyjnie!", "Czadowo!", "OMG!", "Gitówa!", "Zmiana stroju!"]
        self.bop_texts = ["Nadchodzi", "Teraz", "Przybywa", "Już za chwilę", "Trzy, dwa, jeden", "Wkracza", "Wskakuje",
                          "Wlatuje"]

        self.reset()

    def countdown_end(self):

        if self.current_state == 1 or self.current_state == 2:
            self.image_reader.capture()

            img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
            self.top_image_view.setPixmap(QPixmap.fromImage(black_image))
            self.bot_image_view.setPixmap(QPixmap.fromImage(black_image))

            id = random.randint(0, len(self.top_texts) - 1)

            self.set_top_text(self.top_texts[id])

            id = random.randint(0, len(self.bop_texts) - 1)

            self.set_bot_text(self.bop_texts[id] + "<br>Zdjęcie nr " + str(self.current_state + 1))

            self.current_state += 1

            self.sleep(2000)

            self.set_top_text("")
            self.set_bot_text("")

            self.countdown_shower.start_counting()

        elif self.current_state == 3:
            self.image_reader.capture()
            self.image_reader.stop_showing()
            self.output_image_view.setVisible(True)
            self.mid_image_view.setVisible(False)
            self.top_image_view.setVisible(False)

            img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
            self.bot_image_view.setPixmap(QPixmap.fromImage(black_image))

            img = self.image_reader.get_output_image()

            img = cv2.resize(img, (self.output_image_display_width, self.output_image_display_height))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            output_image = ConvertToQtFormat.scaled(self.output_image_display_width, self.output_image_display_height,
                                                    Qt.KeepAspectRatio)
            self.output_image_view.setPixmap(QPixmap.fromImage(output_image))

            self.image_reader.save_all_frames()

            self.set_bot_text("Wciśnij przycisk,<br> aby wydrukować<br>Poczekaj 10 sekund,<br> aby anulować", 80)

    def CountdownUpdate(self, Image):
        self.bot_image_view.setPixmap(QPixmap.fromImage(Image))
        self.top_image_view.setPixmap(QPixmap.fromImage(Image))

    def ImageViewUpdate(self, Image):
        self.mid_image_view.setPixmap(QPixmap.fromImage(Image))

    def set_top_text(self, text):
        self.top_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:100pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def set_bot_text(self, text, size=100):
        self.bot_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:" + str(
                size) + "pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def reset(self):
        self.current_state = 0
        self.output_image_view.setVisible(False)
        self.top_image_view.setVisible(True)
        self.mid_image_view.setVisible(True)
        self.bot_image_view.setVisible(True)
        self.image_reader.stop_showing()

        img = cv2.cvtColor(self.fotobudka, cv2.COLOR_BGR2RGB)
        ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
        fotobudka_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
        self.top_image_view.setPixmap(QPixmap.fromImage(fotobudka_image))

        img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
        ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
        black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
        self.mid_image_view.setPixmap(QPixmap.fromImage(black_image))
        self.bot_image_view.setPixmap(QPixmap.fromImage(black_image))

        self.set_bot_text("Wciśnij przycisk, aby rozpocząć!")
        self.set_top_text("")

    def sleep(self, sleep_time):
        loop = QEventLoop()
        QTimer.singleShot(sleep_time, loop.quit)
        loop.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_N:
            if self.current_state == 0:
                self.image_reader.start_showing()

                img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
                ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
                self.top_image_view.setPixmap(QPixmap.fromImage(black_image))

                self.set_top_text("Przygotuj się do zdjęcia!")

                id = random.randint(0, len(self.bop_texts) - 1)

                self.set_bot_text(self.bop_texts[id] + "<br>Zdjęcie nr 1")

                self.sleep(2000)

                self.set_top_text("")
                self.set_bot_text("")

                self.countdown_shower.start_counting()

                self.current_state += 1

        elif event.key() == Qt.Key_E:
            self.bot_image_view.setVisible(False)
        elif event.key() == Qt.Key_R:
            self.bot_image_view.setVisible(True)
        elif event.key() == Qt.Key_Escape:
            self.close()


app = QApplication(sys.argv)
widget = FotoBudka()
widget.show()
sys.exit(app.exec_())
