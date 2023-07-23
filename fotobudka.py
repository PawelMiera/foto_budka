import cv2

import threading
import time
from enum import IntEnum
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import random
import cups
from queue import Queue
import os
from datetime import datetime
import json
import argparse

class Rate:
    def __init__(self, rate):
        self.rate_time = 1.0 / rate
        self.last_time = time.time()

    def sleep(self):
        time_diff = time.time() - self.last_time
        sleep_time = self.rate_time - time_diff
        if sleep_time > 0:
            time.sleep(sleep_time)

        self.last_time = time.time()

    def get_remaining_time_millis_cv2(self):
        time_diff = time.time() - self.last_time
        sleep_time = self.rate_time - time_diff
        sleep_time = int(sleep_time * 1000)
        if sleep_time > 0:
            return sleep_time
        else:
            return 1

    def update_last_time(self):
        self.last_time = time.time()


class FlashControl:
    def __init__(self, gpio_pin=22):
        print("Starting flash")
        self.flash_event = threading.Event()
        self.end = threading.Event()
        self.gpio_pin = gpio_pin
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.gpio_pin, GPIO.OUT)

        GPIO.output(self.gpio_pin, GPIO.HIGH)

        for _ in range(2):
            GPIO.output(self.gpio_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(self.gpio_pin, GPIO.HIGH)
            time.sleep(0.2)

        thread = threading.Thread(target=self.run)
        thread.start()

    def start_flash(self):
        self.flash_event.set()

    def run(self):
        rate = Rate(100)

        while not self.end.is_set():
            if self.flash_event.is_set():
                GPIO.output(self.gpio_pin, GPIO.LOW)
                time.sleep(0.1)
                GPIO.output(self.gpio_pin, GPIO.HIGH)
                self.flash_event.clear()

            rate.sleep()
        GPIO.cleanup()  # cleanup all GPIO

    def close(self):
        self.end.set()


class CameraControl:
    def __init__(self, flash_control: FlashControl, frame_rate=5, exposure_time=300000, analogue_gain=8.0,
                 size=(2028, 1080), img_format="RGB888", print_fps=False, show_preview=False):
        self.print_fps = print_fps
        self.show_preview = show_preview

        self.end = threading.Event()
        self.photo_event = threading.Event()
        self.photo_done_event = threading.Event()
        self.flash_control = flash_control
        self.last_frame = None

        self.picam2 = Picamera2()
        controls = {"FrameRate": frame_rate, "ExposureTime": exposure_time, "AnalogueGain": analogue_gain}
        preview_config = self.picam2.create_preview_configuration(main={"size": size, "format": img_format},
                                                                  controls=controls)
        self.picam2.configure(preview_config)
        self.picam2.start()

        thread = threading.Thread(target=self.run)
        thread.start()

    def run(self):
        fps = 0
        last_print_time = time.time()

        while not self.end.is_set():
            if self.photo_event.is_set():
                self.flash_control.start_flash()
                self.last_frame = self.picam2.capture_array()
                self.photo_done_event.set()
            else:
                frame = self.picam2.capture_array()
                if self.show_preview:
                    cv2.imshow("preview", frame)
                    cv2.waitKey(1)

            if self.print_fps:
                fps += 1
                if time.time() - last_print_time > 1:
                    last_print_time = time.time()
                    print(fps)
                    fps = 0

    def start_photo(self):
        self.photo_event.set()
        self.photo_done_event.clear()

    def is_done(self):
        return self.photo_done_event.is_set()

    def get_photo(self):
        return self.last_frame.copy()

    def close(self):
        self.end.set()


class CameraControlSim:
    def __init__(self, flash_control, frame_rate=5, exposure_time=300000, analogue_gain=8.0,
                 size=(2028, 1080), img_format="RGB888", print_fps=False, show_preview=False):
        self.print_fps = print_fps
        self.show_preview = show_preview

        self.end = threading.Event()
        self.photo_event = threading.Event()
        self.photo_done_event = threading.Event()
        # self.flash_control = flash_control
        self.last_frame = None

        self.cap = cv2.VideoCapture(0)

        thread = threading.Thread(target=self.run)
        thread.start()

        #
        # self.picam2 = Picamera2()
        # controls = {"FrameRate": frame_rate, "ExposureTime": exposure_time, "AnalogueGain": analogue_gain}
        # preview_config = self.picam2.create_preview_configuration(main={"size": size, "format": format},
        #                                                           controls=controls)
        # self.picam2.configure(preview_config)
        # self.picam2.start()

    def run(self):
        fps = 0
        last_print_time = time.time()

        while not self.end.is_set():
            if self.photo_event.is_set():
                # self.flash_control.start_flash()
                ret, self.last_frame = self.cap.read()
                self.photo_done_event.set()
            else:
                _, frame= self.cap.read()
                if self.show_preview:
                    cv2.imshow("preview", frame)
                    cv2.waitKey(1)

            if self.print_fps:
                fps += 1
                if time.time() - last_print_time > 1:
                    last_print_time = time.time()
                    print(fps)
                    fps = 0
        self.cap.release()

    def start_photo(self):
        self.photo_event.set()
        self.photo_done_event.clear()

    def is_done(self):
        return self.photo_done_event.is_set()

    def get_photo(self):
        return self.last_frame.copy()

    def close(self):
        self.end.set()


class PrinterControl:
    def __init__(self, test, wait_for_print):
        self.test = test
        if not self.test:
            self.conn = cups.Connection()
            printers = self.conn.getPrinters()
            self.default_printer = list(printers.keys())[0]
            cups.setUser('kidier')

        self.end = threading.Event()
        self.print_done_event = threading.Event()
        self.print_changed = threading.Event()
        self.print_queue = Queue()
        self.wait_for_print = wait_for_print

        thread = threading.Thread(target=self.run)
        thread.start()

    def run(self):
        rate = Rate(10)

        while not self.end.is_set():
            if not self.print_queue.empty():
                self.print_changed.set()
                self.print_done_event.clear()
                filename = self.print_queue.get()
                if not self.test:
                    self.conn.printFile(self.default_printer, filename, "boothy", {'fit-to-page': 'True'})
                print("Print job successfully created: ", filename)
                print("Sleeping for:", self.wait_for_print)
                time.sleep(self.wait_for_print)
            else:
                self.print_done_event.set()

            rate.sleep()

    def changed(self):
        val = self.print_changed.is_set()
        self.print_changed.clear()
        return val

    def is_done(self):
        return self.print_done_event.is_set()

    def add(self, filename):
        self.print_done_event.clear()
        self.print_queue.put(filename)

    def get_print_size(self):
        return self.print_queue.qsize()

    def close(self):
        self.end.set()


class States(IntEnum):
    HOME = 0
    PREPARE = 1
    COUNTDOWN_1 = 2
    PHOTO_1 = 3
    COUNTDOWN_2 = 4
    PHOTO_2 = 5
    COUNTDOWN_3 = 6
    PHOTO_3 = 7
    CONFIRM_PRINT = 8
    PRINT = 9


# class ResourceTypes(IntEnum):
#     IMAGE = 0
#     VIDEO = 1

def draw_centered_text(text, image, font):
    max_w, _ = image.size
    draw = ImageDraw.Draw(image)

    lines = text.split("\n")

    current_h, pad = 10, 10
    for line in lines:
        w, h = draw.textsize(line, font=font)
        draw.text(((max_w - w) / 2, current_h), line, font=font)
        current_h += h + pad
    return image


class MainWindow:
    def __init__(self, camera_control: CameraControlSim, printer: PrinterControl, size=(1080, 1920), fps=30,
                 home_file="resources/fotobudka_home.mp4",
                 countdown_file="resources/countdown_675_1080_reduced.mp4",
                 top_text_size=(1060, 400), top_text_pos=(10, 30), bot_text_size=(1060, 400), bot_text_pos=(10, 1490),
                 frame_preview_size=(1014, 540), frame_preview_pos=(33, 500), frame_preview_timeout=2.0,
                 font="resources/tahoma_font.ttf", font_size=130,
                 output_image_background_filename="resources/pasek.png",
                 print_background_filename="resources/print_background.png", output_image_size=(620, 1748),
                 print_image_size=(1240, 1748),
                 small_img_size=(573, 343),
                 small_img_1_pos=(22, 103), small_img_2_pos=(22, 533), small_img_3_pos=(22, 963),
                 confirm_img_preview_size=(434, 1224), confirm_img_preview_pos=(323, 30),
                 confirm_text_size=(1060, 600), confirm_text_pos=(10, 1280), confirm_text_font_size=100, max_prints=4,
                 print_confirm_timeout=15, save_path="saved_images", show_sleep_time=True, test=False,
                 default_how_many_prints=2):

        now = datetime.now()

        dt_string = now.strftime("%Y_%m_%d_%H_%M_%S")

        self.images_save_path = os.path.join(save_path, dt_string)

        os.makedirs(self.images_save_path, exist_ok=True)

        self.printer = printer

        self.current_state = States.HOME

        self.width = size[0]
        self.height = size[1]

        self.show_sleep_time = show_sleep_time

        self.top_text_pos = top_text_pos
        self.bot_text_pos = bot_text_pos
        self.top_text_size = top_text_size
        self.bot_text_size = bot_text_size

        self.frame_preview_size = frame_preview_size
        self.frame_preview_pos = frame_preview_pos

        self.confirm_image_preview_pos = confirm_img_preview_pos
        self.confirm_image_preview_size = confirm_img_preview_size

        self.confirm_text_pos = confirm_text_pos
        self.confirm_text_size = confirm_text_size

        self.empty_image_top_text = Image.new('RGB', self.top_text_size)
        self.empty_image_bot_text = Image.new('RGB', self.bot_text_size)
        self.empty_image_confirm_text = Image.new('RGB', self.confirm_text_size)

        self.empty_background = np.zeros((self.height, self.width, 3), np.uint8)

        self.font = ImageFont.truetype(font, font_size)
        self.confirm_font = ImageFont.truetype(font, confirm_text_font_size)

        self.home_resource, self.home_resource_size = self.read_file(home_file)
        self.home_resource_id = 0

        self.countdown_resource, self.countdown_resource_size = self.read_file(countdown_file)
        self.countdown_resource_id = 0

        self.fps = fps

        self.frame_preview_time_start = time.time()
        self.frame_preview_timeout = frame_preview_timeout

        self.camera_control = camera_control

        self.photo_main_screen = None

        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None

        self.output_image_background = cv2.resize(cv2.imread(output_image_background_filename), output_image_size)
        self.output_image = None

        self.print_background = cv2.resize(cv2.imread(print_background_filename), print_image_size)
        self.print_image_size = print_image_size
        self.print_image = None
        self.print_image_path = ""

        self.small_img_1_pos = small_img_1_pos
        self.small_img_2_pos = small_img_2_pos
        self.small_img_3_pos = small_img_3_pos
        self.small_img_size = small_img_size

        self.top_texts = ["Rewelacyjnie!", "Czadowo!", "Gitówa!", "Całkiem, całkiem!", "Pięknie!", 'Bomba!', 'Sztos!']
        self.bot_texts = ["Nadchodzi", "Teraz", "Przybywa", "Już za chwilę", "Trzy, dwa, jeden", "Wkracza", "Wskakuje",
                          "Wlatuje"]

        self.current_texts_top_id = []
        self.current_texts_bot_id = []

        self.default_how_many_prints = default_how_many_prints
        self.how_many_prints = self.default_how_many_prints
        self.max_prints = max_prints
        self.print_confirm_timeout = print_confirm_timeout
        self.update_print_screen = False

        self.save_id = 0

        self.reset()
        self.test = test
        if not self.test:
            _ = cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
            cv2.moveWindow("window", 0, 0)
            cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def reset(self):
        self.current_state = States.HOME
        self.how_many_prints = self.default_how_many_prints

        self.photo_main_screen = None

        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None

        self.output_image = None
        self.print_image = None

        self.save_id += 1

        while len(self.current_texts_bot_id) < 4:
            text_id = random.randint(0, len(self.bot_texts) - 1)

            if not (text_id in self.current_texts_bot_id):
                self.current_texts_bot_id.append(text_id)

        while len(self.current_texts_top_id) < 4:
            text_id = random.randint(0, len(self.top_texts) - 1)

            if not (text_id in self.current_texts_top_id):
                self.current_texts_top_id.append(text_id)

    def run(self):
        rate = Rate(self.fps)
        frame = self.empty_background.copy()
        while True:

            if self.current_state == States.HOME:
                frame = self.handle_home()

            elif self.current_state == States.PREPARE:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen("Przygotuj się do\nzdjęcia!",
                                                                             self.bot_texts[
                                                                                 self.current_texts_bot_id[0]]
                                                                             + "\nZdjęcie nr 1", None)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = States.COUNTDOWN_1

            elif self.current_state == States.PHOTO_1:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[1]],
                        self.bot_texts[self.current_texts_bot_id[1]]
                        + "\nZdjęcie nr 2", self.frame_1)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = States.COUNTDOWN_2

            elif self.current_state == States.PHOTO_2:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[2]],
                        self.bot_texts[self.current_texts_bot_id[2]]
                        + "\nZdjęcie nr 3", self.frame_2)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = States.COUNTDOWN_3

            elif self.current_state == States.PHOTO_3:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[3]],
                        None, self.frame_3)
                frame = self.photo_main_screen
                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout / 2:
                    self.generate_output_image()
                    self.save_images()
                    self.photo_main_screen = None
                    self.current_state = States.CONFIRM_PRINT
                    self.frame_preview_time_start = time.time()

            elif self.current_state == States.COUNTDOWN_1 or self.current_state == States.COUNTDOWN_2 or \
                    self.current_state == States.COUNTDOWN_3:
                frame, done = self.handle_countdown()

                if done:
                    self.camera_control.start_photo()

                    while not self.camera_control.is_done():
                        time.sleep(0.05)

                    if self.current_state == States.COUNTDOWN_1:
                        self.frame_1 = self.camera_control.get_photo()
                        self.current_state = States.PHOTO_1
                    elif self.current_state == States.COUNTDOWN_2:
                        self.frame_2 = self.camera_control.get_photo()
                        self.current_state = States.PHOTO_2
                    elif self.current_state == States.COUNTDOWN_3:
                        self.frame_3 = self.camera_control.get_photo()
                        self.current_state = States.PHOTO_3

                    self.frame_preview_time_start = time.time()
                    self.countdown_resource_id = 0
                    self.photo_main_screen = None

            elif self.current_state == States.CONFIRM_PRINT:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_confirm_screen \
                        ("Wciśnij przycisk,\naby wydrukować!\nPoczekaj " + str(self.print_confirm_timeout) +
                         " sekund,\naby anulować!", self.output_image)

                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.print_confirm_timeout:
                    self.reset()

            elif self.current_state == States.PRINT:
                if self.photo_main_screen is None or self.update_print_screen or self.printer.changed():
                    text = "Wciśnij przycisk,\naby wydrukować\nwięcej kopii!\nDrukuję " + \
                           str(self.how_many_prints - self.printer.get_print_size()) + " z " + \
                           str(self.how_many_prints) + "..."

                    self.photo_main_screen = self.generate_photo_confirm_screen(text, self.output_image)
                    self.update_print_screen = False

                frame = self.photo_main_screen

                if self.printer.is_done():
                    self.reset()

            if self.show_sleep_time:
                sleep_millis = rate.get_remaining_time_millis_cv2()
                empty = np.zeros((40, 40, 3), np.uint8)
                frame[:40, :40] = empty
                cv2.putText(frame, str(sleep_millis), (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1, 2)

            if self.test:
                frame = cv2.resize(frame, (540, 960))
            cv2.imshow("window", frame)

            sleep_millis = rate.get_remaining_time_millis_cv2()

            key = cv2.waitKey(sleep_millis)
            rate.update_last_time()

            if key == ord("q"):
                print("Closing!")
                break
            elif key == ord(" "):
                self.button_click()

    def generate_photo_confirm_screen(self, bot_text, preview):
        frame = self.empty_background.copy()
        frame = self.set_bot_text_confirm(frame, bot_text)
        frame = self.set_confirm_frame_preview(frame, preview)

        return frame

    def generate_output_image(self):
        self.output_image = self.output_image_background.copy()

        w = self.small_img_size[0]
        h = self.small_img_size[1]

        x1 = self.small_img_1_pos[0]
        x2 = self.small_img_2_pos[0]
        x3 = self.small_img_3_pos[0]
        y1 = self.small_img_1_pos[1]
        y2 = self.small_img_2_pos[1]
        y3 = self.small_img_3_pos[1]

        f1 = cv2.resize(self.frame_1, (w, h))
        f2 = cv2.resize(self.frame_2, (w, h))
        f3 = cv2.resize(self.frame_3, (w, h))

        self.output_image[y1:y1 + h, x1:x1 + w] = f1
        self.output_image[y2:y2 + h, x2:x2 + w] = f2
        self.output_image[y3:y3 + h, x3:x3 + w] = f3

        self.print_image = self.print_background.copy()
        self.print_image[0:self.print_image_size[1], 0:int(self.print_image_size[0] / 2)] = self.output_image

    def save_images(self):
        save_path = os.path.join(self.images_save_path, str(self.save_id))
        os.makedirs(save_path, exist_ok=True)
        cv2.imwrite(os.path.join(save_path, "1.png"), self.frame_1)
        cv2.imwrite(os.path.join(save_path, "2.png"), self.frame_2)
        cv2.imwrite(os.path.join(save_path, "3.png"), self.frame_3)
        cv2.imwrite(os.path.join(save_path, "pasek.png"), self.output_image)

        self.print_image_path = os.path.join(save_path, "print.png")
        cv2.imwrite(self.print_image_path, self.print_image)
        print("Saved images!")

    def generate_photo_main_screen(self, top_text, bot_text, preview):
        frame = self.empty_background.copy()

        if top_text is not None:
            frame = self.set_top_text(frame, top_text)
        if bot_text is not None:
            frame = self.set_bot_text(frame, bot_text)
        if preview is not None:
            frame = self.set_frame_preview(frame, preview)
        return frame

    def set_bot_text_confirm(self, frame, text):
        image = draw_centered_text(text, self.empty_image_confirm_text.copy(), self.confirm_font)
        cv2_im_processed = np.array(image)
        x0 = self.confirm_text_pos[0]
        x1 = self.confirm_text_size[0] + self.confirm_text_pos[0]
        y0 = self.confirm_text_pos[1]
        y1 = self.confirm_text_size[1] + self.confirm_text_pos[1]
        frame[y0:y1, x0:x1] = cv2_im_processed

        return frame

    def set_confirm_frame_preview(self, frame, preview):
        x0 = self.confirm_image_preview_pos[0]
        x1 = self.confirm_image_preview_size[0] + self.confirm_image_preview_pos[0]
        y0 = self.confirm_image_preview_pos[1]
        y1 = self.confirm_image_preview_size[1] + self.confirm_image_preview_pos[1]
        preview = cv2.resize(preview, self.confirm_image_preview_size)
        frame[y0:y1, x0:x1] = preview

        return frame

    def set_bot_text(self, frame, text):
        image = draw_centered_text(text, self.empty_image_bot_text.copy(), self.font)
        cv2_im_processed = np.array(image)
        x0 = self.bot_text_pos[0]
        x1 = self.bot_text_size[0] + self.bot_text_pos[0]
        y0 = self.bot_text_pos[1]
        y1 = self.bot_text_size[1] + self.bot_text_pos[1]
        frame[y0:y1, x0:x1] = cv2_im_processed

        return frame

    def set_top_text(self, frame, text):
        image = draw_centered_text(text, self.empty_image_top_text.copy(), self.font)
        cv2_im_processed = np.array(image)
        x0 = self.top_text_pos[0]
        x1 = self.top_text_size[0] + self.top_text_pos[0]
        y0 = self.top_text_pos[1]
        y1 = self.top_text_size[1] + self.top_text_pos[1]
        frame[y0:y1, x0:x1] = cv2_im_processed

        return frame

    def set_frame_preview(self, frame, preview):
        x0 = self.frame_preview_pos[0]
        x1 = self.frame_preview_size[0] + self.frame_preview_pos[0]
        y0 = self.frame_preview_pos[1]
        y1 = self.frame_preview_size[1] + self.frame_preview_pos[1]
        preview = cv2.resize(preview, self.frame_preview_size)
        frame[y0:y1, x0:x1] = preview

        return frame

    def button_click(self):
        print("Button click")

        if self.current_state == States.HOME:
            self.current_state = States.PREPARE
            self.frame_preview_time_start = time.time()
        elif self.current_state == States.CONFIRM_PRINT:
            self.current_state = States.PRINT
            for _ in range(self.how_many_prints):
                self.printer.add(self.print_image_path)
            self.photo_main_screen = None

        elif self.current_state == States.PRINT:
            if self.how_many_prints < self.max_prints:
                print("Print more!")
                self.printer.add(self.print_image_path)
                self.how_many_prints += 1
                self.update_print_screen = True

    def handle_home(self):
        if self.home_resource_size == 1:
            return self.home_resource
        else:
            resource = self.home_resource[self.home_resource_id]

            if self.home_resource_id < self.home_resource_size - 1:
                self.home_resource_id += 1
            else:
                self.home_resource_id = 0

            return resource

    def handle_countdown(self):
        done = False
        resource = self.countdown_resource[self.countdown_resource_id]

        if self.countdown_resource_id < self.countdown_resource_size - 1:
            self.countdown_resource_id += 1
        else:
            done = True
        return resource, done

    def read_file(self, filename):
        values = filename.split(".")

        img_types = ["png", "jpg", "jpeg"]
        video_types = ["avi", "mp4"]

        if len(values) != 2:
            print("Wrong filename: " + filename)
            exit(0)
        else:
            if values[1] in img_types:
                img = cv2.imread(filename)
                img = cv2.resize(img, (self.width, self.height))
                return img, 1
            elif values[1] in video_types:
                images = []
                cap = cv2.VideoCapture(filename)

                while cap.isOpened():
                    ret, img = cap.read()
                    if ret:
                        img = cv2.resize(img, (self.width, self.height))
                        images.append(img)
                    else:
                        break
                return images, len(images)

            else:
                print("Wrong file format for: " + filename + " Available formats: " + str(img_types) + ", "
                      + str(video_types))
                exit(0)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Fotobudka',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', help='json config file path', default='default_config.json', type=str)
    args = parser.parse_args()

    f = open(args.config)
    data = json.load(f)
    f.close()

    printer_control = PrinterControl(data["main_window"]["test"], 19)

    if not data["main_window"]["test"]:
        from picamera2 import Picamera2
        import RPi.GPIO as GPIO

        flash_control = FlashControl(gpio_pin=data["flash"]["gpio_pin"])

        camera_control = CameraControl(flash_control, frame_rate=data["camera"]["frame_rate"],
                                       exposure_time=data["camera"]["exposure_time"],
                                       analogue_gain=data["camera"]["analogue_gain"],
                                       size=data["camera"]["size"],
                                       img_format=data["camera"]["img_format"],
                                       print_fps=data["camera"]["print_fps"],
                                       show_preview=data["camera"]["show_preview"])
    else:
        camera_control = CameraControlSim(None, show_preview=data["camera"]["show_preview"], print_fps=data["camera"]["print_fps"])

    main_window = MainWindow(camera_control, printer_control,
                             size=data["main_window"]["size"],
                             fps=data["main_window"]["fps"],
                             home_file=data["main_window"]["home_file"],
                             countdown_file=data["main_window"]["countdown_file"],
                             top_text_size=data["main_window"]["top_text_size"],
                             top_text_pos=data["main_window"]["top_text_pos"],
                             bot_text_size=data["main_window"]["bot_text_size"],
                             bot_text_pos=data["main_window"]["bot_text_pos"],
                             frame_preview_size=data["main_window"]["frame_preview_size"],
                             frame_preview_pos=data["main_window"]["frame_preview_pos"],
                             frame_preview_timeout=data["main_window"]["frame_preview_timeout"],
                             font=data["main_window"]["font"],
                             font_size=data["main_window"]["font_size"],
                             output_image_background_filename=data["main_window"]["output_image_background_filename"],
                             print_background_filename=data["main_window"]["print_background_filename"],
                             output_image_size=data["main_window"]["output_image_size"],
                             print_image_size=data["main_window"]["print_image_size"],
                             small_img_size=data["main_window"]["small_img_size"],
                             small_img_1_pos=data["main_window"]["small_img_1_pos"],
                             small_img_2_pos=data["main_window"]["small_img_2_pos"],
                             small_img_3_pos=data["main_window"]["small_img_3_pos"],
                             confirm_img_preview_size=data["main_window"]["confirm_img_preview_size"],
                             confirm_img_preview_pos=data["main_window"]["confirm_img_preview_pos"],
                             confirm_text_size=data["main_window"]["confirm_text_size"],
                             confirm_text_pos=data["main_window"]["confirm_text_pos"],
                             confirm_text_font_size=data["main_window"]["confirm_text_font_size"],
                             max_prints=data["main_window"]["max_prints"],
                             print_confirm_timeout=data["main_window"]["print_confirm_timeout"],
                             save_path=data["main_window"]["save_path"],
                             default_how_many_prints=data["main_window"]["default_how_many_prints"],
                             show_sleep_time=data["main_window"]["show_sleep_time"],
                             test=data["main_window"]["test"])
    main_window.run()

    if not data["main_window"]["test"]:
        flash_control.close()

    printer_control.close()
    camera_control.close()
    cv2.destroyAllWindows()
