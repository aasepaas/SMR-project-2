
import keyboard
import time
import threading


from feed import LiveFeed, VideoFeed
from camera_scanner import CameraScanner
from decoders_zxingcpp import DataMatrixDecoder as DataMatrixDecoder
from roi_auto_detector import ROIAutoDetector
from profile_setup import standard_profile, wallet_profile, giftbox_profile

# Initialize environment and logging before importing modules that use cv2/matplotlib
from logging_config import set_up_logger
import logging
logger = logging.getLogger()
set_up_logger()

def threaded_key_profile_switcher(scanner: CameraScanner):
    while True:
        # result = scanner.get_code()
        # if result:
        #     result = dict(sorted(result.items()))
        #     print(f"Detected codes {result = }")
            
        if keyboard.is_pressed("esc"):
            print("ESC has been pressed... Stopping...")
            scanner.running = False
            scanner.exit_loop()
            break
        elif keyboard.is_pressed("1"):
            scanner.running = True
            scanner.switch_profile(wallet_profile)
            time.sleep(0.25)  # debounce
        elif keyboard.is_pressed("2"):
            scanner.running = True
            scanner.switch_profile(giftbox_profile)
            time.sleep(0.25)
        elif keyboard.is_pressed("0"):
            scanner.running = True
            scanner.switch_profile(standard_profile)
            time.sleep(0.25)


        time.sleep(0.05)

def threaded_match_case_profile_switcher(scanner, state=0):
    while True: 
        if keyboard.is_pressed("esc"):
            print("ESC has been pressed... Stopping...")
            scanner.exit_loop()
            break

        match state:
            case 0:
                time.sleep(2) 
                state = 3
            case 1:
                if scanner.profile.name != giftbox_profile.name:
                    scanner.switch_profile(giftbox_profile)
                result = scanner.get_code()
                if result:
                    result = dict(sorted(result.items()))
                    print(f"Code detected {result}")
                    state = 4
            case 3:
                if scanner.profile.name != wallet_profile.name:
                    code_collection = []
                    scanner.switch_profile(wallet_profile)
                if len(code_collection) < 50:
                    # time.sleep(1)
                    result = scanner.get_code()
                    # print(f"Checking... {len(code_collection)} codes detected so far")
                    if result:
                        result = dict(sorted(result.items()))
                        print(f"Code detected {result}")
                        code_collection.append(result)
                    else:
                        continue
                else:
                    print("50 codes detected:") # {results = }")
                    for i, code in enumerate(code_collection):
                        print(f"{i+1:>02}: {code}")
                    state = 1
            case 4:
                scanner.exit_loop()
                print("Done :) Exiting...")
                break
        time.sleep(0.05)
                
def main(): 
    # Set up profile feeds
    #! Change use_live_flag to True to use live camera feed instead of recorded video. 
    #! Don't forget to set the correct camera index in the profile as well!
    #! Don't change anything else here.
    profiles = [ 
    #   Profile_instance | use_live_flag | first_active_flag | loop_flag | video_path               
        (standard_profile, False, True,  True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi"),
        (giftbox_profile,  False, False, True, "Jasmijn_code/videos/test_mjpg_1.avi"), 
        (wallet_profile,   False, False, True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi"), 
    ]

    try: 
        Feeds = []    
        for profile_instance, use_live_flag, first_active_flag, loop_flag, video_path in profiles:
            if use_live_flag:
                print(f"Using LIVE feed for profile '{profile_instance.name}' (Camera index {profile_instance.camera_index})")
                Feeds.append(LiveFeed(f"Camera {profile_instance.name}", first_active_flag, profile_instance.camera_index))
            else:
                print(f"Using RECORDED VIDEO for profile '{profile_instance.name}' (Camera index {profile_instance.camera_index}) from file: {video_path}")
                Feeds.append(VideoFeed(f"Recorded Video {profile_instance.name}", first_active_flag, video_path, profile_instance.camera_index, loop=loop_flag))
    except ValueError:
        logger.critical("Error setting up feeds. Try another path or camera index.")
        return
    
    feed_list = sorted(Feeds, key=lambda f: f.camera_index)
    print("Sorting feed_list in order of ascending camera index:")
    for feed in feed_list:
        print(f" - {feed.name} (Camera index {feed.camera_index})")
    
    # Set up decoder and ROI detector
    matrix_decoder = DataMatrixDecoder(use_threads=True, num_threads=16)
    roi_detector = ROIAutoDetector(
        expected_n_rois=50,
        threadhold_value=111,
        scaling_factor=2,
        threading=True,
    )

    # Set up CameraScanner
    scanner = CameraScanner(matrix_decoder, roi_detector, feed_list, debug = True)
    
    print("="*50)
    print("   CONTROLS: ")
    print("   0 = Standard profile")
    print("   1 = Wallet profile")
    print("   2 = Giftbox profile")
    print("   ESC = Quit")
    print("="*50)
    
    # Start scanning thread
    scan_thread = threading.Thread(
        target=threaded_key_profile_switcher, # Switch between threaded_match_case_profile_switcher (automatic) or threaded_key_profile_switcher (manual)
        args=(scanner,),
        name="CameraScannerThread",
        daemon=True
    )
    scan_thread.start()
    scanner.run()
    scan_thread.join()
            

   

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    main()

# 0 is Intern
# 1 is Razer Kiyo
# 2 is Daheng Imaging
# 3 is Intel Realsens