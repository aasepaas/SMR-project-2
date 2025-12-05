#%% Harvesters
# # from harvesters.core import Harvester
# import cv2

# # CTI_FILE_PATH = r"C:\Program Files\Daheng Imaging\GalaxySDK\GenTL\Win64\GxGVTL.cti"  # The filepath to the CTI file
# CTI_FILE_PATH = r"C:\Program Files\Daheng Imaging\GalaxySDK\GenTL\Win64\GxUSBTL.cti"

# with Harvester() as h:
#     h.add_file(CTI_FILE_PATH)
#     h.update()
#     with h.create() as ia:
#         ia.start()
#         with ia.fetch() as buffer:
#             component = buffer.payload.components[0]
#             width = component.width
#             height = component.height
#             bayer = component.data.reshape((height, width))
#             img = cv2.cvtColor(bayer, cv2.COLOR_BayerRG2BGR)
#             img = img[..., ::-1]
#             cv2.imshow("image", img)
#             cv2.waitKey(0)
#             cv2.destroyAllWindows()



# from harvesters.core import Harvester

# h = Harvester()
# h.add_file(r"C:\Program Files\Daheng Imaging\GalaxySDK\GenTL\Win64\GxUSBTL.cti")
# h.update()

# print(h.device_info_list)
# print("einde :/")

#%% Dafeng camera
# import gxipy as gx
# import cv2, os

# class Daheng_Camera():
#     # Custom exception
#     class DahengException(Exception):
#         pass
#     device_manager = None
#     cam = None
#     GAIN_MAX = None
#     EXPOSURE_MAX = None
  
#     def __init__(self):
#         # Initialize the camera system
#         self.device_manager = gx.DeviceManager()
#         self.device_manager.update_device_list()
        
#         dev_num = self.__getNumberOfCameras()
#         if dev_num == 0:
#             raise self.DahengException("No Daheng cameras detected")
        
#         self.cam = self.device_manager.open_device_by_index(1)
        
#         self.cam.ExposureAuto.set(False) # Sets auto exposure off (if you want to handle it manually)
#         self.cam.GainAuto.set(False) # Sets auto gain on/off (if you want to handle it manually)
        
#         self.__setSensorArea() # Set full sensor area (MUST HAVE FOR FULL RESOLUTION)
        

#     def __getNumberOfCameras(self):      
#         return self.device_manager.get_device_number()

#     def __setSensorArea(self):
#         # Set full sensor area
#         self.cam.Width.set(self.cam.WidthMax.get())
#         self.cam.Height.set(self.cam.HeightMax.get())
#         self.cam.OffsetX.set(0)
#         self.cam.OffsetY.set(0)
        
#         # Disable trigger mode for continuous capture
#         self.cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
        
#     def loadConfigFile(self, filePath):
#         # Load configuration file
#         if os.path.exists(filePath):
#             self.cam.import_config_file(filePath)
#             print("Camera settings loaded from:", filePath)
#         else:
#             print("Config file not found:", filePath)    

#     def getFrame(self):
#         raw_image = self.cam.data_stream[0].get_image()
#         if raw_image is None:
#             return None
        
#         raw_image = raw_image.get_numpy_array()
#         # Convert Bayer to RGB 
#         image = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_GR2RGB)

#         return image

#     def startStream(self):
#         self.cam.stream_on() # Set camera ON
#         self.flushBuffer
        
#     def stopStream(self):
#         self.flushBuffer
#         self.cam.stream_off() # Set camera ON
        
#     def flushBuffer(self):
#         # Flush buffer
#         for _ in range(5):  # Adjust count if needed
#             try:
#                 self.cam.StreamGetImage(timeout=50)
#             except:
#                 break  # No more frames to discard    
        
#     def changeExposure(self, exposure):
#         self.cam.ExposureTime.set(exposure+24) # Exposure cant be lower than 24, so this makes sure it cant go wrong  
        
#     def changeGain(self, gain):
#         self.cam.Gain.set(gain)
        
#     def closeConnection(self):
#         self.cam.stream_off()
#         self.cam.close_device()
        
# def main():
#     cam = Daheng_Camera()
#     cam.startStream()
#     cam.changeExposure(50000)  # Min:24.0000 Max:1,000,000.0000
#     cam.changeGain(20) # Min:0.0000 Max:25.9000

#     while(True): 
#         frame = cam.getFrame()
#         resized_image = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)

#         cv2.imshow("Daheng Camera View", resized_image)    
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     cam.stopStream()        
    
# if __name__ == "__main__":
#     main()
    
#%% Code datamatrix scannen   
import gxipy as gx
import cv2
import time
from multiprocessing import Process, Queue
from pylibdmtx.pylibdmtx import decode as dm_decoder

# ======================
# Daheng Camera Class
# ======================
class Daheng_Camera:
    class DahengException(Exception):
        pass

    def __init__(self):
        self.device_manager = gx.DeviceManager()
        self.device_manager.update_device_list()
        if self.device_manager.get_device_number() == 0:
            raise self.DahengException("No Daheng cameras detected")

        # Gebruik jouw werkende index 1
        self.cam = self.device_manager.open_device_by_index(1)
        if self.cam is None:
            raise self.DahengException("Camera kon niet worden geopend")

        self.cam.ExposureAuto.set(False)
        self.cam.GainAuto.set(False)
        self.__setSensorArea()

    def __setSensorArea(self):
        self.cam.Width.set(self.cam.WidthMax.get())
        self.cam.Height.set(self.cam.HeightMax.get())
        self.cam.OffsetX.set(0)
        self.cam.OffsetY.set(0)
        self.cam.TriggerMode.set(gx.GxSwitchEntry.OFF)

    def startStream(self):
        self.cam.stream_on()
        self.flushBuffer()

    def stopStream(self):
        self.flushBuffer()
        self.cam.stream_off()

    def flushBuffer(self):
        for _ in range(5):
            try:
                self.cam.stream[0].get_image(timeout=50)
            except:
                break

    def getFrame(self):
        raw_image = self.cam.data_stream[0].get_image()
        if raw_image is None:
            return None
        raw_image = raw_image.get_numpy_array()
        image = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_GR2RGB)
        return image

    def changeExposure(self, exposure):
        self.cam.ExposureTime.set(max(exposure, 24))

    def changeGain(self, gain):
        self.cam.Gain.set(gain)

    def closeConnection(self):
        self.cam.stream_off()
        self.cam.close_device()

# ======================
# DataMatrix Decoder
# ======================
class DataMatrixDecoder:
    def __init__(self):
        self.input_queue = Queue(maxsize=1)
        self.result_queue = Queue(maxsize=1)
        self.proc = Process(target=self.worker)
        self.proc.start()

    def worker(self):
        while True:
            try:
                frame = self.input_queue.get(timeout=0.1)
            except:
                continue
            if frame is None:
                break
            try:
                results = dm_decoder(frame)
                if not self.result_queue.full():
                    self.result_queue.put(results[0] if results else None)
            except:
                if not self.result_queue.full():
                    self.result_queue.put(None)

    def decode_async(self, frame):
        if self.input_queue.empty():
            try:
                self.input_queue.put(frame, timeout=0.01)
            except:
                pass

    def get_result(self):
        try:
            return self.result_queue.get_nowait()
        except:
            return None

    def stop(self):
        try:
            self.input_queue.put_nowait(None)
        except:
            pass
        if self.proc is not None:
            self.proc.join(timeout=1.0)
            if self.proc.is_alive():
                self.proc.terminate()
        self.proc = None

# ======================
# Scanner met vaste instellingen
# ======================
def main():
    cam = Daheng_Camera()
    cam.startStream()
    cam.changeExposure(50000)  # Jouw gewenste instellingen
    cam.changeGain(20)

    decoder = DataMatrixDecoder()
    
    # Definieer 6 ROI's: (top, left, height, width)
    rois = [
        (80, 50, 150, 150),   # ROI 1
        (80, 500, 150, 150),  # ROI 2
        (230, 50, 150, 150),  # ROI 3
        (230, 500, 150, 150),   # ROI 4
        # (450, 250, 150, 150),  # ROI 5
        # (450, 420, 150, 150)   # ROI 6
    ]

    try:
        current_roi = 0  # Start bij ROI 0
        while True:
            
            frame = cam.getFrame()
            if frame is None:
                continue

            # Resize voor preview (optioneel, voor schermweergave)
            height, width = frame.shape[:2]

            # Nieuwe breedte = 640, hoogte wordt berekend
            new_width = 640
            new_height = int(height * (new_width / width))

            # frame = originele camera frame
            preview = cv2.resize(frame, (640, int(frame.shape[0]*640/frame.shape[1])))

            top, left, h, w = rois[current_roi]
            bottom, right = top + h, left + w

            # ROI voor verwerking: originele frame
            roi_frame = frame[top:bottom, left:right]
            gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_RGB2GRAY)

            # Decodeer
            result = dm_decoder(gray_roi)
            if result:
                code = result[0].data.decode("utf-8")
                print(f"Decoded DataMatrix in ROI {current_roi+1}: {code}")

                # Ga door naar de volgende ROI
                current_roi += 1
                if current_roi >= len(rois):
                    print("Alle ROI's gescand. Herstarten bij ROI 1.")
                    current_roi = 0

            # Visualisatie: ROI schalen naar preview
            scale_x = preview.shape[1] / frame.shape[1]
            scale_y = preview.shape[0] / frame.shape[0]
            cv2.rectangle(preview,
                        (int(left*scale_x), int(top*scale_y)),
                        (int(right*scale_x), int(bottom*scale_y)),
                        (0, 255, 0), 2)

            # Vervangen code 
            # preview = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            # preview = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)
            
            # ROI: volledige frame voor decoding
            
            # top, left = 400, 150 # 75mm
            # bottom, right = top + 150, left + 150 # 75mm
            # top, left = 280-75-50//2, 80-75//2 # 50mm
            # bottom, right = top + 150, left + 150 # 50mm roi = 75px
            # top, left = 232, 235 # 8mm
            # bottom, right = top + 25, left + 25 # 8mm
            
                 
            # ROI uit originele frame voor verwerking
            top, left, h, w = rois[current_roi]
            bottom, right = top + h, left + w
            # Voor visualisatie: teken ROI op het previewbeeld
            cv2.rectangle(preview, (left, top), (right, bottom), (0, 0, 255), 2)
            roi_frame = preview[top:bottom, left:right]  # Voor verwerking
            
            
            # Nieuwe breedte = 640, hoogte wordt berekend
            height, width = roi_frame.shape[:2]
            new_width = 120
            new_height = int(height * (new_width / width))

            # roi_frame = cv2.resize(roi_frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            # roi_frame = cv2.resize(roi_frame, (120, 120), interpolation=cv2.INTER_LINEAR)
            gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_RGB2GRAY)

            import numpy as np
            # Definieer sharpening kernel
            kernel = np.array([[0, -1, 0],
                               [-1, 6,-1],
                               [0, -1, 0]])

            # Pas filter toe
            sharpened_roi = cv2.filter2D(roi_frame, -1, kernel)
            sharpened_gray = cv2.filter2D(gray_roi, -1, kernel)

            # Decodeer
            decoder.decode_async(sharpened_gray)
            result = decoder.get_result()
            if result:
                try:
                    code = result.data.decode("utf-8")
                    print(f"Decoded DataMatrix in ROI {current_roi+1}: {code}")
                    
                    # Maak de queue leeg zodat oude frames niet opnieuw gelezen worden
                    while decoder.get_result() is not None:
                        pass

                    # Ga door naar de volgende ROI
                    current_roi += 1
                    if current_roi >= len(rois):
                        print("Alle ROI's gescand. Herstarten bij ROI 1.")
                        current_roi = 0
                except:
                    pass
            # decoder.decode_async(sharpened_gray)
            # result = decoder.get_result()
            # if result:
            #     try:
            #         code = result.data.decode("utf-8")
            #         print("Decoded DataMatrix:", code)
            #     except:
            #         pass


            cv2.imshow("Daheng Camera View", preview)
            cv2.imshow("greyroi", gray_roi)
            cv2.imshow("roi", roi_frame)
            cv2.imshow("sharpend greyroi", sharpened_gray)
            cv2.imshow("sharpend roi", sharpened_roi)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        decoder.stop()
        cam.stopStream()
        cam.closeConnection()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
