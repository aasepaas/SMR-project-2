import cv2
from cv2.typing import MatLike
import json
from typing import List, Tuple

class ROIAutoDetector:
    """
    Automatically detect datamatrices in camera feed and extract ROI coordinates.
    
    Usage:
    - Press 'c' to capture frame and detect all datamatrices
    - Press 'q' to quit
    """
    
    def __init__(self, camera_index: int = 0, DEBUG: bool = False):
        self.camera_index = camera_index
        self.debug = DEBUG
        self.cap = cv2.VideoCapture(camera_index)
        
        if not self.cap.isOpened():
            print(f"Cannot open camera {camera_index}")
            return
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self.rois: List[Tuple[int, int, int, int]] = []  # List of (top, bottom, left, right)
        self.frame = None
        self.detected_frame = None
    
    
    def __preprocess_frame(self, frame) -> MatLike:
        """Preprocess frame for better contour detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # contrast verbeteren
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl1  = clahe.apply(gray)
        if self.debug: cv2.imshow("createCLAHE", cl1 )
        
        # Contrast verbeteren
        blur = cv2.GaussianBlur(cl1 , (5, 5), 0)
        if self.debug: cv2.imshow("GaussianBlur", blur)

        # Adaptieve threshold (werkt bij wisselend licht)
        th1 = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31, 7
        )
        if self.debug: cv2.imshow("adaptiveThreshold", th1)
                
        # Morfologie om blokken te sluiten
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        th2 = cv2.morphologyEx(th1, cv2.MORPH_CLOSE, kernel, iterations=2)
        if self.debug: cv2.imshow("morphologyEx", th2)

        
        return th2
                
    def __detect_rois_opencv(self, frame):
        """Detect ROIs using OpenCV contour detection."""
        th = self.__preprocess_frame(frame)
        
        contours, _ = cv2.findContours(
            th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        rois = []
        h, w = frame.shape[:2]

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # if area < 1500 or area > 7000:
            if 1500 > area > 7000:
                continue
            # print(f"Contour area: {area}")
            x, y, cw, ch = cv2.boundingRect(cnt)

            aspect = cw / ch
            if not 0.7 < aspect < 1.3:   # vrijwel vierkant
                continue

            # extra filtering op grootte
            if cw < 30 or ch < 30:
                continue
            
            # Padding als percentage van contour dimensies
            pad_w = int(cw * 0.10)
            pad_h = int(ch * 0.10)
            
            top = y - pad_h
            bottom = y + ch + pad_h
            left = x - pad_w
            right = x + cw + pad_w

            rois.append((top, bottom, left, right))

        print(f"OpenCV found {len(rois)} ROIs")
        return rois    
    
    def __draw_rois_on_frame(self, frame, rois):
        """Draw detected ROIs on frame with labels."""
        display_frame = frame.copy()
        
        for i, (top, bottom, left, right) in enumerate(rois):
            # Draw green rectangle
            cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
            # Draw label
            cv2.putText(display_frame, f"ROI {i+1}", (left, top - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return display_frame

    def __sort_rois_column_major(self, rois):
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
        
    def __save_to_file(self, filename: str = "roi_coordinates.json"):
        """Save ROI coordinates to JSON file."""
        if not self.rois:
            print("No ROIs to save.")
            return
        
        data = {
            "camera_index": self.camera_index,
            "total_rois": len(self.rois),
            "rois": [
                {
                    "index": i + 1,
                    "coordinates": {
                        "top": top,
                        "bottom": bottom,
                        "left": left,
                        "right": right
                    }
                }
                for i, (top, bottom, left, right) in enumerate(self.rois)
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n╔══════════════════════════════════════════════╗")
        print(f"║ ✓ {len(self.rois)} ROI(s) saved to '{filename}'  ║")
        print(f"╚══════════════════════════════════════════════╝")
    
    def __recalculate_rois(self):
        """Herbereken ROI's op basis van het huidige frame."""
        if self.frame is not None:
            print("\n>>> Herberekenen van ROI's...")
            self.rois = self.__detect_rois_opencv(self.frame)
            self.rois = self.__sort_rois_column_major(self.rois)
            self.detected_frame = self.__draw_rois_on_frame(self.frame, self.rois)
            print(f">>> {len(self.rois)} ROI's gedetecteerd\n")
    
    def __set_standard_camera_settings(self):
        """Stel standaard camera instellingen in."""
        # Zet autofocus aan
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        
        # Zet auto-exposure aan (waarde 0.75 = auto mode) (soms werkt 3 ook)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
        
        # Reset brightness naar standaard (vaak 128)
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 100)        

        
    def run(self) -> List[Tuple[int, int, int, int]]:
        """Detecteer ROI's en laat beeld open tot 'q' of ESC."""

        while True:
            ret, self.frame = self.cap.read()
            if not ret:
                print("Error reading frame")
                break
            self.__set_standard_camera_settings()
               
            # Als nog geen ROI's gedetecteerd zijn, doe dit nu
            if not self.rois:
                self.__recalculate_rois()

            # Maak display frame
            if self.debug: 
                display_frame = self.detected_frame.copy() if self.detected_frame is not None else self.frame.copy()
                cv2.putText(display_frame, f"ROIs found: {len(self.rois)}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(display_frame, "Press 'c' to recalculate", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                cv2.imshow("ROI Auto Detector", display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # ESC
                    break
                elif key == ord('c'):  # Herbereken ROI's
                    self.__recalculate_rois()
            else: 
                # self.__save_to_file()
                print("\nROI List for code:")
                for i, (top, bottom, left, right) in enumerate(self.rois):
                    print(f"roi_{i+1} = ({top}, {bottom}, {left}, {right})")
                break

                
        self.__cleanup()
        return self.rois
    
    def __cleanup(self) -> None:
        """Clean up resources."""
        self.cap.release()
        cv2.destroyAllWindows()
        print("\nDetector closed.")
        
        
if __name__ == "__main__":
    detector = ROIAutoDetector(camera_index=0, DEBUG=True)
    # detector = ROIAutoDetector(camera_index=0, DEBUG=False)
    results = detector.run()
    print(f"Detected ROIs: {results}")