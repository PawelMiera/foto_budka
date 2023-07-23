import cv2

import threading
import time
from enum import IntEnum
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import random


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
    def __init__(self) -> None:
        print("Starting flash")
        self.flash_event = threading.Event()
        self.end = threading.Event()
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(22, GPIO.OUT)

        GPIO.output(22, GPIO.HIGH)

        for _ in range(2):
            GPIO.output(22, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(22, GPIO.HIGH)
            time.sleep(0.2)

        thread = threading.Thread(target=self.run)
        thread.start()

    def start_flash(self):
        self.flash_event.set()

    def run(self):
        rate = Rate(100)

        while not self.end.is_set():
            if self.flash_event.is_set():
                GPIO.output(22, GPIO.LOW)
                time.sleep(0.1)
                GPIO.output(22, GPIO.HIGH)
                self.flash_event.clear()

            rate.sleep()
        GPIO.cleanup()  # cleanup all GPIO

    def close(self):
        self.end.set()


class CameraControl:
    def __init__(self, flash_control: FlashControl, frame_rate=5, exposure_time=300000, analogue_gain=8.0,
                 size=(2028, 1080), img_format="RGB888", print_fps=False):
        self.print_fps = print_fps

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
                _ = self.picam2.capture_array()

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
                 size=(2028, 1080), img_format="RGB888", print_fps=False):
        self.print_fps = print_fps

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
                _, _ = self.cap.read()

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


class State(IntEnum):
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
    MAX_W, MAX_H = image.size
    draw = ImageDraw.Draw(image)

    lines = text.split("\n")

    current_h, pad = 10, 10
    for line in lines:
        w, h = draw.textsize(line, font=font)
        draw.text(((MAX_W - w) / 2, current_h), line, font=font)
        current_h += h + pad
    return image


class MainWindow:
    def __init__(self, camera_control: CameraControlSim, size=(1080, 1920), fps=30,
                 home_file="resources/fotobudka_home.mp4",
                 countdown_file="resources/countdown_675_1080_reduced.mp4",
                 top_font_size=(1060, 400), top_font_pos=(10, 30), bot_font_size=(1060, 400), bot_font_pos=(10, 1490),
                 frame_preview_size=(1014, 540), frame_preview_pos=(33, 500), frame_preview_timeout=2.0,
                 font="resources/tahoma_font.ttf", font_size=130,
                 output_image_background_filename="resources/pasek.png",
                 print_background="resources/print_background.png", output_image_size=(620, 1748),
                 print_image_size=(1240, 1748),
                 small_img_size=(573, 343),
                 small_img_1_pos=(22, 103), small_img_2_pos=(22, 533), small_img_3_pos=(22, 963),
                 confirm_img_preview_size=(434, 1224), confirm_img_preview_pos=(323, 30),
                 confirm_text_size=(1060, 600), confirm_text_pos=(10, 1280), confirm_text_font_size=100,
                 show_sleep_time=True):

        self.current_state = State.HOME

        self.width = size[0]
        self.height = size[1]

        self.show_sleep_time = show_sleep_time

        self.top_font_pos = top_font_pos
        self.bot_font_pos = bot_font_pos
        self.top_font_size = top_font_size
        self.bot_font_size = bot_font_size

        self.frame_preview_size = frame_preview_size
        self.frame_preview_pos = frame_preview_pos

        self.confirm_image_preview_pos = confirm_img_preview_pos
        self.confirm_image_preview_size = confirm_img_preview_size

        self.confirm_text_pos = confirm_text_pos
        self.confirm_text_size = confirm_text_size

        self.empty_image_top_font = Image.new('RGB', self.top_font_size)
        self.empty_image_bop_font = Image.new('RGB', self.bot_font_size)
        self.empty_image_confirm_text = Image.new('RGB', self.confirm_text_size)

        self.empty_background = np.zeros((self.height, self.width, 3), np.uint8)

        self.font = ImageFont.truetype(font, font_size)
        self.confirm_font = ImageFont.truetype(font, confirm_text_font_size)

        # image = draw_centered_text("Wciśnij przycisk,\n aby wydrukować!\nPoczekaj 15 sekund,\n aby anulować!",
        #                    self.empty_image_top_font.copy(), self.font)
        #
        # cv2_im_processed = np.array(image)
        #
        # cv2.imshow("XD", cv2_im_processed)
        # cv2.waitKey(0)

        self.home_resource, self.home_resource_size = self.read_file(home_file)
        self.home_resource_id = 0

        self.countdown_resource, self.countdown_resource_size = self.read_file(countdown_file)
        self.countdown_resource_id = 0

        self.fps = fps

        self.current_state = 0
        self.how_many_prints = 1
        self.current_print = 0
        self.frame_preview_time_start = time.time()
        self.frame_preview_timeout = frame_preview_timeout

        self.camera_control = camera_control

        self.photo_main_screen = None

        self.frame_1 = None
        self.frame_2 = None
        self.frame_3 = None

        self.output_image_background = cv2.resize(cv2.imread(output_image_background_filename), output_image_size)
        self.output_image = None
        self.img_id = 0

        self.print_background = cv2.resize(cv2.imread(print_background), print_image_size)
        self.print_image_size = print_image_size
        self.print_image = None

        self.small_img_1_pos = small_img_1_pos
        self.small_img_2_pos = small_img_2_pos
        self.small_img_3_pos = small_img_3_pos
        self.small_img_size = small_img_size

        self.top_texts = ["Rewelacyjnie!", "Czadowo!", "Gitówa!", "Całkiem, całkiem!", "Pięknie!", 'Bomba!', 'Sztos!']
        self.bot_texts = ["Nadchodzi", "Teraz", "Przybywa", "Już za chwilę", "Trzy, dwa, jeden", "Wkracza", "Wskakuje",
                          "Wlatuje"]

        self.current_texts_top_id = []
        self.current_texts_bot_id = []

        self.reset()

        # _ = cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
        # cv2.moveWindow("window", 0, 0)
        # cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def reset(self):
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

            if self.current_state == State.HOME:
                frame = self.handle_home()

            elif self.current_state == State.PREPARE:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen("Przygotuj się do\nzdjęcia!",
                                                                             self.bot_texts[
                                                                                 self.current_texts_bot_id[0]]
                                                                             + "\nZdjęcie nr 1", None)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = State.COUNTDOWN_1

            elif self.current_state == State.PHOTO_1:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[1]],
                        self.bot_texts[self.current_texts_bot_id[1]]
                        + "\nZdjęcie nr 2", self.frame_1)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = State.COUNTDOWN_2

            elif self.current_state == State.PHOTO_2:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[2]],
                        self.bot_texts[self.current_texts_bot_id[2]]
                        + "\nZdjęcie nr 3", self.frame_2)
                frame = self.photo_main_screen

                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout:
                    self.current_state = State.COUNTDOWN_3

            elif self.current_state == State.PHOTO_3:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_main_screen(
                        self.top_texts[self.current_texts_top_id[3]],
                        None, self.frame_3)
                frame = self.photo_main_screen
                if time.time() - self.frame_preview_time_start > self.frame_preview_timeout / 2:
                    self.generate_output_image()
                    self.photo_main_screen = None
                    self.current_state = State.CONFIRM_PRINT

            elif self.current_state == State.COUNTDOWN_1 or self.current_state == State.COUNTDOWN_2 or \
                    self.current_state == State.COUNTDOWN_3:
                frame, done = self.handle_countdown()

                if done:
                    self.camera_control.start_photo()

                    while not self.camera_control.is_done():
                        time.sleep(0.05)

                    if self.current_state == State.COUNTDOWN_1:
                        self.frame_1 = self.camera_control.get_photo()
                        self.current_state = State.PHOTO_1
                    elif self.current_state == State.COUNTDOWN_2:
                        self.frame_2 = self.camera_control.get_photo()
                        self.current_state = State.PHOTO_2
                    elif self.current_state == State.COUNTDOWN_3:
                        self.frame_3 = self.camera_control.get_photo()
                        self.current_state = State.PHOTO_3

                    self.frame_preview_time_start = time.time()
                    self.countdown_resource_id = 0
                    self.photo_main_screen = None

            elif self.current_state == State.CONFIRM_PRINT:
                if self.photo_main_screen is None:
                    self.photo_main_screen = self.generate_photo_confirm_screen \
                        ("Wciśnij przycisk,\naby wydrukować!\nPoczekaj 15 sekund,\naby anulować!", self.output_image)

                frame = self.photo_main_screen

            if self.show_sleep_time:
                sleep_millis = rate.get_remaining_time_millis_cv2()
                empty = np.zeros((40, 40, 3), np.uint8)
                frame[:40, :40] = empty
                cv2.putText(frame, str(sleep_millis), (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1, 2)

            cv2.imshow("window", cv2.resize(frame, (540, 960)))

            sleep_millis = rate.get_remaining_time_millis_cv2()

            key = cv2.waitKey(sleep_millis)
            rate.update_last_time()

            if key == ord("q"):
                break
            elif key == ord(" "):
                print("Click")
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
        image = draw_centered_text(text, self.empty_image_top_font.copy(), self.font)
        cv2_im_processed = np.array(image)
        x0 = self.bot_font_pos[0]
        x1 = self.bot_font_size[0] + self.bot_font_pos[0]
        y0 = self.bot_font_pos[1]
        y1 = self.bot_font_size[1] + self.bot_font_pos[1]
        frame[y0:y1, x0:x1] = cv2_im_processed

        return frame

    def set_top_text(self, frame, text):
        image = draw_centered_text(text, self.empty_image_top_font.copy(), self.font)
        cv2_im_processed = np.array(image)
        x0 = self.top_font_pos[0]
        x1 = self.top_font_size[0] + self.top_font_pos[0]
        y0 = self.top_font_pos[1]
        y1 = self.top_font_size[1] + self.top_font_pos[1]
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
        if self.current_state == State.HOME:
            self.current_state = State.PREPARE
            self.frame_preview_time_start = time.time()
        elif self.current_state == State.CONFIRM_PRINT:
            pass
        # if self.current_state == 0:
        #     self.current_state += 1

        # self.set_top_text("Przygotuj się do zdjęcia!")
        #
        # self.set_bot_text(self.bop_texts[self.current_texts_bot_id[0]] + "<br>Zdjęcie nr 1")
        #
        # self.sleep(self.wait_before_countdown)
        #
        # self.set_top_text("")
        # self.set_bot_text("")
        #
        # self.countdown_shower.start_counting()

        # elif self.current_state == 4:
        #     self.current_state += 1
        #     self.timer.stop()
        #     self.print()
        #     self.reset()
        # elif self.current_state == 5:
        #     if self.how_many_prints < self.max_prints:
        #         print("Print more!")
        #         self.how_many_prints += 1
        #         self.set_bot_text("Wciśnij przycisk, aby wydrukować więcej kopii!<br>Drukuję " + str(
        #             self.current_print + 1) + " z " + str(self.how_many_prints) + "...", 65)

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
    test = True
    if not test:
        from picamera2 import Picamera2
        import RPi.GPIO as GPIO

        flash_control = FlashControl()

        camera_control = CameraControl(flash_control)
    else:
        camera_control = CameraControlSim(None)

    main_window = MainWindow(camera_control)
    main_window.run()

    if not test:
        flash_control.close()

    camera_control.close()
    cv2.destroyAllWindows()
