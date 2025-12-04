from Datamatrixgit_aangepast import CameraScanner, ScanProfile
import keyboard
import time
import threading

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    
    # ---------------------------
    #  Define Profiles
    # ---------------------------

    # Wallet profile
    top1, left1 = 525, 800
    top1, left1 = 100, 100
    bottom1, right1 = top1 + 100, left1 + 100
    wallet_profile = ScanProfile(
        name="Wallet",
        camera_index = 1,
        roi=(top1, bottom1, left1, right1),
        focus=175,
        exposure=-5,
        brightness=100,
        data_timeout=0.5
    )

    # Giftbox profile
    top2, left2 = 300, 800
    top2, left2 = 150, 150
    bottom2, right2 = top2 + 150, left2 + 150
    giftbox_profile = ScanProfile(
        name="GiftBox",
        camera_index = 1,
        roi=(top2, bottom2, left2, right2),
        focus=120,
        exposure=-4,
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
    
    scanner = CameraScanner(barcode_profile, profiles)
    # scanner.run(wallet_profile, giftbox_profile, barcode_profile)
    
    scan_thread = threading.Thread(
        target=scanner.run, 
        args=(wallet_profile, giftbox_profile, barcode_profile),
        daemon=True
        )
    scan_thread.start()


    # print("[MAIN] Keyboard ready: w=wallet, g=giftbox, b=barcode, q=quit")

    # while True:
    #     # print("HELLO")
    #     key = cv2.waitKey(1) & 0xFF

    #     if key == ord('q') or key == 27:
    #         print("Exiting...")
    #         scanner.exit_loop()
    #         break
    #     # print("BYEE")
    #     if key == ord('1'):
    #         scanner.switch_profile("wallet")

    #     if key == ord('2'):
    #         scanner.switch_profile("giftbox")

    #     if key == ord('3'):
    #         scanner.switch_profile("barcode")

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
        key = keyboard.read_key()  # lees de toets één keer
        print(f"Key pressed = {key}")

        if key == "esc":
            print("ESC has been pressed... Stopping...")
            scanner.exit_loop()
            break
        elif key == "1":
            print("Switch to barcode giftbox profile")
            scanner.set_profile(barcode_profile)
        elif key == "2":
            print("Switch to datamatrix giftbox profile")
            scanner.set_profile(giftbox_profile)
        elif key == "3":
            print("Switch to datamatrix wallet profile")
            scanner.set_profile(wallet_profile)
        time.sleep(0.2)
