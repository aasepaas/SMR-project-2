import cv2
# =============================================================================
# Configuable parameters
# =============================================================================
# Configure which camera indexes to test
# camera_indexen = [0, 1, 2, 3]
camera_indexen = [0]
# Keep at "" to use default backend (also used in camerascanner.py)
value = "" # dshow to test camera properties (pop up Window) or "msmf" for Media Foundation, or "" for default
settings = {'focus': 186, 'brightness': None, 'exposure': None} # Set to None for auto

test_capture_properties_bool = True
test_region_of_interest_bool = True
test_resizing_pixel_quality_bool = True # Test with test_region_of_interest_bool = True

# =============================================================================
# Main code
# =============================================================================
def set_start_camera_properties(cap, settings):
    if settings.get('focus') is not None:
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap.set(cv2.CAP_PROP_FOCUS, settings['focus'])
    else:
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

    if settings.get('exposure') is not None:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cap.set(cv2.CAP_PROP_EXPOSURE, settings['exposure'])
    else:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
    
    if settings.get('brightness') is not None:
        cap.set(cv2.CAP_PROP_BRIGHTNESS, settings['brightness'])
    else:
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 100) # 'Default' brightness
        
property_steps = {
    'focus':    {ord('f'): 1,  ord('F'): 5,  ord('g'): -1, ord('G'): -5},
    'brightness': {ord('b'): 1, ord('B'): 5, ord('n'): -1, ord('N'): -5},
    'exposure': {ord('e'): 1, ord('E'): 5, ord('r'): -1, ord('R'): -5}
}

properties_cv = {
    'focus': cv2.CAP_PROP_FOCUS,
    'brightness': cv2.CAP_PROP_BRIGHTNESS,
    'exposure': cv2.CAP_PROP_EXPOSURE
}

def handle_key_adjust(key, name, value):
    step = property_steps[name][key]
    value += step
    cap.set(properties_cv[name], value)
    direction = "increased" if step > 0 else "decreased"
    print(f"{name.capitalize()} {direction} to {value} (camera reports {cap.get(properties_cv[name])})")
    return value

for index in camera_indexen:
    backends = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}
    if value in backends:
        cap = cv2.VideoCapture(index, backends[value])
    else:
        cap = cv2.VideoCapture(index)

    if test_capture_properties_bool:
        cap.set(cv2.CAP_PROP_SETTINGS, 1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)

    set_start_camera_properties(cap, settings)
    printed_info = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Geen frame!")
            break

        if not printed_info:
            print(f"{index = }: {frame.shape}")
            printed_info = True

        if test_region_of_interest_bool: 
            width, height = 80, 80
            middentp, middenlr = 685+20, 950-240
            top, left = middentp-height, middenlr-height
            bottom, right = middentp+width, middenlr+width
            frame = cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            roi = frame[top:bottom, left:right]
            # roi = cv2.rotate(roi, cv2.ROTATE_90_CLOCKWISE)

            if test_resizing_pixel_quality_bool:
                for interp, name in [(cv2.INTER_LINEAR,"linear"), (cv2.INTER_CUBIC,"cubic"),
                                     (cv2.INTER_AREA,"area"), (cv2.INTER_NEAREST,"nearest")]:
                    cv2.imshow(f"ROI {name}", cv2.resize(roi, None, fx=4, fy=4, interpolation=interp))

        cv2.putText(frame, "Press ESC to exit", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Focus: {settings['focus']}, Brightness: {settings['brightness']}, Exposure: {settings['exposure']}",
            org=(10, 70), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.7, color=(0, 255, 0), thickness=2)
        
        cv2.imshow("Test", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 27: # ESC key to exit
            break

        for name in property_steps: # Adjust camera properties based on key presses
            if key in property_steps[name]:
                settings[name] = handle_key_adjust(key, name, settings[name])

    if test_capture_properties_bool:
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

    cap.release()
    cv2.destroyAllWindows()
