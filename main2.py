from Datamatrixgit_aangepast import CameraScanner, ScanProfile
from roi_auto_detector import ROIAutoDetector
import keyboard
import time
import threading

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":

    # ---------------------------
    #  Get ROIs giftbox matrices
    # ---------------------------
    detector = ROIAutoDetector(camera_index=0, DEBUG=True)
    # detector = ROIAutoDetector(camera_index=0, DEBUG=False)
    Giftbox_results = detector.run()
    print(f"Detected ROIs: {Giftbox_results}")
    
    # ---------------------------
    #  Define Profiles
    # ---------------------------

    # Wallet profile
    top1, left1 = 525, 800
    top1, left1 = 100, 100
    bottom1, right1 = top1 + 100, left1 + 100
    wallet_profile = ScanProfile(
        name="Wallet",
        camera_index = 0,
        roi=(top1, bottom1, left1, right1),
        focus=175,
        exposure=-5,
        brightness=100,
        data_timeout=0.5
    )


    # Giftbox profile (single ROI)
    giftbox_profile = ScanProfile(
        name="GiftBox",
        camera_index=0,
        roi=Giftbox_results,  # Pass as list
        focus=120,
        exposure=-1,
        brightness=100,
        data_timeout=0.5
    )

    # Barcode profile
    top3, left3 = 300, 1250
    top3, left3 = 200, 200
    bottom3, right3 = top3 + 150, left3 + 300
    barcode_profile = ScanProfile(
        name="Barcode",
        camera_index = 0,
        roi=(top3, bottom3, left3, right3),
        focus=120,
        exposure=-5,
        brightness=120,
        data_timeout=1.0,
        type="barcode"
    )

    profiles = {
        "wallet": wallet_profile,
        "giftbox": giftbox_profile,
        "barcode": barcode_profile
    }



    # ---------------------------
    # Start scanner
    # ---------------------------
    
    scanner = CameraScanner(profiles)
    try: 
        # scanner.run(wallet_profile, giftbox_profile, barcode_profile)

        scan_thread = threading.Thread(
            target=scanner.run, 
            # args=(wallet_profile, giftbox_profile, barcode_profile),
            daemon=True
            )
        scan_thread.start()

        print("==============================================")
        print("   CONTROLS: ")
        print("   1 = Wallet profile")
        print("   2 = Giftbox profile")
        print("   3 = Barcode profile")
        print("   q or ESC = Quit")
        print("==============================================")

        # ---------------------------
        # Main Loop
        # ---------------------------

        while True:
            # Do not use __set_profile from outside the class, use switch_profile
            
            key = keyboard.read_key() 
            print(f"Key pressed = {key}")

            if key == "esc":
                print("ESC has been pressed... Stopping...")
                scanner.exit_loop()
                break
            elif key == "1":
                print("Trying to switch to barcode giftbox profile")
                scanner.switch_profile("barcode")
            elif key == "2":
                print("Trying to switch to datamatrix giftbox profile")
                scanner.switch_profile("giftbox")
            elif key == "3":
                print("Trying to switch to datamatrix wallet profile")
                scanner.switch_profile("wallet")
            elif key == "4":
                print("Trying to switch to super wallet profile")
                scanner.switch_profile("super wallet")  # Test non-existing profile
            time.sleep(0.2)
            
    finally:
        scanner.exit_loop()

# 0 is Intern
# 1 is Razer Kiyo
# 2 is Daheng Imaging
# 3 is Intel Realsense