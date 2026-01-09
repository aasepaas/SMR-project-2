import cv2
import numpy as np

from typing import List, Tuple
from DBSCANFiltering import DBSCANFiltering
from feed import resize_frame
class ErrorNoROICenters(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class ROIAutoDetector:
    """
    Automatically detect datamatrices in camera feed and extract ROI coordinates.
    
    Usage:
    - Press 'c' to recapture frame and detect all datamatrices
    - Press 'q' to quit and accept detected ROIs
    """
    
    def __init__(self, expected_n_rois = 100, DEBUG: bool = False, DEBUGPROCESS: bool = False):
        self.debug = DEBUG
        self.debug_process = DEBUGPROCESS
        self.frame_scale = 2       
        self.expected_n_rois = expected_n_rois  # Verwacht aantal ROI's
             
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

    def __preprocess_frame(self, frame):
        """Preprocess frame for better contour detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
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
        _, th2 = cv2.threshold(blur, 185, 255, cv2.THRESH_BINARY)        
        if self.debug_process: 
            cv2.imshow("Threshold blur 185", resize_frame(th2))
        # _, th3 = cv2.threshold(blur, 185+15, 255, cv2.THRESH_BINARY)        
        # if self.debug_process: 
        #     cv2.imshow("Threshold blur 200", resize_frame(th3))
        # _, th4 = cv2.threshold(blur, 185+30, 255, cv2.THRESH_BINARY)        
        # if self.debug_process: 
        #     cv2.imshow("Threshold blur 215", resize_frame(th4))
        # _, th5 = cv2.threshold(blur, 185+35, 255, cv2.THRESH_BINARY)        
        # if self.debug_process: 
        #     cv2.imshow("Threshold blur 220", resize_frame(th5))

        # Groffe filtering met connected components
        Grove_filter, _ = self.__connected_components_filtering(th2, Min_area=100, Max_area=40_000, squareness=15, connect=4)                    
        if self.debug_process: 
            cv2.imshow("Groffe_filter", resize_frame(Grove_filter))

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
            
        print(f"OpenCV found {len(rois)} ROIs")
        
        return rois    
    
    @staticmethod
    def __sort_rois_column_major(rois):
        """Sort ROIs column-major but ensure each column is ordered top->bottom.

        This implements a simple 1D k-means on the x-centers (`cx`) to
        group ROIs into `n_columns` (approx len(rois)/10), then sorts each
        column by y-center (`cy`) ascending so indices go top-to-bottom
        within each column.
        """
        import numpy as np

        if not rois:
            return []

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

        sorted_rois = []
        for j in col_order:
            idxs = assignments[j]
            # Map to (roi, cx, cy) and sort by cy (top to bottom)
            col_items = [centers[i] for i in idxs]
            col_items.sort(key=lambda x: x[2])
            sorted_rois.extend([x[0] for x in col_items])

        return sorted_rois

    @staticmethod
    def __draw_rois_on_frame(frame, rois, frame_scale: float = 1.0):
        """Draw detected ROIs on frame with labels."""
        
        for i, (top, bottom, left, right) in enumerate(rois):
            # Draw green rectangle
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            # Draw label
            cv2.putText(frame, f"ROI {i+1}", (left, top - 5), cv2.FONT_HERSHEY_SIMPLEX, float(1*frame_scale), (0, 255, 0), int(2*frame_scale))
        
        return frame
      
    def __recalculate_rois(self, frame):
        """Herbereken ROI's op basis van het huidige frame."""
        print("\n>>> Herberekenen van ROI's...")
        rois = self.__detect_rois_opencv(frame)
        rois = self.__sort_rois_column_major(rois)
        detected_frame = self.__draw_rois_on_frame(frame, rois, frame_scale=self.frame_scale)
        print(f">>> {len(rois)} ROI's gedetecteerd\n")
        
        return detected_frame, rois

    def run(self, frame) -> List[Tuple[int, int, int, int]]:
        """Detecteer ROI's. Roep zelf destroywindows aan"""
        
        frame_copy = frame.copy()       
        # Als nog geen ROI's gedetecteerd zijn, doe dit nu
        display_frame, rois = self.__recalculate_rois(frame_copy)
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
            print("\nROI List for code:")
            for i, (top, bottom, left, right) in enumerate(rois):
                print(f"roi_{i+1} = ({top}, {bottom}, {left}, {right})")
     
        return rois

    def capture_loop(self, frame) -> List[Tuple[int, int, int, int]]:
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
        # while True:
         
        if len(Results) == self.expected_n_rois:
            print(f"Expected number of ROIs ({self.expected_n_rois}) detected.")
            return Results
        
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            return Results
        else:
            return []
        # No relevant key pressed: continue waiting

    
        
        
if __name__ == "__main__":
    from logging_config import init_environment, set_up_loger
    init_environment()
    set_up_loger()

    # cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # # set capture properties
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3920) # 640, 1280
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160) # 480, 720

    from feed import LiveFeed, VideoFeed
    # feed = LiveFeed("Test Feed", True, 1)
    feed = VideoFeed("Recorded Video 2 (Camera 4K Webcam)", False, "Jasmijn/videos/recorded_output4.avi", loop=True)
    stream = feed.openFeed()
    
    detector1 = ROIAutoDetector(DEBUG=True, DEBUGPROCESS=True)
    results = []
    
    try:
        while True:
            # ret, frame = cap.read()
            # if not ret:
            #     break
            frame = next(stream)
            
            if results == []: 
                print("In capture loop, waiting for user input...")
                results = detector1.capture_loop(frame)
            elif results != []:
                print(f"{len(results)} ROI's detected, exiting capture loop.")
                break
    finally:
        # cap.release()
        cv2.destroyAllWindows()

    # for i, (x, y, w, h) in enumerate(results, start=1):
    #     print(f"{i:>02}: x = {x:>4}, y = {y:>4}, w = {w:>4}, h = {h:>4}")
