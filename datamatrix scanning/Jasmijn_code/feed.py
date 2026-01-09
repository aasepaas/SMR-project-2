from abc import ABC, abstractmethod
import cv2

from profile_setup import ScanProfile, standard_profile, wallet_profile, giftbox_profile, barcode_profile

# Debugging
from logging_config import set_up_loger
import logging
logger = logging.getLogger()
set_up_loger()

"""
Verantwoordelijk voor het openen van de camera met de juiste index.
Geeft een frame terug aan de scanner.
"""
class Feed(ABC):
    def __init__(self, name: str, active: bool) -> None:
        self.name = name
        self.isactive = active

    @abstractmethod
    def openFeed(self):
        pass

    # LiveFeed only methods
    def adjust_camera_settings(self, profile: 'ScanProfile', attr_name: str, cap_prop: int, delta: float) -> None:
        """Optional hook: override in LiveFeed to change camera properties.
        Default implementation is a no-op so non-camera feeds (e.g. VideoFeed)
        can be used without raising attribute errors in static analysis.
        """
        return None
    
    def configure_camera(self, profile: 'ScanProfile', set_resolution: bool = False) -> None:
        """Optional hook: override in LiveFeed to configure camera settings.

        Default implementation is a no-op so non-camera feeds (e.g. VideoFeed)
        can safely accept calls like `configure_camera(profile, set_resolution=...)`
        without raising runtime errors.
        """
        return None

    def stop_stream(self):
        """ Optional hook: override in LiveFeed to safely release camera. """
        raise NotImplementedError("stop_stream should be implemented by subclasses that support camera controls")

class PictureFeed(Feed):
    def __init__(self, name, active, file_name) -> None:
        super().__init__(name, active)
        self.file_name = file_name

    def openFeed(self):
        image = cv2.imread(self.file_name)
        while True:
            # if cv2.waitKey(10) == 27:  # Wait until 'esc' key is pressed
            #     raise KeyboardInterrupt("ESC has been pressed")

            yield image


class VideoFeed(Feed):
    def __init__(self, name, active, file_name, acceleration=1.0, loop: bool = False) -> None:
        super().__init__(name, active)
        self.file_name = file_name
        self.acceleration = acceleration
        self.loop = bool(loop)
        
        self.cap = cv2.VideoCapture(self.file_name)
        # fps = self.cap.get(cv2.CAP_PROP_FPS) * self.acceleration
        # wait_time = int(1000 / fps) if fps > 0 else 30
        print(f"Opened video file '{self.file_name}'")
        
    def __del__(self):
        """ Safely release capture. """
        print(f"Stopping video {self.file_name}...")
        self.cap.release()
        
    def openFeed(self):
        while True:
            ret, frame = self.cap.read()
        
            if ret:
                yield frame
                
            if not self.loop:
                print("\nEnd of video...\n")
                break
            
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
            
   
class LiveFeed(Feed):
    def __init__(self, name, active, camera_index: int) -> None:
        super().__init__(name, active)
        self.camera_index = camera_index
        
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened(): 
            logger.error("Cannot initialize video capture")
            raise ValueError("Try a different camera_index")
        
        # Initial configuration with resolution setting
        self.configure_camera(profile=standard_profile, set_resolution=True)

    def __del__(self):
        """ Safely release camera. """
        print("Releasing camera...")
        self.cap.release()       
        
    def openFeed(self):          
        # grabbed = self.cap.grab()  # Discard frame to reduce latency
        # retrieved, frame = self.cap.retrieve()  # Retrieve the latest frame
        # if not retrieved:
        #     print("\nFailed to retrieve frame...\n")
        #     break
        try: 
            while True: #self.isactive:             
                ret, frame = self.cap.read()
                if not ret:
                    print("\nNo longer connected to camera...\n")
                    break
                # if self.camera_index == 0: 
                #     frame = cv2.rotate(frame, cv2.ROTATE_180)  # Mirror for internal camera
                yield frame
        finally:
            self.__del__
            
    def configure_camera(self, profile: ScanProfile, set_resolution: bool = False) -> None: 
        """ Apply all camera settings from the profile (single source of truth."""
        
        # Resolution: only set during initialization to avoid MSMF stream errors
        if set_resolution:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            self.cap.set(cv2.CAP_PROP_FPS, 30)  # Set desired FPS
            self.cap.get(cv2.CAP_PROP_FPS)  # Confirm FPS setting
            logger.info(f"Camera {self.camera_index} ({self.name}) FPS set to: {self.cap.get(cv2.CAP_PROP_FPS)}")
            self.try_to_set_camera_frame()

        if profile.focus is not None:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # Turn off auto focus
            self.cap.set(cv2.CAP_PROP_FOCUS, profile.focus)
        else:   
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Turn on auto focus
            
        if profile.exposure is not None:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Turn off auto exposure: 0.25 of 0
            self.cap.set(cv2.CAP_PROP_EXPOSURE, profile.exposure)    
        else:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)  # Turn on auto exposure
            
        if profile.brightness is not None:
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, profile.brightness)
        else:
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 100)  # Use a default brightness

    def adjust_camera_settings(self, profile: ScanProfile, attr_name: str, cap_prop: int, delta: float) -> None:
        """Adjust a camera setting by delta and persist to profile."""
        value = getattr(profile, attr_name, None)
        #-=x Not needed to check cap is valid here?? x=-
        if value is not None: # and self.cap is not None: #! Check if value and cap are valid
            value += delta
            setattr(profile, attr_name, value)
            self.cap.set(cap_prop, value)
            logger.debug(f"{attr_name.capitalize()} {'omhoog' if delta>0 else 'omlaag'} -> {value}")
                     
    def get_camera_info(self):
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        return width, height, fps
    
    def try_to_set_camera_frame(self):
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        except Exception:
            try:
                # print(f"Could not set 4K resolution on camera {self.camera_index}, trying lower resolution... (1920 x 1080)")
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            except Exception:
                # print(f"Could not set full HD resolution on camera {self.camera_index}, trying lower resolution... (1280 x 720)")
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # print(f"Set camera {self.camera_index} ({self.name}) resolution to: {width} x {height}")
        logger.info(f"Set camera {self.camera_index} ({self.name}) resolution to: {width} x {height}")
        
# Import functions    
def resize_frame(frame, scale: float = 2): # was 1.2 # ratio 640 / 360 = 16:9
    width = int(640 * scale) 
    height = int(360 * scale)       
    resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    return resized

def display_camera_info(*texts, frame, font_scale=0.5):
    thickness = int(2*font_scale)
    spacing = int(40 * font_scale)

    for i, txt in enumerate(texts):
        cv2.putText(frame, txt, (spacing//2, spacing + i*spacing), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)
    
    return frame

        
# =================================================
# Test functions    
# =================================================
def switch_every_n_seconds(switch_n_seconds=5):
    import time

    feed_list = [LiveFeed("Camera Original", True, 0), LiveFeed("Camera 4K Webcam", False, 1)] # Original, 4K Webcam
    streams = [f.openFeed() for f in feed_list]

    current = 0
    last_switch = time.time()

    try:
        logger.info("Starting feed switching test...")
        while True:
            # haal en toon frame alleen van de actieve feed
            if feed_list[current].isactive:
                try:
                    frame = next(streams[current])
                except StopIteration:
                    break
                
                # toon/gebruik frame
                cv2.imshow(feed_list[current].name, resize_frame(frame))
                
            # wisselmoment
            if time.time() - last_switch >= switch_n_seconds:
                # close/hide current window if gewenst
                try:
                    cv2.destroyWindow(feed_list[current].name)
                except Exception:
                    pass
                
                # advance
                current = (current + 1) % len(feed_list)
                for feed in feed_list:
                    feed.isactive = not feed.isactive
                last_switch = time.time()
                logger.info("Switched feed...")
                
            # verwerk key (optioneel)
            if cv2.waitKey(1) & 0xFF == 27:
                break
            
    finally:
        for f in feed_list:
            try:
                f.stop_stream()
            except Exception:
                pass
        cv2.destroyAllWindows()

def test_switchting_feeds(): 
    import time
    feed_list = [LiveFeed("Camera Original", True, 0), LiveFeed("Camera 4K Webcam", True, 1)] # Original, 4K Webcam
        
    # streams = []
    # for feed in feed_list:
    #     streams.append(feed.openFeed())
    streams = [feed.openFeed() for feed in feed_list] # list comprehension
    
    try:
        current_time = time.time() 
        # print("Inside try")
        while True:
            # print("Inside while True")
            if time.time() - current_time < 5:
                feed_list[0].isactive = True
                feed_list[1].isactive = False
            elif time.time() - current_time >= 5 and time.time() - current_time < 10:
                feed_list[0].isactive = False
                feed_list[1].isactive = True
            elif time.time() - current_time >= 10:
                current_time = time.time()
                print("reset current_time")
            
            # # Original
            # if feed1.isactive: 
            #     frame1 = next(stream1)
            #     width, height, fps = feed1.get_camera_info()
            #     frame = display_camera_info(f"Camera Index: {feed1.camera_index}", 
            #             f"Resolution: {width}x{height}", 
            #             f"FPS: {fps:.2f}",
            #             frame=resize_frame(frame1), font_scale=0.5)
            #             # frame=frame, font_scale=1)
            #     cv2.imshow(feed1.name, frame)
        
            # # 4K Webcam
            # if feed2.isactive:
            #     frame2 = next(stream2)
            #     width, height, fps = feed2.get_camera_info()
            #     frame = display_camera_info(f"Camera Index: {feed2.camera_index}", 
            #             f"Resolution: {width}x{height}", 
            #             f"FPS: {fps:.2f}",
            #             frame=resize_frame(frame2), font_scale=0.5)
            #             # frame=frame, font_scale=3)
            #     cv2.imshow(feed2.name, frame)
            
            for feed in feed_list:
                if feed.isactive:
                    frame = next(streams[feed_list.index(feed)])
                    width, height, fps = feed.get_camera_info()
                    display_frame = display_camera_info(f"Camera Index: {feed.camera_index}", 
                            f"Resolution: {width}x{height}", 
                            f"FPS: {fps:.2f}",
                            frame=resize_frame(frame), font_scale=0.5)
                    cv2.imshow(feed.name, display_frame)
                
            # # alternating frames
            # if feed_list[0].isactive:
            #     testframe = next(stream1)
            # elif feed_list[1].isactive: 
            #     testframe = next(stream2)
            # else: 
            #     continue    
            # cv2.imshow("Alternating frame", resize_frame(testframe))            
    finally:
        for feed in feed_list:
            del feed
        # del feed_list[0]
        # del feed_list[1]
        # cv2.destroyAllWindows()

def test_2_feeds(): 
    feed1 = LiveFeed("Camera Original", True, 0) # Original
    feed2 = LiveFeed("Camera 4K Webcam", True, 1) # 4K Webcam

    stream1 = feed1.openFeed()
    stream2 = feed2.openFeed()

    while True:
        frame1 = next(stream1)
        frame2 = next(stream2)
        width, height, fps = feed1.get_camera_info()
        
        # Original
        display_camera_info(f"Camera Index: {feed1.camera_index}", 
                f"Resolution: {width}x{height}", 
                f"FPS: {fps:.2f}",
                # frame=resize(frame1, 1.5), font_scale=0.5)
                frame=frame1, font_scale=1)
        cv2.imshow(feed1.name, resize_frame(frame1))
        
        # 4K Webcam
        width, height, fps = feed2.get_camera_info()
        display_camera_info(f"Camera Index: {feed2.camera_index}", 
                f"Resolution: {width}x{height}", 
                f"FPS: {fps:.2f}",
                # frame=resize(frame2, 1.5), font_scale=0.5)
                frame=frame2, font_scale=3)
        cv2.imshow(feed2.name, resize_frame(frame2))
                    
def test_cam(name, index):
    new = LiveFeed(name, True, index)
    feed = new.openFeed()
    for frame in feed:
        width, height, fps = new.get_camera_info()
        
        display_camera_info(f"Camera Index: {index}", 
                f"Resolution: {width}x{height}", 
                f"FPS: {fps:.2f}",
                frame=frame, font_scale=0.5)

        cv2.imshow(new.name, frame)
      
def simpel_test(index, mode="normal"):
    match mode:
        case "dshow":
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)    # 0 = 4K Webcam, 1 = intern
        case "msmf":
            cap = cv2.VideoCapture(index, cv2.CAP_MSMF)     # 0 = intern, 1 = 4K Webcam
        case _:
            cap = cv2.VideoCapture(index)                   # 0 = intern, 1 = 4K Webcam

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("\nNo longer connected to camera...\n")
                break

            if cv2.waitKey(1) == 27:  # Wait until 'esc' key is pressed
                raise KeyboardInterrupt("ESC has been pressed")
            
            display_camera_info(f"Camera Index: {index}", 
                                f"Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}", 
                                f"FPS: {cap.get(cv2.CAP_PROP_FPS):.2f}",
                                frame=frame, font_scale=0.5)
            
            cv2.imshow(f"Camera {index}", frame)
    finally:
        print("Releasing camera...")
        cap.release()
            
if __name__ == "__main__":
    logger.info("Starting feed test...")
    try: 
        switch_every_n_seconds(switch_n_seconds=5)
        # test_switchting_feeds()
        # test_2_feeds()
        
        # simpel_test(1)
        # simpel_test(0)
        
        # test_cam("test", 1)
        # test_cam("test2", 0)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        
# CAP_DSHOW : 1 = intern, 0 = 4K Webcam # snelste...
# CAP_MSMF  : 0 = intern, 1 = 4K Webcam
# zonder    : 0 = intern, 1 = 4K Webcam