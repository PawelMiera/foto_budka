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
        self.break_count = images_count - 2
        self.t = 5 / images_count

        self.start_countdown = False

        self.filename = 'odliczanie_reduced.mp4'

        self.cap = cv2.VideoCapture(self.filename)

    def reset(self):
        self.load_cap()
        self.start_countdown = False

    def load_cap(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.filename)

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

                    if ret:
                        s = time.time()
                        # img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # ConvertToQtFormat = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
                        # img_qt = ConvertToQtFormat.scaled(self.width, self.height, Qt.KeepAspectRatio)
                        # self.ImageUpdate.emit(img_qt)
                        rgbImage = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgbImage.shape
                        bytesPerLine = ch * w
                        convertToQtFormat = QImage(rgbImage.data, w, h, bytesPerLine, QImage.Format_RGB888)
                        p = convertToQtFormat.scaled(1050, 1680, Qt.KeepAspectRatio)
                        self.ImageUpdate.emit(p)

                        elapsed = time.time() - s
                        delta = self.t - elapsed

                        if delta > 0:
                            loop = QEventLoop()
                            QTimer.singleShot(int(delta * 1000), loop.quit)
                            loop.exec_()

                    # Break the loop
                    else:
                        break
                self.start_countdown = False
                self.EndSignal.emit()
                self.load_cap()
            else:
                loop = QEventLoop()
                QTimer.singleShot(50, loop.quit)
                loop.exec_()

    def stop(self):
        self.ThreadActive = False
        self.quit()


class ImageReader(QThread):
    EndSignal = pyqtSignal()
    def __init__(self, camera_width, camera_height, camera_flip, camera_rotation, shutter, frame_rate, iso,
                 save_dir, pasek_filename="Pasek_v3.png"):
        super().__init__()
        self.camera_height = camera_height
        self.camera_width = camera_width
        self.camera_rotation = camera_rotation
        self.camera_flip = camera_flip

        if platform.architecture()[0] != '64bit':
            self.camera = picamera.PiCamera()
            self.camera.rotation = self.camera_rotation
            self.camera.resolution = (self.camera_width, self.camera_height)
            self.camera.exposure_mode = 'off'
            self.camera.hflip = self.camera_flip
            self.camera.framerate = frame_rate
            self.camera.shutter_speed = shutter
            self.camera.iso = iso

            self.camera.capture('frame.png')

        self.current_frame = None
        self.save_dir = save_dir

        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None
        self.background = cv2.imread(pasek_filename)
        self.print_background = cv2.imread("print_background.png")

        self.output_image = None
        self.output_image_path = ""

        self.print_image = None
        self.print_image_path = ""

        self.img_id = 0

        self.last_dir_id = 0

        os.makedirs(self.save_dir, exist_ok=True)

        while True:

            if not os.path.isdir(os.path.join(self.save_dir, str(self.last_dir_id))):
                break
            self.last_dir_id += 1

        self.save_all_frames()

    def reset(self):
        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None
        self.output_image = None
        self.img_id = 0
        self.output_image_path = ""

        self.print_image_path = ""
        self.print_image = None

    def capture(self):
        if platform.architecture()[0] != '64bit':
            self.camera.capture('frame.png')
            frame = cv2.imread("frame.png")
        else:
            frame = cv2.imread("0.jpg")
            loop = QEventLoop()
            QTimer.singleShot(2000, loop.quit)
            loop.exec_()

        if frame is not None:
            if self.img_id == 0:
                self.frame_1 = frame.copy()
                self.img_id += 1
            elif self.img_id == 1:
                self.frame_2 = frame.copy()
                self.img_id += 1
            elif self.img_id == 2:
                self.frame_3 = frame.copy()
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

        if self.print_image is not None:
            self.print_image_path = os.path.join(current_dir, "print.png")
            cv2.imwrite(self.print_image_path, self.print_image)
        else:
            self.print_image_path = None

        self.last_dir_id += 1

    def generate_output_image(self):
        self.output_image = self.background.copy()

        w = 573
        h = 343

        x1 = 22
        x2 = 22
        x3 = 21
        y1 = 103
        y2 = 533
        y3 = 963

        f1 = cv2.resize(self.frame_1, (w, h))
        f2 = cv2.resize(self.frame_2, (w, h))
        f3 = cv2.resize(self.frame_3, (w, h))

        self.output_image[y1:y1 + h, x1:x1 + w] = f1
        self.output_image[y2:y2 + h, x2:x2 + w] = f2
        self.output_image[y3:y3 + h, x3:x3 + w] = f3

        self.print_image = self.print_background.copy()
        self.print_image[0:1748, 0:620] = self.output_image

    def get_output_image(self):
        return self.output_image.copy()

    def run(self):
        self.capture()
        self.EndSignal.emit()


class FotoBudka(QDialog):
    def __init__(self):
        super(FotoBudka, self).__init__()
        loadUi('fotobudka_new.ui', self)

        self.setWindowTitle('Fotobudka')

        self.showFullScreen()

        self.img_width = 1050
        self.img_height = 1680

        self.output_image_display_width = 307
        self.output_image_display_height = 874

        """
        Tutaj ustawiasz wszystkie parametry

        self.enable_camera_preview - czy w????czy?? podgl??d kamery
        self.fotobudka - nazwa pliki w ekranie startowym 720x405 px
        self.black - t??o pod wyswietlanym tekstem, raczej nie zmieniaj
        
        CAMERA_BUTTON_PIN - pin na raspi do przycisku
        self.wait_before_countdown - czas przed w????czeniem timera przed zdjeciem ms
        self.timeout_before_return - czas oczekiwania na powr??t do g??ownego ekranu po ca??ej sekwencji ms
        self.wait_for_print - czas oczekiwania na wydruk przed powrotem do g??ownego menu ms
        
        
        self.image_reader - parametry kolejno
        rozdzielczo???? kamery w, h
        wymiar obrazu wyswietlanego z kamery
        obrot kamery
        rotacja kamery
        nazwa folderu do zapisu zdjec
        nazwa pliku z paskiem
        """

        self.enable_camera_preview = True

        self.ekran_startowy = QPixmap("ekran_startowy.png")
        self.black = QPixmap("black_1050_1680.png")
        self.smile = QPixmap("smile.png")

        CAMERA_BUTTON_PIN = 21
        self.wait_before_countdown = 4000
        self.timeout_before_return = 15000
        self.wait_for_print = 19000
        self.foto_taken = False

        self.how_many_prints = 1
        self.max_prints = 4
        self.current_print = 0

        self.image_reader = ImageReader(camera_width=1920, camera_height=1080, camera_flip=0, camera_rotation=0,
                                        shutter=480000, frame_rate=1, iso=400, save_dir="saved_images",
                                        pasek_filename="Pasek_v3.png")

        self.image_reader.EndSignal.connect(self.foto_end)
        self.image_reader.start()
        self.current_state = 0

        self.countdown_shower = CountdownShower(self.img_width, self.img_height, 107)  #107
        self.countdown_shower.ImageUpdate.connect(self.CountdownUpdate)
        self.countdown_shower.EndSignal.connect(self.countdown_end)
        self.countdown_shower.start()

        self.top_texts = ["Rewelacyjnie!", "Czadowo!", "Git??wa!", "Zmiana stroju!", "Pi??knie!", 'Bomba!', 'Sztos!']
        self.bop_texts = ["Nadchodzi", "Teraz", "Przybywa", "Ju?? za chwil??", "Trzy, dwa, jeden", "Wkracza", "Wskakuje",
                          "Wlatuje"]

        self.current_texts_top_id = []
        self.current_texts_bot_id = []

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.timeout_before_return)
        self.timer.timeout.connect(self.timeout)

        while not self.foto_taken:
            self.sleep(10)

        self.reset()

        if platform.architecture()[0] != '64bit':
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(CAMERA_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(CAMERA_BUTTON_PIN, GPIO.FALLING, callback=self.button_click)

    def foto_end(self):
        print("CAPTURED")
        self.foto_taken = True

    def countdown_end(self):
        print("COUNTDOWN END")
        if self.current_state == 1 or self.current_state == 2:

            self.image_view.setPixmap(self.smile)

            self.foto_taken = False

            self.image_reader.start()

            loop_i = 0
            while not self.foto_taken:
                loop_i += 1
                if loop_i < 10:
                    self.image_view.setPixmap(self.smile)
                    self.sleep(10)
                else:
                    self.image_view.setPixmap(self.smile)
                    self.sleep(100)
                if loop_i > 400:
                    print("ERROR CAPTURE IS TAKING TOO LONG!")
                    break

            self.image_view.setPixmap(self.black)

            self.set_top_text(self.top_texts[self.current_texts_top_id[self.current_state - 1]])

            self.set_bot_text(
                self.bop_texts[self.current_texts_bot_id[self.current_state]] + "<br>Zdj??cie nr " + str(
                    self.current_state + 1))

            self.current_state += 1

            self.sleep(self.wait_before_countdown)

            self.set_top_text("")
            self.set_bot_text("")

            self.countdown_shower.start_counting()

        elif self.current_state == 3:
            self.image_view.setPixmap(self.smile)

            self.foto_taken = False

            self.image_reader.start()
            loop_i = 0
            while not self.foto_taken:
                loop_i += 1
                if loop_i < 10:
                    self.image_view.setPixmap(self.smile)
                    self.sleep(10)
                else:
                    self.image_view.setPixmap(self.smile)
                    self.sleep(100)
                if loop_i > 400:
                    print("ERROR CAPTURE IS TAKING TOO LONG!")
                    break

            self.output_image_view.setVisible(True)

            self.image_reader.generate_output_image()
            self.image_reader.save_all_frames()

            self.image_view.setPixmap(self.black)

            if self.image_reader.output_image_path != "":
                pixmap = QPixmap(self.image_reader.output_image_path)
                self.output_image_view.setPixmap(pixmap)

            self.set_bot_text("Wci??nij przycisk,<br> aby wydrukowa??!<br>Poczekaj 15 sekund,<br> aby anulowa??!", 65)

            print("Start Timer")

            self.current_state += 1

            self.timer.start()

    def timeout(self):
        print("TIMEOUT")
        self.reset()

    def CountdownUpdate(self, Image):
        self.image_view.setPixmap(QPixmap.fromImage(Image))

    def ImageViewUpdate(self, Image):
        pass

    def set_top_text(self, text):
        self.top_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:100pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def set_bot_text(self, text, size=100):
        self.bot_text.setText(
            "<html><head/><body><p align=\"center\"><span style=\" font-size:" + str(
                size) + "pt; font-weight:600; color:#ffffff;\"> " + text + "</span></p></body></html>")

    def reset(self):
        self.current_state = 0
        self.how_many_prints = 1
        self.current_print = 0
        self.output_image_view.setVisible(False)
        self.image_view.setVisible(True)
        self.image_reader.reset()
        self.countdown_shower.reset()

        self.image_view.setPixmap(self.ekran_startowy)

        self.set_bot_text("")
        self.set_top_text("")

        self.current_texts_bot_id.clear()
        self.current_texts_top_id.clear()
        self.foto_taken = False

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
        if self.image_reader.print_image_path != "":
            self.current_print = 0
            while self.current_print < self.how_many_prints:
                print("PRINTING!", self.current_print)
                self.set_bot_text("Wci??nij przycisk, aby wydrukowa?? wi??cej kopii!<br>Drukuj?? " + str(self.current_print + 1) + " z " + str(self.how_many_prints) + "...", 65)
                if platform.architecture()[0] != '64bit':
                    conn = cups.Connection()
                    printers = conn.getPrinters()
                    default_printer = list(printers.keys())[0]
                    cups.setUser('kidier')
                    conn.printFile(default_printer, self.image_reader.print_image_path, "boothy", {'fit-to-page': 'True'})
                    print("Print job successfully created.")

                self.sleep(self.wait_for_print)
                self.current_print += 1
        else:
            print("Missing output image!")

    def button_click(self, channel):
        if self.current_state == 0:
            self.current_state += 1

            self.image_view.setPixmap(self.black)

            self.set_top_text("Przygotuj si?? do zdj??cia!")

            self.set_bot_text(self.bop_texts[self.current_texts_bot_id[0]] + "<br>Zdj??cie nr 1")

            self.sleep(self.wait_before_countdown)

            self.set_top_text("")
            self.set_bot_text("")

            self.countdown_shower.start_counting()

        elif self.current_state == 4:
            self.current_state += 1
            self.timer.stop()
            self.print()
            self.reset()
        elif self.current_state == 5:
            if self.how_many_prints < self.max_prints:
                print("Print more!")
                self.how_many_prints += 1
                self.set_bot_text("Wci??nij przycisk, aby wydrukowa?? wi??cej kopii!<br>Drukuj?? " + str(self.current_print+1) + " z " + str(self.how_many_prints) + "...", 65)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_N:
            self.button_click(4)
        elif event.key() == Qt.Key_Escape:
            self.close()


app = QApplication(sys.argv)
widget = FotoBudka()
widget.show()
sys.exit(app.exec_())
