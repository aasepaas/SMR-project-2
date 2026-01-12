import cv2
import numpy as np

from DBSCANFiltering import DBSCANFiltering
from feed import resize_frame

# Debugging
from logging_config import set_up_loger
import logging
logger = logging.getLogger()
set_up_loger()

def nothing(x):
    pass

class ROIAutoDetector:
    """
    Automatically detect datamatrices in camera feed and extract ROI coordinates.
    
    Usage:
    - Press 'q' to quit and accept detected ROIs
    - Press any other key to recalculate ROIs
    - Adjust `expected_n_rois` to set how many ROIs to expect
    - Set `DEBUG` to True to see debug information on screen
    - Set `DEBUGPROCESS` to True to see intermediate processing steps
    """
    
    def __init__(self, expected_n_rois = 50, DEBUG: bool = False, DEBUGPROCESS: bool = False):
        self.debug = DEBUG
        self.debug_process = DEBUGPROCESS
        self.expected_n_rois = expected_n_rois  # Verwacht aantal ROI's
        self.threshold_value = None  # Standaard geen vaste tresh value    
        self.frame_scale = 2       
                             
    @staticmethod
    def __connected_components_filtering(frame, Min_area=100, Max_area=500_000, squareness=10, connect=8):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(frame, connectivity=connect)

        full_mask = np.zeros(labels.shape, dtype="uint8")
        points = []

        for label in range (1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]
            # msg = f"Fijne filter area: {area}" if squareness == 1 else f"Groffe filter area: {area}"
            # print(msg)
            
            # Verwijder kleine ruis
            if area >= Max_area or area <= Min_area: 
                continue
            
            # Verwijder data niet vierkant genoeg 
            if abs(stats[label, cv2.CC_STAT_WIDTH] - stats[label, cv2.CC_STAT_HEIGHT]) > squareness: 
                continue

            x, y, w, h = stats[label, cv2.CC_STAT_LEFT], stats[label, cv2.CC_STAT_TOP], stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]           
            points.append((x, y, w, h))
            full_mask[labels == label] = 255
            
            # if squareness == 1: 
            #     print(f"Contour found - Area: {area}, x:{x}, y:{y}, w:{w}, h:{h}")
            
        # cv2.imshow("Connected Components", resize(full_mask, 1.0))
        return full_mask, points  

    @staticmethod
    def test_threshold_values(frame) -> int:
        windowname = "Test Threshold Values"
        cv2.namedWindow(windowname)
        cv2.createTrackbar('ThresholdValue', windowname, 0, 255, nothing)
        
        while True: 
            threshold_value = cv2.getTrackbarPos('ThresholdValue', windowname)
            _, th = cv2.threshold(frame, threshold_value, 255, cv2.THRESH_BINARY)
            cv2.imshow(windowname, resize_frame(th))
            k = cv2.waitKey(1) & 0xFF
            if k == ord('q'): # 27 is ESC
                break
        cv2.destroyAllWindows()
        print(f"Selected threshold value: {threshold_value}")
        return threshold_value
    
    def __preprocess_frame(self, frame):
        """Preprocess frame for better contour detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        #! Moet misschien maar gewoon weglaten, omdat we al een blur toepassen
        # contrast verbeteren (verscherpen)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl1  = clahe.apply(gray)
        if self.debug_process: 
            cv2.imshow("createCLAHE", resize_frame(cl1)) 
        
        # contrast verbeteren (blurren)
        blur = cv2.GaussianBlur(cl1 , (5, 5), 0)
        if self.debug_process:
            cv2.imshow("GaussianBlur", resize_frame(blur)) 
        
        # thresholding 
        if self.threshold_value is None:
            self.threshold_value = 185 
            if self.debug_process: 
                self.threshold_value = self.test_threshold_values(blur)  # Uncomment to use trackbar for threshold value selection      
        _, th = cv2.threshold(blur, self.threshold_value, 255, cv2.THRESH_BINARY)        
        if self.debug_process: 
            cv2.imshow(f"Threshold blur {self.threshold_value}", resize_frame(th))

        # grove filtering met connected components
        Grove_filter, _ = self.__connected_components_filtering(th, Min_area=100, Max_area=40_000, squareness=15, connect=4)                    
        if self.debug_process: 
            cv2.imshow("Grove_filter", resize_frame(Grove_filter))

        # Make bounding rectangles around detected components
        contours, _ = cv2.findContours(Grove_filter, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)   
            side = ch if cw - ch < 0 else cw
            cv2.rectangle(Grove_filter, (x, y), (x + side, y + side), (255), -1)     
        if self.debug_process: 
            cv2.imshow("Bounding Rectangles", resize_frame(Grove_filter)) 
        
        # Fijne filtering met connected components
        Fijne_filter, boxes = self.__connected_components_filtering(Grove_filter, Min_area=1000*self.frame_scale, Max_area=100_000, squareness=1, connect=8) # Used to be 1000 with 1280x720, with 4K now 4000                    
        if self.debug_process: 
            cv2.imshow("Fijne_filter", resize_frame(Fijne_filter))


        # =========================================================
        # Make list of all coordinates: 
        # =========================================================       
        centers_list = []
        for box in boxes:
            x, y, w, h = box
            cX, cY = x + w // 2, y + h // 2
            centers_list.append((cX, cY)) 
        
        return Fijne_filter, boxes, centers_list
              
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
        
        
        DBSfilter = DBSCANFiltering(data=centers_list, eps=35*self.frame_scale, min_samples=9)
        valid_indices, labels  = DBSfilter.get_filtered_indices(y_as=False)
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
            label = str((int(cX), int(cY)))
            textbox = (cX, cY - 45) # 25

            cv2.rectangle(th, (x, y), (x + cw, y + ch), (128), 2)
            cv2.circle(th, (cX, cY), 10, (128), 2)
            cv2.putText(th, label, textbox, cv2.FONT_HERSHEY_SIMPLEX, float(0.5*self.frame_scale), (200,200,200), int(1*self.frame_scale))
            if self.debug_process: 
                cv2.imshow("Centers", resize_frame(th)) 
                
            rois.append((top, bottom, left, right))
                    
        return rois    
    
    @staticmethod
    def __sort_rois_column_major(rois: list[tuple[int,int,int,int]]) -> dict[int, tuple[int,int,int,int]]:
        """Sort ROIs column-major but ensure each column is ordered top->bottom.

        This implements a simple 1D k-means on the x-centers (`cx`) to
        group ROIs into `n_columns` (approx len(rois)/10), then sorts each
        column by y-center (`cy`) ascending so indices go top-to-bottom
        within each column.
        """
        import numpy as np

        if not rois:
            return {}

        centers = []
        for roi in rois:
            top, bottom, left, right = roi
            cx = (left + right) / 2.0
            cy = (top + bottom) / 2.0
            centers.append((roi, cx, cy))

        # Estimate number of columns assuming ~10 rows per column
        n_cols = max(1, int(round(len(rois) / 10)))

        xs = np.array([c[1] for c in centers])

        # Initialize centroids uniformly across the range
        minx, maxx = float(xs.min()), float(xs.max())
        if n_cols == 1:
            centroids = np.array([(minx + maxx) / 2.0])
        else:
            centroids = np.linspace(minx, maxx, n_cols)

        # Simple 1D k-means (small fixed iterations)
        assignments = [[] for _ in range(n_cols)]
        for _ in range(10):
            assignments = [[] for _ in range(n_cols)]
            for idx, x in enumerate(xs):
                j = int(np.argmin(np.abs(centroids - x)))
                assignments[j].append(idx)

            new_centroids = centroids.copy()
            for j in range(n_cols):
                if assignments[j]:
                    new_centroids[j] = float(xs[assignments[j]].mean())

            if np.allclose(new_centroids, centroids):
                break
            centroids = new_centroids

        # Order columns by centroid x (left to right)
        col_order = sorted(range(n_cols), key=lambda j: centroids[j])

        sorted_rois: list[tuple[int, int, int, int]] = []
        for j in col_order:
            idxs = assignments[j]
            # Map to (roi, cx, cy) and sort by cy (top to bottom)
            col_items = [centers[i] for i in idxs]
            col_items.sort(key=lambda x: x[2])
            sorted_rois.extend([x[0] for x in col_items])
            
        sorted_with_index = {idx+1 : roi for idx, roi in enumerate(sorted_rois)}

        return sorted_with_index


    @staticmethod
    def __draw_rois_on_frame(frame, rois, frame_scale: float = 1.0):
        """Draw detected ROIs on frame with labels."""
        
        for idx, (top, bottom, left, right) in rois.items():
            # top, bottom, left, right = roi
            # Draw green rectangle
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            # Draw label
            cv2.putText(frame, f"ROI {idx}", (left, top - 5), cv2.FONT_HERSHEY_SIMPLEX, float(1*frame_scale), (0, 255, 0), int(2*frame_scale))
        
        return frame
      
    def __recalculate_rois(self, frame):
        """Herbereken ROI's op basis van het huidige frame."""
        print("\nHerberekenen van ROI's...")
        rois_list = self.__detect_rois_opencv(frame)
        rois_dict = self.__sort_rois_column_major(rois_list)
        detected_frame = self.__draw_rois_on_frame(frame, rois_dict, frame_scale=self.frame_scale)
        print(f">>> {len(rois_list)} ROI's gedetecteerd\n")
        
        return detected_frame, rois_dict

    def run(self, frame) -> dict[int, tuple[int, int, int, int]]:
        """Detecteer ROI's. Roep zelf destroywindows aan"""
        
        frame_copy = frame.copy()       
        # Als nog geen ROI's gedetecteerd zijn, doe dit nu
        display_frame, rois = self.__recalculate_rois(frame_copy)
        if rois:
            # display_frame = resize_frame(display_frame)
            # Maak display frame
            begin = 20*self.frame_scale
            steps = 40*self.frame_scale
            if self.debug: 
                # display_frame = self.detected_frame.copy() if self.detected_frame is not None else frame
                cv2.putText(display_frame, f"ROIs found: {len(rois)}", (begin, begin+steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.5*self.frame_scale), (0, 255, 0), int(3*self.frame_scale))
                cv2.putText(display_frame, "Press q to save", (begin, begin+2*steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.2*self.frame_scale), (255, 255, 0), int(3*self.frame_scale))
                cv2.putText(display_frame, "Press any to recalculate", (begin, begin+3*steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.2*self.frame_scale), (255, 255, 0), int(3*self.frame_scale))
                cv2.imshow("ROI Auto Detector", resize_frame(display_frame))
            else: 
                # self.__save_to_file()
                print("\nROI list for code:")
                for idx, (top, bottom, left, right) in rois.items():
                    print(f"roi {idx:>2} = ({top}, {bottom}, {left}, {right})")
     
        return rois

    def capture_loop(self, frame, max_attempts: int = 5, automatic: bool = True) -> dict[int, tuple[int, int, int, int]]:
        """
        Process a single `frame` interactively and return detected ROIs when the
        user confirms (presses `q`).

        - `frame`: BGR image to process.
        - `max_attempts`: Maximum number of automatic recalculation attempts
          when `automatic` is True. Every attempt adjusts the threshold by adding 5 to the threshold value.
        
        If max_attempts is reached without detecting the expected number of ROIs,
        the debug process view is enabled for manual threshold selection.
          
        Returns a list of detected ROIs as tuples `(top, bottom, left, right)`
        when the user presses `q`. Returns an empty list otherwise to retreive new frame.
        """

        Results = self.run(frame)
   
        if automatic:  
            counter = 0
            while counter <= max_attempts: 
                if counter == max_attempts:
                    self.debug_process = True
                    self.threshold_value = None  # Reset tresh value to allow manual selection
                    logger.critical("Final attempt reached, enabling debug process view.")
                    logger.critical("Automatic retrying disabled. Please select threshold value manually.")
                    break    
                
                if len(Results) == self.expected_n_rois:
                    logger.approved(f"Expected number of {self.expected_n_rois} ROIs detected in {counter+1} attempts. Returning automatically.") # type: ignore (logger.approved not in Logger by default)
                    return Results
                else: 
                    counter += 1
                    logger.denied(f"Fail {counter}: Detected {len(Results)} ROIs, expected {self.expected_n_rois}.") # type: ignore (logger.denied not in Logger by default)
                    if isinstance(self.threshold_value, int):
                        self.threshold_value += 5 # Verhoog tresh value elke poging
                    logger.info(f"Adjusting tresh value to {self.threshold_value} and retrying...")
                    Results = self.run(frame)

        Results = self.run(frame)
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            return Results
        else:
            return {}

    
        
        
if __name__ == "__main__":
    # cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # # set capture properties
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3920) # 640, 1280
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160) # 480, 720

    from feed import LiveFeed, VideoFeed
    # feed = LiveFeed("Test Feed", True, 1)
    # feed = VideoFeed("Recorded Video 2 (Camera 4K Webcam)", True, "Jasmijn_code/videos/recorded_output4.avi", loop=True)
    feed = VideoFeed("Recorded Video 2 (Camera 4K Webcam)", True, "Jasmijn_code/videos/test_mjpg_1.avi", loop=True)
    stream = feed.openFeed()
    
    detector1 = ROIAutoDetector(expected_n_rois=51, DEBUG=True, DEBUGPROCESS=False)
    results = {}
    
    try:
        while True:
            frame = next(stream)
            
            if results == {}: 
                print("In capture loop, waiting for user input...")
                results = detector1.capture_loop(frame, max_attempts=5, automatic=True)
            elif results != {}:
                print(f"{len(results)} ROI's detected, exiting capture loop.")
                break
    finally:
        cv2.destroyAllWindows()

    for i, (top, bottom, left, right) in results.items():
        print(f"{i:>02}: xmin = {top:>4}, xmax = {bottom:>4}, ymin = {left:>4}, ymax = {right:>4}")
