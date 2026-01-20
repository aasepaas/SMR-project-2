import time
import cv2
from cv2.typing import MatLike
import numpy as np

from DBSCANFiltering import DBSCANFiltering
from feed import resize_frame

# Debugging
from logging_config import set_up_logger
import logging
logger = logging.getLogger()
set_up_logger()

def nothing(x):
    pass

def processframe_timer_func(func):
    # This function shows the execution time of the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time.perf_counter()    
        result = func(*args, **kwargs)
        t2 = time.perf_counter()
        print(f'Function {func.__name__!r} executed in {(t2-t1)*1000:.4f} milliseconds')
        return result
    return wrap_func

def timer_func(func):
    # This function shows the execution time of the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time.perf_counter()    
        result = func(*args, **kwargs)
        t2 = time.perf_counter()
        print(f'Function {func.__name__!r} executed in {(t2-t1)*1000:.4f} milliseconds')
        return result
    return wrap_func

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
    
    def __init__(self, expected_n_rois = 50, threadhold_value = 177, scaling_factor = 1):
        self.expected_n_rois = expected_n_rois  # Verwacht aantal ROI's
        self.threshold_value = threadhold_value  # Standaard geen vaste tresh value    
        self.scaling_factor = scaling_factor    
        self.frame_scale = 2  

        # Store intermediate images for debugging
        self.imgstore_thresholds = {}
        self.imgstore_rough_filter = {}
        self.imgstore_bounding_rect = {}
        self.imgstore_fine_filter = {}
        self.imgstore_centers = {}
        
    @staticmethod
    def __connected_components_filtering(frame: MatLike, Min_area=100, Max_area=500_000, squareness=10, connect=8):
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
    
    #@processframe_timer_func
    def apply_gray(self, frame):
        """Convert frame to grayscale."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.debug_process: 
            cv2.imshow("Gray Frame", resize_frame(gray)) 
        return gray
    
    #@processframe_timer_func
    def apply_CLAHE(self, frame):
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve contrast.
        clipLimit: This parameter sets the threshold for contrast limiting. 
                   By default value is 40. 
        tileGridSize: It is used to divide the image into grids for applying CLAHE. 
                      It sets the number of rows and columns. By default this is 8x8.
        """
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl1  = clahe.apply(frame)
        if self.debug_process: 
            cv2.imshow("createCLAHE (8, 8)", resize_frame(cl1)) 
        return cl1
    
    #@processframe_timer_func
    def apply_GaussianBlur(self, frame):
        """Apply Gaussian Blur to reduce noise and detail in the image."""
        kernel_size = (5, 5)  # Kernel size should be odd and positive
        blur = cv2.GaussianBlur(frame , kernel_size, 0) 
        if self.debug_process:
            cv2.imshow("GaussianBlur (5, 5)", resize_frame(blur)) 
        return blur

    #@processframe_timer_func
    def apply_NormalBlur(self, frame):
        """Apply Normal Blur to reduce noise and detail in the image."""
        kernel_size = (5, 5)  # Kernel size should be odd and positive
        blur = cv2.blur(frame , kernel_size) 
        if self.debug_process:
            cv2.imshow("NormalBlur (5, 5)", resize_frame(blur)) 
        return blur
    #@processframe_timer_func
    def apply_Threshold(self, frame, threshold_value: int, index: int = 0):
        """Apply binary thresholding to the image."""
        #threshold_value = self.test_threshold_values(frame)  # Uncomment to use trackbar for threshold value selection
        _, th = cv2.threshold(frame, threshold_value, 255, cv2.THRESH_BINARY)        
        if self.debug_process: 
            self.imgstore_thresholds[f"Threshold {index}"] = resize_frame(th, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
            # imgstore_thresholds[f"Threshold {threshold_value} {index}"] = resize_frame(th, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
            # cv2.imshow("Threshold", )
            # cv2.imshow(f"Threshold {threshold_value}", resize_frame(th))
        return th

    #@processframe_timer_func
    def apply_RoughFiltering(self, frame, index: int = 0):
        """Apply rough connected components filtering to remove large non-ROI areas."""
        Rough_filter, _ = self.__connected_components_filtering(frame, Min_area=int(80/self.scaling_factor), Max_area=int(40_000/self.scaling_factor), squareness=15, connect=4)                    
        if self.debug_process: 
            self.imgstore_rough_filter[f"Rough_filter {index}"] = resize_frame(Rough_filter, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
            # cv2.imshow("Rough_filter", resize_frame(Rough_filter, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0]))
        return Rough_filter

    #@processframe_timer_func
    def apply_FineFiltering(self, frame, index: int = 0):
        """Apply fine connected components filtering to isolate ROIs."""
        Fine_filter, boxes = self.__connected_components_filtering(frame, Min_area=int(1000*self.frame_scale/self.scaling_factor), Max_area=int(100_000/self.scaling_factor), squareness=1, connect=8) # Used to be 1000 with 1280x720, with 4K now 4000                    
        if self.debug_process: 
            self.imgstore_fine_filter[f"Fine_filter {index}"] = resize_frame(Fine_filter, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
            # cv2.imshow("Fine_filter", resize_frame(Fine_filter, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0]))
        return Fine_filter, boxes
    
    #@processframe_timer_func
    def apply_BoundingRectangles(self, frame, index: int = 0):
        """Make bounding rectangles around detected components."""
        contours, _ = cv2.findContours(frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)  
            middle_x, middle_y = x + int(cw/2), y + int(ch/2) 
            side = ch//2 if cw - ch < 0 else cw//2
            cv2.rectangle(frame, (middle_x-side, middle_y-side), (middle_x + side, middle_y + side), (255), -1)     
        if self.debug_process: 
            self.imgstore_bounding_rect[f"Bounding Rectangles {index}"] = resize_frame(frame, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
            # cv2.imshow("Bounding Rectangles", resize_frame(frame, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0]))
        return frame

    def show_debug_frames(self):
        img_threshold = np.hstack([self.imgstore_thresholds[key] for key in self.imgstore_thresholds])
        img_threshold = cv2.putText(img_threshold, "Threshold", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2, cv2.LINE_AA)
        cv2.imshow("Preprocessed Frame - Thresholds", resize_frame(img_threshold, scale=1*self.scaling_factor, old_width=img_threshold.shape[1], old_height=img_threshold.shape[0]))
        img_rough = np.hstack([self.imgstore_rough_filter[key] for key in self.imgstore_rough_filter])
        img_rough = cv2.putText(img_rough, "Rough filter", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2, cv2.LINE_AA)
        cv2.imshow("Preprocessed Frame - Rough filter", resize_frame(img_rough, scale=1*self.scaling_factor, old_width=img_rough.shape[1], old_height=img_rough.shape[0]))
        img_bounding = np.hstack([self.imgstore_bounding_rect[key] for key in self.imgstore_bounding_rect])
        img_bounding = cv2.putText(img_bounding, "Bounding Rect", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2, cv2.LINE_AA)
        cv2.imshow("Preprocessed Frame - Bounding Rectangles", resize_frame(img_bounding, scale=1*self.scaling_factor, old_width=img_bounding.shape[1], old_height=img_bounding.shape[0]))
        img_fine = np.hstack([self.imgstore_fine_filter[key] for key in self.imgstore_fine_filter])
        img_fine = cv2.putText(img_fine, "Fine filter", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2, cv2.LINE_AA)
        cv2.imshow("Preprocessed Frame - Fine filter", resize_frame(img_fine, scale=1*self.scaling_factor, old_width=img_fine.shape[1], old_height=img_fine.shape[0]))
        if self.imgstore_centers:
            img_centers = np.hstack([self.imgstore_centers[key] for key in self.imgstore_centers])
            img_centers = cv2.putText(img_centers, "Centers", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2, cv2.LINE_AA)
            cv2.imshow("Preprocessed Frame - Centers", resize_frame(img_centers, scale=1*self.scaling_factor, old_width=img_centers.shape[1], old_height=img_centers.shape[0]))
        
        # stacked = np.hstack([img_threshold, img_rough, img_bounding, img_fine, img_centers])
        # cv2.imshow("Preprocessed Frame Final", resize_frame(stacked, scale=1, old_width=stacked.shape[1], old_height=stacked.shape[0]))    
    
    #@processframe_timer_func
    def __preprocess_frame(self, frame):
        """Preprocess frame for better contour detection."""
        # Mogelijkheid 1: thresh_value =  172 
        # Resize -> Gray -> Gaussian Blur -> CLAHE -> Threshold -> Rough filter -> Bounding Rectangles -> Fine filter -> Retreive ROIs
        # Mogelijkheid 2: # thresh_value =  121 
        # Resize -> Gray -> Normal Blur -> Threshold -> Rough filter-> Bounding Rectangles -> Fine filter -> Retreive ROIs
        
        start_threshold_value = int(self.threshold_value)
        margin = int(start_threshold_value * 0.1)  # 10% margin
        steps = 5

        resized_frame = cv2.resize(frame, fx=1/self.scaling_factor, fy=1/self.scaling_factor, 
                           dsize=None, interpolation=cv2.INTER_LINEAR_EXACT)
        gray = self.apply_gray(resized_frame)
        if 121 + margin > start_threshold_value > 121 - margin:
            input_frame = self.apply_NormalBlur(gray)
        else: 
            Gaussianblur = self.apply_GaussianBlur(gray)
            input_frame = self.apply_CLAHE(Gaussianblur)

        def make_slices(frame, amount_of_slices: int = 7, slice_margin_y: int = 0, slice_margin_x: int = 0) -> list[tuple[MatLike, int, int]]:
            if amount_of_slices == 1:
                return [(frame, 0, 0)]
            width, height = int(frame.shape[1]/amount_of_slices), int(frame.shape[0])
            
            slices_with_offset = []
            for i in range (1, amount_of_slices-1):
                ymin, ymax, xmin, xmax = 0+slice_margin_y, height-slice_margin_y, width*i+slice_margin_x, width*(i+1)-slice_margin_x
                frame = cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0,0,255), 3)
                slices_with_offset.append((frame[ymin:ymax, xmin:xmax], xmin, ymin)) # top:bottom, left:right] 
            
            if self.debug_process: 
                display_imgs = [s[0] for s in slices_with_offset]
                cv2.imshow("Preprocessed Frame", resize_frame(np.hstack(display_imgs), scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0]))            
            return slices_with_offset
        
        def adjust_roi_coordinates(rois: list[tuple[int,int,int,int]], x_offset: int, y_offset: int) -> list[tuple[int,int,int,int]]:
            """Adjust ROI coordinates from slice-relative to frame-relative."""
            adjusted_rois = []
            for top, bottom, left, right in rois:
                adjusted_rois.append((
                    top     + y_offset * self.scaling_factor,
                    bottom  + y_offset * self.scaling_factor,
                    left    + x_offset * self.scaling_factor,
                    right   + x_offset * self.scaling_factor
                ))
            return adjusted_rois
        
        def attempt_detection(frame: MatLike, threshold_value: int, index: int) -> tuple[list[tuple[int,int,int,int]], bool]:
            """Attempt ROI detection with given threshold value."""
            logger.info(f"Attempting with {threshold_value = }")
            thresholded_image        = self.apply_Threshold(frame, threshold_value, index=index)
            rough_filter             = self.apply_RoughFiltering(thresholded_image, index=index)
            bounding_rect            = self.apply_BoundingRectangles(rough_filter, index=index)
            fine_filter, boxes_local = self.apply_FineFiltering(bounding_rect, index=index)
            if len(boxes_local) == 0: 
                return [], False # No boxes found don't continue the loop further
            rois_local                  = self.retreive_rois(boxes_local, fine_filter, index=index)
            logger.info(f"Detected {len(rois_local)} ROIs with threshold {threshold_value}.")
            return rois_local, True

        def search_threshold_range(frame: MatLike, start: int, end: int, step: int, direction: str, slice_idx=0, expected_rois_per_slice=10) -> list[tuple[int,int,int,int]] | None:
            """Search for ROIs in threshold range. Returns ROIs if found, None otherwise."""
            logger.info(f"Starting {direction} search from {start} to {end} (step={step})")
            for threshold in range(start, end, step):
                rois, success = attempt_detection(frame, threshold, index=slice_idx)
                if not success:
                    logger.critical(f"No boxes found at threshold {threshold}, stopping {direction} search")
                    break 
                if len(rois) == expected_rois_per_slice:
                    logger.approved(f"Slice: {slice_idx + 1} Found {len(rois)} ROIs at threshold {threshold} ({direction}).") # type: ignore (logger.approved not in Logger by default)
                    return rois
            return None
        
        # Process slices
        slices_with_offsets = make_slices(input_frame, amount_of_slices=7)
        expected_rois_per_slice = self.expected_n_rois // (len(slices_with_offsets))
        print(f"Expected ROIs per slice: {expected_rois_per_slice}")
        all_rois = []
        for slice_idx, (slice_img, x_offset, y_offset) in enumerate(slices_with_offsets):
            logger.info(f"Processing slice {slice_idx + 1}/{len(slices_with_offsets)}")
            
            # Try initial threshold
            rois, _ = attempt_detection(slice_img, start_threshold_value, index=slice_idx)
            if len(rois) == expected_rois_per_slice:
                logger.approved(f"Slice: {slice_idx + 1} Found {len(rois)} ROIs at initial threshold {start_threshold_value}") # type: ignore (logger.approved not in Logger by default)
                all_rois.extend(adjust_roi_coordinates(rois, x_offset, y_offset))
                continue 
            
            # Search upward
            max_threshold = min(255, start_threshold_value + margin) # Can't go above 255
            rois = search_threshold_range(slice_img, start_threshold_value + steps, max_threshold + 1, steps, "upward", slice_idx=slice_idx, expected_rois_per_slice=expected_rois_per_slice)
            if rois and len(rois) == expected_rois_per_slice:
                all_rois.extend(adjust_roi_coordinates(rois, x_offset, y_offset))
                continue

            # Search downward
            min_threshold = max(0, start_threshold_value - margin) # Can't go below 0
            rois = search_threshold_range(slice_img, start_threshold_value - steps, min_threshold - 1, -steps, "downward", slice_idx=slice_idx, expected_rois_per_slice=expected_rois_per_slice)
            if rois and len(rois) == expected_rois_per_slice:
                all_rois.extend(adjust_roi_coordinates(rois, x_offset, y_offset))
                continue           # Then search downwards
            
            # Fallback: use whatever was found
            if rois:
                logger.warning(f"Slice {slice_idx + 1}: Found {len(rois)} ROIs, expected {expected_rois_per_slice}")
                all_rois.extend(adjust_roi_coordinates(rois, x_offset, y_offset))
            else:
                rois, _ = attempt_detection(slice_img, start_threshold_value, index=slice_idx)
                logger.critical(f"Slice {slice_idx + 1}: Could not find expected ROIs. Using {len(rois)} from initial threshold")
                all_rois.extend(adjust_roi_coordinates(rois, x_offset, y_offset))
    
        if self.debug_process:
            self.show_debug_frames()
        
        # Final results
        # print(f"Total ROIs detected: {len(all_rois)}: {[r for r in all_rois]}")
        if len(all_rois) == self.expected_n_rois:
            logger.warning(f"Detected ROIs ({len(all_rois)}) expected ({self.expected_n_rois}).")
        else:
            logger.critical(f"Could not detect expected number of ROIs ({self.expected_n_rois}). Detected {len(all_rois)} ROIs.")
        
        return all_rois

    def retreive_rois(self, boxes: list[tuple[int,int,int,int]], frame: MatLike, index:int = 0) -> list[tuple[int,int,int,int]]:
        centers_list = []
        rois = []
        for box in boxes:
            x, y, w, h = box
            cX, cY = x + w // 2, y + h // 2
            centers_list.append((cX, cY)) 
        
        DBSfilter = DBSCANFiltering(data=centers_list, eps=35*self.frame_scale, min_samples=9)
        valid_indices, labels  = DBSfilter.get_filtered_indices(y_as=False)
        if self.debug_process:
            fig = DBSfilter.visualize_dbscan_results(labels)
            DBSCANFiltering.fig_to_cv2(fig)
                   
        for idx in valid_indices:
            #  Get all needed coordinates: 
            x, y, width, height = boxes[idx]
            cX, cY = centers_list[idx]
            
            # Padding as percentage of contour dimensions
            padding = 0.10
            pad_w = int(width * padding)
            pad_h = int(height * padding)
            
            top, bottom = y - pad_h, y + height + pad_h
            left, right = x - pad_w, x + width + pad_w
            
            #  Draw all the information
            if self.debug_process: 
                cv2.rectangle(frame, (left, top), (right, bottom), (200), 2)
                cv2.circle(frame, (cX, cY), 10, (128), 2)
                self.imgstore_centers[f"Centers {index}"] = resize_frame(frame, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])
                # cv2.imshow("Centers", resize_frame(frame, scale=0.3, old_width=frame.shape[1], old_height=frame.shape[0])) 

            rois.append((top*self.scaling_factor, bottom*self.scaling_factor, left*self.scaling_factor, right*self.scaling_factor))
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
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, f"ROI {idx}", (left, top - 5), cv2.FONT_HERSHEY_SIMPLEX, float(1*frame_scale), (0, 255, 0), int(2*frame_scale))
        
        return frame
      
    def __recalculate_rois(self, frame):
        """Herbereken ROI's op basis van het huidige frame."""
        print("\nHerberekenen van ROI's...")
        rois_list = self.__preprocess_frame(frame)
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
            begin, steps= 20*self.frame_scale, 40*self.frame_scale
            if self.debug: 
                cv2.putText(display_frame, f"ROIs found: {len(rois)}", (begin, begin+steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.5*self.frame_scale), (0, 255, 0), int(3*self.frame_scale))
                cv2.putText(display_frame, "Press q to save", (begin, begin+2*steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.2*self.frame_scale), (255, 255, 0), int(3*self.frame_scale))
                cv2.putText(display_frame, "Press any to recalculate", (begin, begin+3*steps), cv2.FONT_HERSHEY_SIMPLEX, float(1.2*self.frame_scale), (255, 255, 0), int(3*self.frame_scale))
                cv2.imshow("ROI Auto Detector", resize_frame(display_frame))
            # else: 
            #     print("\nROI list for code:")
            #     for idx, (top, bottom, left, right) in rois.items():
            #         print(f"roi {idx:>2} = ({top}, {bottom}, {left}, {right})")
     
        return rois

    @timer_func
    def capture_loop(self, frame, automatic: bool = True) -> dict[int, tuple[int, int, int, int]]:
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

        if automatic:  
            self.debug = False
            self.debug_process = False
            return self.run(frame)
        else:
            self.debug = True
            self.debug_process = True
            
        Results = self.run(frame)
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            return Results
        else:
            return {}

    
        
if __name__ == "__main__":
    from feed import LiveFeed, VideoFeed

    camera_index = 1
    feed = LiveFeed(name="Test Feed", active=True, camera_index=camera_index)
    #feed = VideoFeed(name="Recorded Video 2 (Camera 4K Webcam)", active=True, camera_index=camera_index,
    #                 file_name="Jasmijn_code/videos/test_mjpg_1.avi", loop=True)
    stream = feed.openFeed()
    
    detector1 = ROIAutoDetector(
        expected_n_rois=50,
        threadhold_value=172+10,
        scaling_factor=2,
    )
    results = {}
    
    try:
        start_time = time.perf_counter()
        while True:
            frame = next(stream)
            
            if results == {}: 
                print("In capture loop, waiting for user input...")
                results = detector1.capture_loop(frame, automatic=False)
            elif results != {}:
                print(f"{len(results)} ROI's detected, exiting capture loop.")
                break
    finally:
        cv2.destroyAllWindows()
        end_time = time.perf_counter()
        print(f"Elapsed time: {(end_time - start_time)*1000:.4f} milliseconds")
    # for i, (top, bottom, left, right) in results.items():
    #     print(f"{i:>02}: xmin = {top:>4}, xmax = {bottom:>4}, ymin = {left:>4}, ymax = {right:>4}")