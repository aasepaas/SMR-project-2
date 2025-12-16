
import keyboard
import time
import threading
from multiprocessing import Process, Queue

from camera_scanner import CameraScanner
from datamatrix_decoder import DataMatrixDecoder
from roi_auto_detector import ROIAutoDetector
from profile_setup import wallet_profile, giftbox_profile, barcode_profile


def run_thread(scanner: CameraScanner):
    scan_thread = threading.Thread(
        target=scanner.run, 
        daemon=True
        )
    scan_thread.start()


    # ---------------------------
    # Main Loop
    # ---------------------------
    first = True
    while True:
        if scanner.detected_all and first:
            print(f"All codes detected {scanner.get_code() = }")
            first = False

        if keyboard.is_pressed("esc"):
            print("ESC has been pressed... Stopping...")
            scanner.exit_loop()
            break
        elif keyboard.is_pressed("1"):
            scanner.switch_profile(wallet_profile)
            time.sleep(0.25)  # debounce
        elif keyboard.is_pressed("2"):
            scanner.switch_profile(giftbox_profile)
            time.sleep(0.25)
        elif keyboard.is_pressed("3"):
            scanner.switch_profile(barcode_profile)
            time.sleep(0.25)

        time.sleep(0.05)

def run_thread_match_case(scanner, state=0):
    scan_thread = threading.Thread(
        target=scanner.run, 
        daemon=True
        )
    scan_thread.start()

    First = True
    while True: 
        if keyboard.is_pressed("esc"):
            print("ESC has been pressed... Stopping...")
            scanner.exit_loop()
            break

        match state:
            case 0:
                time.sleep(2) 
                state = 1
            case 1:
                if First:
                    scanner.switch_profile(giftbox_profile)
                    First = False
                if scanner.detected_all:
                    print(f"All {len(scanner.get_code())} codes detected {scanner.get_code() = }")
                    First = True
                    state = 2
            case 2:
                if First:
                    scanner.switch_profile(giftbox_profile)
                    First = False
                if scanner.detected_all:
                    print(f"All {len(scanner.get_code())} codes detected {scanner.get_code() = }")
                    First = True
                    state = 3
            case 3:
                # scanner.exit_loop()
                print("Done :) Exiting...")
                break
        time.sleep(0.05)
                
def main(): 
    # ---------------------------
    # Start scanner
    # ---------------------------
    input_queue = Queue(maxsize=1)
    result_queue = Queue(maxsize=1)
    processor= Process(target=DataMatrixDecoder.worker, args=(input_queue, result_queue))
    matrix_decoder = DataMatrixDecoder(processor=processor, input_queue=input_queue, result_queue=result_queue)
    roi_detector = ROIAutoDetector(DEBUG=True, DEBUGPROCESS=True)
    scanner = CameraScanner(matrix_decoder, roi_detector, debug = True)
    
    try: 

        print("==============================================")
        print("   CONTROLS: ")
        print("   1 = Wallet profile")
        print("   2 = Giftbox profile")
        print("   3 = Barcode profile")
        print("   ESC = Quit")
        print("==============================================")
        
        # run_thread(scanner)
        run_thread_match_case(scanner)
            
    finally:
        scanner.exit_loop()
   

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    main()

# 0 is Intern
# 1 is Razer Kiyo
# 2 is Daheng Imaging
# 3 is Intel Realsense