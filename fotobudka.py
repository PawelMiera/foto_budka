import cv2
# from picamera2 import Picamera2
# import RPi.GPIO as GPIO
import threading
import time
from enum import IntEnum
import numpy as np


class Rate:
    def __init__(self, rate):
        self.rate_time = 1.0 / rate
        self.last_time = time.time()

    def sleep(self):
        now = time.time()
        time_diff = now - self.last_time
        sleep_time = self.rate_time - time_diff
        self.last_time = now
        if sleep_time > 0:
            time.sleep(sleep_time)

    def get_remaining_time_millis(self):
        now = time.time()
        time_diff = now - self.last_time
        sleep_time = self.rate_time - time_diff
        self.last_time = now
        if sleep_time > 0:
            return int(sleep_time * 1000)
        else:
            return 1


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
                 size=(2028, 1080), format="RGB888", print_fps=False):
        self.print_fps = print_fps

        self.end = threading.Event()
        self.photo_event = threading.Event()
        self.photo_done_event = threading.Event()
        self.flash_control = flash_control
        self.last_frame = None

        self.picam2 = Picamera2()
        controls = {"FrameRate": frame_rate, "ExposureTime": exposure_time, "AnalogueGain": analogue_gain}
        preview_config = self.picam2.create_preview_configuration(main={"size": size, "format": format},
                                                                  controls=controls)
        self.picam2.configure(preview_config)
        self.picam2.start()

    def run(self):
        fps = 0
        last_print_time = time.time()

        while not self.end.is_set():
            if self.photo_event.is_set():
                self.flash_control.start_flash()
                self.last_frame = self.picam2.capture_array()
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

    def close(self):
        self.end.set()


class State(IntEnum):
    HOME = 0
    COUNTDOWN_1 = 1
    PHOTO_1 = 2
    COUNTDOWN_2 = 3
    PHOTO_2 = 4
    COUNTDOWN_3 = 5
    PHOTO_3 = 6
    PRINT = 7


# class ResourceTypes(IntEnum):
#     IMAGE = 0
#     VIDEO = 1


class MainWindow:
    def __init__(self, width=1080, height=1920, home_file="countdown_675_1080_reduced.mp4"):

        self.current_state = State.HOME

        self.width = width
        self.height = height

        self.home_resource, self.home_resource_size = self.read_file(home_file)
        self.home_resource_id = 0

        # _ = cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
        # cv2.moveWindow("window", 0, 0)
        # cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def run(self):
        rate = Rate(30)
        while True:

            if self.current_state == State.HOME:
                frame = self.handle_home()

                cv2.imshow("window", frame)

            sleep_millis = rate.get_remaining_time_millis()
            print(sleep_millis)
            key = cv2.waitKey(sleep_millis)

            if key == ord("q"):
                break
            elif key == ord(" "):
                print("Click")
                self.button_click()

    def button_click(self):
        if self.current_state == 0:
            self.current_state += 1

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
            self.home_resource_id += 1

            if self.home_resource_id >= self.home_resource_size:
                self.home_resource_id = 0

            return resource

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
    main_window = MainWindow()
    main_window.run()
    # flash_control = FlashControl()
    #
    # camera_control = CameraControl(flash_control)

    # flash_control.close()
    # camera_control.close()
    cv2.destroyAllWindows()
