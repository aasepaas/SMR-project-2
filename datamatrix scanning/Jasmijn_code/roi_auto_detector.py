import cv2
import numpy as np
import time

from typing import List, Tuple
from DBSCANFiltering import DBSCANFiltering

class ErrorNoROICenters(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class ROIAutoDetector:
    """
    Automatically detect datamatrices in camera feed and extract ROI coordinates.
    
    Usage:
    - Press 'c' to capture frame and detect all datamatrices
    - Press 'q' to quit
    """
    
    def __init__(self, DEBUG: bool = False, DEBUGPROCESS: bool = False, recalc = "c"):
        self.debug = DEBUG
        self.debug_process = DEBUGPROCESS
        self.recalc = recalc
                
    
    @staticmethod
    def __connected_components_filtering(frame, Min_area=100, Max_area=500_000, squareness=10, connect=8):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(frame, connectivity=connect)

        full_mask = np.zeros(labels.shape, dtype="uint8")
        points = []
        # print("Connected Components found:", num_labels - 1)
        for label in range (1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]
            # print("label area:", area)
            if area >= Max_area or area <= Min_area: # Verwijder kleine ruis
                continue
        
            x, y, w, h = stats[label, cv2.CC_STAT_LEFT], stats[label, cv2.CC_STAT_TOP], stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]
            points.append((x, y, w, h))
            
            if abs(w - h) > squareness: # Niet vierkant genoeg
                continue
            
            full_mask[labels == label] = 255
            
            # if squareness == 1: 
            #     print(f"Contour found - Area: {area}, x:{x}, y:{y}, w:{w}, h:{h}")
            
        # cv2.imshow("Connected Components", full_mask)
        return full_mask, points  

    def __preprocess_frame(self, frame):
        """Preprocess frame for better contour detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # contrast verbeteren (verscherpen)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl1  = clahe.apply(gray)
        if self.debug_process: 
            cv2.imshow("createCLAHE", cl1 ) 
        
        # contrast verbeteren (blurren)
        blur = cv2.GaussianBlur(cl1 , (5, 5), 0)
        if self.debug_process:
            cv2.imshow("GaussianBlur", blur) 
        
        # thresholding
        _, th2 = cv2.threshold(blur, 185, 255, cv2.THRESH_BINARY)        
        if self.debug_process: 
            cv2.imshow("Threshold blur", th2)

        # Groffe filtering met connected components
        Groffe_filter, _ = self.__connected_components_filtering(th2, Min_area=100, Max_area=500_000, squareness=15, connect=4)                    
        if self.debug_process: 
            cv2.imshow("Groffe_filter", Groffe_filter)

        # Make bounding rectangles around detected components
        contours, _ = cv2.findContours(Groffe_filter, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)   
            side = ch if cw - ch < 0 else cw
            cv2.rectangle(Groffe_filter, (x, y), (x + side, y + side), (255), -1)     
        if self.debug_process: 
            cv2.imshow("Bounding Rectangles", Groffe_filter) 
        
        # Fijne filtering met connected components
        Fijne_filter, boxes = self.__connected_components_filtering(Groffe_filter, Min_area=1000, Max_area=500_000, squareness=1, connect=8)                    
        if self.debug_process: 
            cv2.imshow("Fijne_filter", Fijne_filter)


        # =========================================================
        # Make list of all coordinates: 
        # =========================================================       
        centers_list = []
        for box in boxes:
            x, y, w, h = box
            cX, cY = x + w // 2, y + h // 2
            centers_list.append((cX, cY)) 
        
        return Fijne_filter, boxes, centers_list
        
    def __preprocess_frame2(self, frame):
        """Preprocess frame for better contour detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # contrast verbeteren
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl1  = clahe.apply(gray)
        if self.debug_process: 
            cv2.imshow("createCLAHE", cl1 ) 
        
        # Contrast verbeteren
        blur = cv2.GaussianBlur(cl1 , (5, 5), 0)
        if self.debug_process: 
            cv2.imshow("GaussianBlur", blur) 

        # Adaptieve threshold (werkt bij wisselend licht)
        th1 = cv2.adaptiveThreshold(blur, 255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 7)
        if self.debug_process: 
            cv2.imshow("adaptiveThreshold", th1) 
                
        # Morfologie om blokken te sluiten
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        th2 = cv2.morphologyEx(th1, cv2.MORPH_CLOSE, kernel, iterations=2)
        if self.debug_process: 
            cv2.imshow("morphologyEx", th2) 

        # =========================================================
        # Make list of all coordinates: 
        # =========================================================
        points, centers_list = [], []
        contours, _ = cv2.findContours(th2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 1500 or area > 7000:
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            points.append((x, y, w, h))
            
            cX, cY = x + w // 2, y + h // 2
            centers_list.append((cX, cY)) 
    
        return th2, points, centers_list     
              
    def __detect_rois_opencv(self, frame):
        """Detect ROIs using OpenCV contour detection.""" 
        th, points, centers_list = self.__preprocess_frame(frame)
        rois = []
        if not centers_list:
            # Geen centers gevonden — geef een lege lijst terug in plaats van een exception
            # Zo voorkomt de hele applicatie te crashen bij wisselende lichtomstandigheden.
            if self.debug_process:
                print("No ROIS detected to get centers from. Returning empty list.")
            return []
        
        
        DBSfilter = DBSCANFiltering(data=centers_list, eps=50, min_samples=5)
        valid_indices, labels  = DBSfilter.get_filtered_indices()
        fig = DBSfilter.visualize_dbscan_results(labels)
        DBSCANFiltering.fig_to_cv2(fig)
                    
        for idx in valid_indices:
            
            # =========================================================
            #  Get all needed coordinates: 
            # =========================================================
            x, y, cw, ch = points[idx]
            cX, cY = centers_list[idx]
            
            # Padding als percentage van contour dimensies
            pad_w = int(cw * 0.10)
            pad_h = int(ch * 0.10)
            
            top = y - pad_h
            bottom = y + ch + pad_h
            left = x - pad_w
            right = x + cw + pad_w
            
            # =========================================================
            #  Draw all the information
            # =========================================================
            label = str((cX, cY))
            textbox = (cX, cY - 45) # 25

            cv2.rectangle(th, (x, y), (x + cw, y + ch), (128), 2)
            cv2.circle(th, (cX, cY), 10, (128), 2)
            cv2.putText(th, label, textbox, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)
            if self.debug_process: 
                cv2.imshow("Centers", th)       
                
            rois.append((top, bottom, left, right))
            
        print(f"OpenCV found {len(rois)} ROIs")
        
        return rois    
    
    @staticmethod
    def __sort_rois_column_major(rois):
        rois_with_center = []
        for roi in rois:
            top, bottom, left, right = roi
            cx = (left + right) / 2
            cy = (top + bottom) / 2
            rois_with_center.append((roi, cx, cy))

        rois_with_center.sort(key=lambda x: x[1])

        columns = []
        for r in rois_with_center:
            placed = False
            for col in columns:
                if abs(r[1] - col[0][1]) < 60:
                    col.append(r)
                    placed = True
                    break
            if not placed:
                columns.append([r])

        sorted_rois = []
        for col in columns:
            col.sort(key=lambda x: x[2])
            sorted_rois.extend([x[0] for x in col])

        return sorted_rois

    @staticmethod
    def __draw_rois_on_frame(frame, rois):
        """Draw detected ROIs on frame with labels."""
        
        for i, (top, bottom, left, right) in enumerate(rois):
            # Draw green rectangle
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            # Draw label
            cv2.putText(frame, f"ROI {i+1}", (left, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame
      
    def __recalculate_rois(self, frame):
        """Herbereken ROI's op basis van het huidige frame."""
        print("\n>>> Herberekenen van ROI's...")
        rois = self.__detect_rois_opencv(frame)
        rois = self.__sort_rois_column_major(rois)
        detected_frame = self.__draw_rois_on_frame(frame, rois)
        print(f">>> {len(rois)} ROI's gedetecteerd\n")
        
        return detected_frame, rois

  
    def run(self, frame) -> List[Tuple[int, int, int, int]]:
        """Detecteer ROI's. Roep zelf destroywindows aan"""
        
        frame_copy = frame.copy()       
        # Als nog geen ROI's gedetecteerd zijn, doe dit nu
        display_frame, rois = self.__recalculate_rois(frame_copy)

        # Maak display frame
        if self.debug: 
            # display_frame = self.detected_frame.copy() if self.detected_frame is not None else frame
            display_frame = cv2.resize(display_frame, (None), fx=0.7, fy=0.7)
            cv2.putText(display_frame, f"ROIs found: {len(rois)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if self.recalc:
                cv2.putText(display_frame, f"Press '{self.recalc}' to recalculate", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.imshow("ROI Auto Detector", display_frame)
        else: 
            # self.__save_to_file()
            print("\nROI List for code:")
            for i, (top, bottom, left, right) in enumerate(rois):
                print(f"roi_{i+1} = ({top}, {bottom}, {left}, {right})")
     
        return rois

    def capture_loop(self, frame, button: str = "c", skip_frames: int = 5) -> List[Tuple[int, int, int, int]]:
        """
        Process a single `frame` interactively and return detected ROIs when the
        user confirms (presses `q`).

        - `frame`: BGR image to process.
        - `button`: key to trigger recalculation (default 'c').

        Returns a list of detected ROIs as tuples `(top, bottom, left, right)`
        when the user presses `q`. Returns an empty list otherwise.
        """

        try:
            Results = self.run(frame)
        except ErrorNoROICenters as e:
            print(e)
            return []

        # Wait for user to press 'q' (accept) or the recalc `button`.
        # Use a short waitKey timeout and loop so we remain responsive
        # and do not return on spurious keycodes.
        while True:
            key = cv2.waitKey(10) & 0xFF
            if key == ord('q'):
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
                return Results
            elif key == ord(button):
                return []
            # No relevant key pressed: continue waiting
            time.sleep(0.01)

    
        
        
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    button = "c"
    detector1 = ROIAutoDetector(DEBUG=True, DEBUGPROCESS=True, recalc=button)
    results = []
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if results == []: 
                print("In capture loop, waiting for user input...")
                results = detector1.capture_loop(frame, button=button, skip_frames=0)
            elif results != []:
                print(f"{len(results)} ROI's detected, exiting capture loop.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    for i, (x, y, w, h) in enumerate(results, start=1):
        print(f"{i:>02}: x = {x:>4}, y = {y:>4}, w = {w:>4}, h = {h:>4}")
