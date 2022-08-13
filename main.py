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
import cups

if platform.architecture()[0] != '64bit':
    import picamera
    import RPi.GPIO as GPIO
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

        self.cap = cv2.VideoCapture('count_5_cropped.mp4')

        # for i in range(images_count):
        #     frame = cv2.imread("countdown/" + str(i) + ".jpg")
        #     self.images.append(frame)

    def reset(self):
        self.load_cap()
        self.start_countdown = False
    def load_cap(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture('count_5_cropped.mp4')

    def start_counting(self):
        self.start_countdown = True

    def stop_counting(self):
        self.start_countdown = False

    def run(self):
        self.ThreadActive = True

        while self.ThreadActive:

            if self.start_countdown:
                while self.cap.isOpened():
                    if not self.start_countdown:
                        break
                    ret, frame = self.cap.read()
                    if ret == True:
                        s = time.time()
                        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                        ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                        img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)
                        self.ImageUpdate.emit(img_qt)
                        elapsed = time.time() - s
                        delta = self.t - elapsed

                        if delta > 0:
                            loop = QEventLoop()
                            QTimer.singleShot(int(delta * 1000), loop.quit)
                            loop.exec_()

                    # Break the loop
                    else:
                        break
                self.EndSignal.emit()
                self.start_countdown = False

                self.load_cap()
            else:
                loop = QEventLoop()
                QTimer.singleShot(100, loop.quit)
                loop.exec_()
                # for i in range(len(self.images)):
                #     if not self.start_countdown:
                #         break
                #
                #     s = time.time()
                #     img = cv2.cvtColor(self.images[i], cv2.COLOR_BGR2RGB)
                #
                #     ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                #     img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)
                #     self.ImageUpdate.emit(img_qt)
                #
                #     elapsed = time.time() - s
                #     delta = self.t - elapsed
                #
                #     if delta > 0:
                #         loop = QEventLoop()
                #         QTimer.singleShot(int(delta * 1000), loop.quit)
                #         loop.exec_()
                # self.EndSignal.emit()
                #
                # self.start_countdown = False


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

    def reset(self):
        self.show = False
        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None
        self.output_image = None
        self.img_id = 0
        self.output_image_path = ""

    def start_showing(self):
        self.show = True

    def stop_showing(self):
        self.show = False

    def capture(self):
        print("CAPTURE!")
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
        loadUi('fotobudka_hd.ui', self)

        self.setWindowTitle('Fotobudka')

        self.showFullScreen()

        self.img_width = 720
        self.img_height = 405

        self.wait_before_countdown = 4000

        self.output_image_display_width = 307
        self.output_image_display_height = 874

        self.fotobudka = cv2.imread("fotobudka_hd.png")
        self.black = cv2.imread("black.png")

        self.current_state = 0

        self.image_reader = ImageReader(1280, 720, self.img_width, self.img_height, 0, 0, "saved_images")
        self.image_reader.ImageUpdate.connect(self.ImageViewUpdate)
        self.image_reader.start()

        self.countdown_shower = CountdownShower(self.img_width, self.img_height, 80)
        self.countdown_shower.ImageUpdate.connect(self.CountdownUpdate)
        self.countdown_shower.EndSignal.connect(self.countdown_end)
        self.countdown_shower.start()

        self.top_texts = ["Rewelacyjnie!", "Czadowo!", "OMG!", "Gitówa!", "Zmiana stroju!"]
        self.bop_texts = ["Nadchodzi", "Teraz", "Przybywa", "Już za chwilę", "Trzy, dwa, jeden", "Wkracza", "Wskakuje",
                          "Wlatuje"]

        self.current_texts_top_id = []
        self.current_texts_bot_id = []

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.timeout)

        self.reset()

        CAMERA_BUTTON_PIN = 21
        if platform.architecture()[0] != '64bit':
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(CAMERA_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(CAMERA_BUTTON_PIN, GPIO.FALLING, callback=self.button_click)

    def countdown_end(self):
        print("COUNTDOWN END")
        if self.current_state == 1 or self.current_state == 2:
            self.image_reader.capture()

            img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
            self.top_image_view.setPixmap(QPixmap.fromImage(black_image))
            self.bot_image_view.setPixmap(QPixmap.fromImage(black_image))

            self.set_top_text(self.top_texts[self.current_texts_top_id[self.current_state - 1]])

            self.set_bot_text(
                self.bop_texts[self.current_texts_bot_id[self.current_state]] + "<br>Zdjęcie nr " + str(self.current_state + 1))

            self.current_state += 1

            self.sleep(self.wait_before_countdown)

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
            self.image_reader.save_all_frames()

            #img = cv2.resize(img, (self.output_image_display_width, self.output_image_display_height))
            # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            # output_image = ConvertToQtFormat.scaled(self.output_image_display_width, self.output_image_display_height,
            #                                         Qt.KeepAspectRatio)
            # self.output_image_view.setPixmap(QPixmap.fromImage(output_image))
            if self.image_reader.output_image_path != "":
                pixmap = QPixmap(self.image_reader.output_image_path)
                self.output_image_view.setPixmap(pixmap)

            self.set_bot_text("Wciśnij przycisk,<br> aby wydrukować!<br>Poczekaj 10 sekund,<br> aby anulować!", 55)

            print("Start Timer")

            self.current_state += 1

            self.timer.start()

    def timeout(self):
        print("TIMEOUT")
        self.reset()

    def CountdownUpdate(self, Image):
        self.bot_image_view.setPixmap(QPixmap.fromImage(Image))
        self.top_image_view.setPixmap(QPixmap.fromImage(Image))

    def ImageViewUpdate(self, Image):
        self.mid_image_view.setPixmap(QPixmap.fromImage(Image))

    def set_top_text(self, text):
        self.top_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:70pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def set_bot_text(self, text, size=70):
        self.bot_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:" + str(
                size) + "pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def reset(self):
        self.current_state = 0
        self.output_image_view.setVisible(False)
        self.top_image_view.setVisible(True)
        self.mid_image_view.setVisible(True)
        self.bot_image_view.setVisible(True)
        self.image_reader.reset()
        self.countdown_shower.reset()

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

        self.current_texts_bot_id.clear()
        self.current_texts_top_id.clear()

        while len(self.current_texts_bot_id) < 3:
            id = random.randint(0, len(self.bop_texts) - 1)

            if not (id in self.current_texts_bot_id):
                self.current_texts_bot_id.append(id)

        while len(self.current_texts_top_id) < 2:
            id = random.randint(0, len(self.top_texts) - 1)

            if not (id in self.current_texts_top_id):
                self.current_texts_top_id.append(id)

    def sleep(self, sleep_time):
        loop = QEventLoop()
        QTimer.singleShot(sleep_time, loop.quit)
        loop.exec_()

    def print(self):
        if self.image_reader.output_image_path != "":
            print("PRINTING!")
            self.set_bot_text("Drukuję...")
            # conn = cups.Connection()
            # printers = conn.getPrinters()
            # default_printer = printers.keys()[0]
            # cups.setUser('kidier')
            # conn.printFile(default_printer, self.image_reader.output_image_path, "boothy", {'fit-to-page': 'True'})
            # print("Print job successfully created.")

            self.sleep(5000)
        else:
            print("Missing output image!")

    def button_click(self):
        if self.current_state == 0:
            self.current_state += 1
            self.image_reader.start_showing()

            img = cv2.cvtColor(self.black, cv2.COLOR_BGR2RGB)
            ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            black_image = ConvertToQtFormat.scaled(self.img_width, self.img_height, Qt.KeepAspectRatio)
            self.top_image_view.setPixmap(QPixmap.fromImage(black_image))

            self.set_top_text("Przygotuj się do zdjęcia!")

            self.set_bot_text(self.bop_texts[self.current_texts_bot_id[0]] + "<br>Zdjęcie nr 1")

            self.sleep(self.wait_before_countdown)

            self.set_top_text("")
            self.set_bot_text("")

            self.countdown_shower.start_counting()

        elif self.current_state == 4:
            self.current_state += 1
            self.timer.stop()
            self.print()
            self.reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_N:
            self.button_click()
        elif event.key() == Qt.Key_Escape:
            self.close()


app = QApplication(sys.argv)
widget = FotoBudka()
widget.show()
sys.exit(app.exec_())
