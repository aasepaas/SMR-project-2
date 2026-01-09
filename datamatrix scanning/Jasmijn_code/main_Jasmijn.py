
import keyboard
import time
import threading


from feed import LiveFeed, VideoFeed
from camera_scanner import CameraScanner
from decoders import DataMatrixDecoder, BarcodeDecoder
from roi_auto_detector import ROIAutoDetector
from profile_setup import standard_profile, wallet_profile, giftbox_profile, barcode_profile

# Initialize environment and logging before importing modules that use cv2/matplotlib
from logging_config import init_environment, set_up_loger
init_environment()
set_up_loger()

def threaded_key_profile_switcher(scanner: CameraScanner):
    while True:
        result = scanner.get_code()
        if result:
            result = dict(sorted(result.items()))
            print(f"Detected codes {result = }")
            
        if keyboard.is_pressed("esc"):
            print("ESC has been pressed... Stopping...")
            scanner.running = False
            scanner.exit_loop()
            break
        elif keyboard.is_pressed("1"):
            scanner.running = False
            scanner.running = True
            scanner.switch_profile(wallet_profile)
            time.sleep(0.25)  # debounce
        elif keyboard.is_pressed("2"):
            scanner.running = False
            scanner.running = True
            scanner.switch_profile(giftbox_profile)
            time.sleep(0.25)
        elif keyboard.is_pressed("3"):
            scanner.running = False
            scanner.running = True
            scanner.switch_profile(barcode_profile)
            time.sleep(0.25)
        elif keyboard.is_pressed("0"):
            scanner.running = False
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
    # ---------------------------
    # Start scanner
    # ---------------------------
    # Verhoogd naar 8 threads voor 50 ROI's parallelle verwerking
    matrix_decoder = DataMatrixDecoder(num_threads=8, max_queue_size=100)
    barcode_decoder = BarcodeDecoder(num_threads=8, max_queue_size=100)    
    roi_detector = ROIAutoDetector(DEBUG=True, DEBUGPROCESS=True)

    # Realtime = False
    # if Realtime: #-=x Use two live cameras # Original, 4K Webcam
    #     feed_list = [
    #         LiveFeed("Camera Kiyo", True, 0), 
    #         LiveFeed("Camera laptop", False, 1),
    #         LiveFeed("Camera 4K Webcam", False, 2)
    #     ] 
    # else:#-=x Use two recorded video files instead of live cameras.
    #     feed_list = [
    #         VideoFeed("Recorded Video 1 (Camera Original)", True, "Jasmijn_code/videos/record_of_wallets_Kiyo_30secV6.avi", loop=True),
    #         VideoFeed("Recorded Video 2 (Camera 4K Webcam)", False, "Jasmijn_code/videos/recorded_output3.avi", loop=True),
    #         VideoFeed("Recorded Video 3 (Camera 4K Webcam)", False, "Jasmijn_code/videos/recorded_output4.avi", loop=True),
    #     ]2
    
    feed_list = [
            VideoFeed("Recorded Video 1 (Camera Original)", True, "Jasmijn_code/videos/record_of_wallets_Kiyo_30secV6.avi", loop=True),
            LiveFeed("Camera 4K Webcam", False, giftbox_profile.camera_index),
            # VideoFeed("Recorded Video 1 (Camera 4K Webcam)", False, "Jasmijn_code/videos/test_mjpg_1.avi", loop=True),
            VideoFeed("Recorded Video 2 (Camera 4K Webcam)", False, "Jasmijn_code/videos/recorded_output3.avi", loop=True),
    ]    
    scanner = CameraScanner(matrix_decoder, barcode_decoder, roi_detector, feed_list, debug = True)
    
    print("="*50)
    print("   CONTROLS: ")
    print("   1 = Wallet profile")
    print("   2 = Giftbox profile")
    print("   3 = Barcode profile")
    print("   ESC = Quit")
    print("="*50)
    
    scan_thread = threading.Thread(
    target=threaded_key_profile_switcher, # threaded_match_case_profile_switcher of threaded_key_profile_switcher
    args=(scanner,),
    name="CameraScannerThread",
    daemon=True
    )
    scan_thread.start()
    scanner.run()
    # while scanner.isactive:
    #     pass
    scan_thread.join()
            

   

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    main()

# 0 is Intern
# 1 is Razer Kiyo
# 2 is Daheng Imaging
# 3 is Intel Realsense