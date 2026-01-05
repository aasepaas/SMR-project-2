import cv2

# camera_indexen = [0, 1, 2, 3]
camera_indexen = [2]
value = "normal"  # "normal", "dshow", "msmf", "CAP_V4L2", "CAP_VFW"

for index in camera_indexen:
#     cap = cv2.VideoCapture(index)  # probeer 0 en 1
#     ret, frame = cap.read()
#     print(f"{index = }: ")
#     print(ret, frame.shape if ret else "No frame")

# 0 is Intern
# 1 is Razer Kiyo
# 2 is nvt
# 3 is Intel Realsense

# 0 = kiyo, blauw links onder
# 1 = intern
# 2 = 4k Webcam
# 3 = nvt

    match value:
        case "normal":
            print(f"{value} = normal?")
            cap = cv2.VideoCapture(index) # 0 = intern, 1 = 4K Webcam
        case "dshow":
            print(f"{value} = dshow?")
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) # 0 = 4K Webcam, 1 = intern
        case "msmf": 
            print(f"{value} = msmf?")
            cap = cv2.VideoCapture(index, cv2.CAP_MSMF) # 0 = intern, 1 = 4K Webcam
        # case "CAP_V4L2": 
        #     cap = cv2.VideoCapture(index, cv2.CAP_V4L2) # 0,1,2,3 = None
        # case "CAP_GIGANETIX ":
        #     cap = cv2.VideoCapture(index, cv2.CAP_GIGANETIX ) # 0,1,2,3 = None
        case _: 
            print(f"{value} = none?")
            cap = cv2.VideoCapture(index) # 0 = intern, 1 = 4K Webcam
    # cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        # cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
        # cap.set(cv2.CAP_PROP_BRIGHTNESS, 100)
        # cap.set(cv2.CAP_PROP_SETTINGS, 1)  # Open camera settings window
    except Exception as e:
        print(f"Could not change frame heigt/width: {e}")
    finally:
        pass
    DEBUG = True
    BARCODE = False
    CAPTURE_SETTING = True
    while True:
        ret, frame = cap.read()
        cap.set(cv2.CAP_PROP_SETTINGS, 1)  # Open camera settings window
        # if CAPTURE_SETTING:
            # cap.set(cv2.CAP_PROP_SETTINGS, 1)  # Open camera settings window
        
        if not ret:
            print("Geen frame!")
            break
        

        if DEBUG: 
            print(f"{index = }: {frame.shape}")
            DEBUG = False
        
        # Testing Barcode Scanning ROI
        if BARCODE: 
            left, top = 850, 200
            right, bottom = left + 75, top + 150
            
            frame = cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            roi = frame[top:bottom, left:right]
            roi = cv2.rotate(roi, cv2.ROTATE_90_CLOCKWISE)
            
            roi1 = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)
            cv2.imshow("ROI, linear", roi1)
            roi2 = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            cv2.imshow("ROI, cubic", roi2)
            roi3 = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_AREA)
            cv2.imshow("ROI, area", roi3)
            roi4 = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
            cv2.imshow("ROI, nearest", roi4)
        
        # frame = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_LINEAR)
        cv2.imshow("Test", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            if CAPTURE_SETTING: # showing values of the properties
                print("CV_CAP_PROP_FRAME_WIDTH: '{}'".format(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
                print("CV_CAP_PROP_FRAME_HEIGHT : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                print("CAP_PROP_FPS : '{}'".format(cap.get(cv2.CAP_PROP_FPS)))
                print("CAP_PROP_POS_MSEC : '{}'".format(cap.get(cv2.CAP_PROP_POS_MSEC)))
                print("CAP_PROP_FRAME_COUNT  : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
                print("CAP_PROP_BRIGHTNESS : '{}'".format(cap.get(cv2.CAP_PROP_BRIGHTNESS)))
                print("CAP_PROP_CONTRAST : '{}'".format(cap.get(cv2.CAP_PROP_CONTRAST)))
                print("CAP_PROP_SATURATION : '{}'".format(cap.get(cv2.CAP_PROP_SATURATION)))
                print("CAP_PROP_HUE : '{}'".format(cap.get(cv2.CAP_PROP_HUE)))
                print("CAP_PROP_GAIN  : '{}'".format(cap.get(cv2.CAP_PROP_GAIN)))
                print("CAP_PROP_CONVERT_RGB : '{}'".format(cap.get(cv2.CAP_PROP_CONVERT_RGB)))
            break
    cap.release()
    cv2.destroyAllWindows()
