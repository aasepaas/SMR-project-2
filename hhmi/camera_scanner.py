import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"  # OpenCV warnings uitschakelen

import time
import numpy as np
import cv2
from cv2.typing import MatLike

# Private imports
from feed import resize_frame
from roi_auto_detector import ROIAutoDetector
from decoders import DataMatrixDecoder, BarcodeDecoder
from profile_setup import standard_profile, wallet_profile, giftbox_profile, barcode_profile, ScanProfile

# Debugging
from logging_config import set_up_loger
import logging
logger = logging.getLogger()
set_up_loger()


# =====================================================================
#  Camera Scanner
# =====================================================================
class CameraScanner:
    # =================================================================
    #  Initialization
    # =================================================================
    def __init__(self, 
                 dm_decoder: DataMatrixDecoder,
                 barcode_decoder: BarcodeDecoder, 
                 detector: ROIAutoDetector, 
                 feed_list: list,
                 profile: ScanProfile = standard_profile, 
                 debug: bool = False,
                 roi_timeout: float = 5.0) -> None: 
        
        # =============================================================
        # Setting up received parameters
        # =============================================================
        self.dm_decoder = dm_decoder
        self.barcode_decoder = barcode_decoder
        self.detector = detector
        self.feed_list = feed_list
        self.profile: ScanProfile = profile
        self.rois: list = profile.rois
        self.DEBUG: bool = debug
        self.isactive: bool = True
        # =============================================================
        # Setting up starting booleans and values
        # =============================================================
        # Set up feed activity
        self.streams = [f.openFeed() for f in feed_list]
        self.frame_scale = 2
                
        # setting up boolean flags and storage variables
        self.running: bool = True
        self.detected_all: bool = False
        self.datamatrixes: list = [] # Stores detected datamatrix codes

        # Store last detected code and its timestamp
        self.last_code: str = ""
        self.last_code_time: float = 0
        
        # Track when ROI was last changed
        self.roi_transition_time: float = time.time()
        # How many seconds to wait on a ROI without a successful datamatrix decode
        self.roi_timeout: float = float(roi_timeout)
                
        # Persistent results across scanning rounds
        self.persistent_results: dict[int, str] = {}  # Results that stay saved (only reset on profile switch)
        # Has the last full set of codes been retrieved by caller?
        self.codes_retrieved: bool = False
        
        # Batch processing state (temporary for current round)
        self.batch_results: dict[int, str] = {}  # Accumulated results for this round
        
        # Start decoders immediately so they run continuously throughout all frames
        self.dm_decoder.start()
        self.barcode_decoder.start()
        
    def __del__(self) -> None:
        print("Stop Scanner file")
        # Flush any remaining work and stop decoder workers
        try:
            if self.dm_decoder:
                self.dm_decoder.flush()
                self.dm_decoder.stop()
            if self.barcode_decoder:
                self.barcode_decoder.flush()
                self.barcode_decoder.stop()
        except Exception as e:
            logger.error(f"Error stopping decoders: {e}")
            
        # Close camera and all windows
        cv2.destroyAllWindows()
        
    def set_active(self, idx):
        for i, f in enumerate(self.feed_list):
            f.isactive = (i == idx)

                

    # =====================================================================
    #  Main loop
    # =====================================================================    
    
    def __retrieve_rois(self, frame):
        try:
            # if self.profile.name != standard_profile.name:
            #     # Temporarily use standard_profile for consistent ROI detection
            #     self.feed_list[self.profile.camera_index].configure_camera(profile=standard_profile, set_resolution=False)
            #     self.profile = standard_profile
            #     time.sleep(0.5)  # small delay for camera to stabilise
            #     return []
            
            if self.DEBUG:
                rois = self.detector.capture_loop(frame)
            else:
                rois = self.detector.run(frame)    
            if not rois:
                return []
            
            # print(f"{len(rois)} ROI's detected, exiting capture loop.")
            cv2.destroyAllWindows()
            # Restore the target profile settings
            self.feed_list[self.profile.camera_index].configure_camera(profile=self.profile, set_resolution=False)
            
            logger.debug(f"Assigned {len(rois)} ROIs from auto-detection for profile {self.profile.name}")
            return rois

        except Exception as e:
            logger.error(f"Auto ROI detection failed in scanner: {e}")

    #! Single batch
    def __create_roi_grid(self, frame, display_hor = False) -> MatLike:
        """Create a 5x10 grid visualization of all ROIs."""
        total = len(self.rois)
        cols = max(total//10, 1)
        rows = max(total//5, 1)
        print(f"{total} ROIs to display in grid of {cols} cols and {rows} rows")
        
        # print(f"width = {frame.shape[1]}, height = {frame.shape[0]}")
        top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], self.rois[0])
        roi_width, roi_height = right - left, bottom - top
        print(f"Each ROI box size: {roi_width}x{roi_height}")
        
        # Create canvas (convert to BGR for colored borders)
        canvas = np.zeros((rows * roi_height, cols * roi_width, 3), dtype=np.uint8)
        
        # Fill grid with ROIs
        for idx, roi in enumerate(self.rois):
            if idx >= cols * rows:  # Stop if more than 50 ROIs
                break
            
            if display_hor: # Horizontal filling
                row = idx // cols  # Which row (0-4 -> row 0, 5-9 -> row 1, etc.)
                col = idx % cols   # Which column within that row (0-4)
            else: # Vertical filling
                col = idx // rows  # Which column (0-9 -> col 0, 10-19 -> col 1, etc.)
                row = idx % rows   # Which row within that column (0-9)
            
            # Extract ROI
            top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
            roi_box = frame[top:bottom, left:right]
            gray_roi = cv2.cvtColor(roi_box.astype("uint8"), cv2.COLOR_BGR2GRAY)
            
            # Resize to fit grid cell
            resized = cv2.resize(gray_roi, (roi_width, roi_height))
            
            # Convert grayscale to BGR for colored border
            resized_bgr = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
            
            # Place in grid
            y_start = row * roi_height
            y_end = y_start + roi_height
            x_start = col * roi_width
            x_end = x_start + roi_width
            canvas[y_start:y_end, x_start:x_end] = resized_bgr
            
            # Draw green border if ROI is already decoded
            if idx in self.persistent_results and self.persistent_results[idx]:
                color = (0, 255, 0)  # Green border
            else:
                color = (0, 0, 255)  # Red border for undecoded
            cv2.rectangle(canvas, (x_start+1, y_start+1), (x_end-1, y_end-1), color, 2)
        
        return canvas
    
    #! Single batch   
    def __process_frame(self, frame):
        """Extract and convert current ROI to grayscale."""

        for index, roi in enumerate(self.rois):
            # Skip ROIs that are already successfully decoded
            if index in self.persistent_results and self.persistent_results[index]:
                continue
            
            top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
            roi_box = frame[top:bottom, left:right]
            gray_roi = cv2.cvtColor(roi_box.astype("uint8"), cv2.COLOR_BGR2GRAY) 
    
            if self.profile.scan_type != giftbox_profile.scan_type:
                # Stretch contrast: lichtste pixel -> 255, donkerste pixel -> 0
                norm = cv2.normalize(gray_roi, gray_roi, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)  
                if self.profile.scan_type == barcode_profile.scan_type:
                    # Additional preprocessing for DataMatrix codes
                    norm = cv2.rotate(norm, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    # contrast verbeteren (verscherpen)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                    norm  = clahe.apply(norm)
                    
                # Testing low-contrast wallet profile
                elif self.profile.name == wallet_profile.name:
                    min_thresh_value, max_thresh_value, thresh_steps = 5, 250, 16
                    min_adap_thresh_value, max_adap_thresh_value, adap_thresh_steps = 9, 599, 16
                    thresh_values = (min_thresh_value, max_thresh_value, thresh_steps)
                    adap_thresh_values = (min_adap_thresh_value, max_adap_thresh_value, adap_thresh_steps)

                    test = self.test_low_contrast_wallet(norm, thresh_values, adap_thresh_values, max_per_row=6)
                    cv2.imshow("Selected low-contrast threshold", test)
            else:
                resized = cv2.resize(gray_roi, (0,0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                # Stretch contrast: lichtste pixel -> 255, donkerste pixel -> 0
                norm = cv2.normalize(resized, resized, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)       
            
            while True:
                if self.profile.scan_type == barcode_profile.scan_type:
                    if self.barcode_decoder.input_queue.full():
                        continue
                    else:
                        self.barcode_decoder.input_queue.put({"index": index, "frame": norm})
                else:
                    if self.dm_decoder.input_queue.full():
                        continue
                    else:
                        self.dm_decoder.input_queue.put({"index": index, "frame": norm})
                break
        
    #! Multiple batches
    def _preprocess_roi(self, roi_img, variant=0):
        # Convert to grayscale and upscale
        gray = cv2.cvtColor(roi_img.astype("uint8"), cv2.COLOR_BGR2GRAY)
        upscaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        
        if variant == 0:
            # Normalize
            return cv2.normalize(upscaled, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        elif variant == 1:
            # CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            return clahe.apply(upscaled)
        elif variant == 2:
            # Adaptive Threshold
            return cv2.adaptiveThreshold(upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        else:  # variant == 3
            # Sharpen
            blurred = cv2.GaussianBlur(upscaled, (3, 3), 0)
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(blurred, -1, kernel)
            return cv2.normalize(sharpened, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    #! Multiple batches    
    def _extract_roi_image(self, frame, roi_idx):
        if roi_idx >= len(self.rois):
            logger.debug(f"Invalid ROI index {roi_idx}, max is {len(self.rois)-1}")
            return None
        
        roi = self.rois[roi_idx]
        top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
        roi_img = frame[top:bottom, left:right]
        
        if roi_img.shape[0] < 10 or roi_img.shape[1] < 10:
            return None
        
        return roi_img

    #! Multiple batches    
    def _process_roi_batch(self, frame, batch_indices, variant=0, timeout=None):
        for idx in batch_indices:
            if idx not in self.batch_results or not self.batch_results[idx]:
                roi_img = self._extract_roi_image(frame, idx)
                if roi_img is None:
                    continue
                
                processed = self._preprocess_roi(roi_img, variant)
                self.dm_decoder.input_queue.put({"index": idx, "frame": processed})
        
        decoded = self.__decode_roi(timeout=timeout)
        for roi_idx, value in decoded.items():
            if value:
                self.batch_results[roi_idx] = value
        
        return decoded

    #! Multiple batches
    def first_pass(self, total_rois, start_time, scan_timeout, batch_size, batch_timeout, frame):
        """First pass: Process all ROIs in batches with normalize preprocessing."""
        for batch_start in range(0, total_rois, batch_size):
            if time.time() - start_time >= scan_timeout:
                break
            
            batch_end = min(batch_start + batch_size, total_rois)
            batch_indices = list(range(batch_start, batch_end))
            
            self._process_roi_batch(frame, batch_indices, variant=0, timeout=batch_timeout)
                    
    #! Multiple batches
    def second_pass(self, total_rois, batch_size, start_time, scan_timeout, stream_iterator, batch_timeout):
        """Second pass: Focus on undecoded ROIs with sharpen preprocessing."""
        undecoded = [i for i in range(total_rois) 
                    if i not in self.batch_results or not self.batch_results[i]]
        
        if not undecoded:
            return
        
        logger.debug(f"Second pass: {len(undecoded)} ROIs still need decoding")
        
        for batch_start in range(0, len(undecoded), batch_size):
            if time.time() - start_time >= scan_timeout:
                break
            
            batch_end = min(batch_start + batch_size, len(undecoded))
            batch_indices = undecoded[batch_start:batch_end]
            
            # Get fresh frame
            frame = next(stream_iterator)
            if frame is None:
                continue
            
            self._process_roi_batch(frame, batch_indices, variant=3, timeout=batch_timeout)

    #! Multiple batches  
    def third_pass(self, total_rois, start_time, scan_timeout, stream_iterator):
        """Third pass: Focus on remaining undecoded ROIs with all preprocessing variants."""
        final_undecoded = [i for i in range(total_rois) 
                          if i not in self.batch_results or not self.batch_results[i]]
        
        if not final_undecoded or time.time() - start_time >= scan_timeout - 2:
            return
        
        logger.debug(f"Third pass: {len(final_undecoded)} ROIs still need decoding - extended timeout")
        
        # Process each remaining ROI individually with multiple preprocessing variants
        for roi_idx in final_undecoded:
            if time.time() - start_time >= scan_timeout - 0.5:
                break
            
            # Get fresh frame for each ROI
            frame = next(stream_iterator)
            if frame is None:
                continue
            
            roi_img = self._extract_roi_image(frame, roi_idx)
            if roi_img is None:
                continue
            
            # Try only 2 most effective preprocessing variants (saves 50% time = 3s per ROI instead of 6s)
            for variant in [0, 3]:  # Normalize, Sharpen only (CLAHE and Adaptive waste time)
                if time.time() - start_time >= scan_timeout - 0.5:
                    break
                
                processed = self._preprocess_roi(roi_img, variant)
                self.dm_decoder.input_queue.put({"index": roi_idx, "frame": processed})
                
                # Give each variant 2.0 seconds to decode (increased from 1.5s for difficult ROIs)
                decoded = self.__decode_roi()
                if roi_idx in decoded and decoded[roi_idx]:
                    self.batch_results[roi_idx] = decoded[roi_idx]
                    logger.debug(f"ROI {roi_idx+1} decoded with variant {variant}!")
                    break  # Found it, move to next ROI
        
    def run(self, single_batch: bool = True) -> None:
        print("\nW = Wallet profile | G = Giftbox profile | B = Barcode Profile | Q = Stop frame | ESC = quit")
        print("f/g = Focus | e/r = Exposure | b/n = Brightness | SPACE = Next ROI\n")

        logger.info("CameraScanner.run started")
        self.running = True
        # =============================================================
        # Main loop - using while loop to support dynamic camera switching
        # =============================================================
        stream_iterator = None
        current_camera_index = self.profile.camera_index
        self.switch_time = time.time()
        self.timeout_reached = False
        final_results = None
        
        while self.running:
            # =============================================================
            # Switch camera stream if profile changed and update frame iterator
            # =============================================================
            # Check if camera index changed (profile switch) and reinitialize stream
            if current_camera_index != self.profile.camera_index:
                logger.info(f"Camera index changed from {current_camera_index} to {self.profile.camera_index}, reinitializing stream")
                current_camera_index = self.profile.camera_index
                stream_iterator = None

            # Initialize or reinitialize stream iterator
            if stream_iterator is None:
                stream_iterator = iter(self.streams[self.profile.camera_index])
            # Get next frame from current stream
            try:
                frame = next(stream_iterator)
            except StopIteration:
                # Stream ended, reinitialize it
                logger.error("Stream ended, reinitializing")
                stream_iterator = iter(self.streams[self.profile.camera_index])
                break
                continue
            
            # =============================================================
            # If no ROIs assigned yet, try to retrieve them
            # =============================================================
            if not self.rois:
                rois = self.__retrieve_rois(frame)
                if rois:
                    self.rois = rois
                    self.switch_time = time.time()
                else:
                    continue
                
            self.__handle_key()
                                
            if self.timeout_reached or self.detected_all: 
                time.sleep(0.1) #? Reduce CPU usage when timed out or all decoded 
                continue
            
            # print(f"{len(self.rois) = } en {len(self.persistent_results) = }, result = {len(self.rois)} >= {(len(self.persistent_results) - 1)}")
            if len(self.rois) <= 1:
                pass
            else: 
                if len(self.persistent_results) >= len(self.rois):
                    self.detected_all = True
                    self.codes_retrieved = False
                    logger.debug("All ROIs have been successfully decoded.")
                    logger.debug(f"Completed in {time.time() - self.switch_time:.4f} seconds.")
                    continue
                
            if time.time() - self.switch_time > self.profile.total_timeout:    
                logger.critical("Total scan timeout reached.")
                logger.debug("Please retreive codes or switch profile.")
                self.timeout_reached = True
                self.detected_all = True
                self.codes_retrieved = False
            else:
                self.timeout_reached = False
                
                     
            # Wrap the processing in a broad exception catcher so unexpected errors get logged instead of silently terminating the thread.
            try:
                # Start decoders
                if not self.dm_decoder.active:
                    self.dm_decoder.start()
                if not self.barcode_decoder.active:
                    self.barcode_decoder.start()
                
                # Initialize batch_results with persistent results (keep successful decodes)
                self.batch_results = self.persistent_results.copy()
                

                total_rois = len(self.rois)
                processing_rois = total_rois - len(self.persistent_results)
                
                if single_batch: #! Single batch
                    # logger.debug(f"Single batch processing of {processing_rois} ROIs")
                    
                    t2 = time.perf_counter()
                    self.__process_frame(frame) 
                    # Show all ROIs in 5x10 grid
                    roi_grid = self.__create_roi_grid(frame)
                    cv2.imshow("ROI Grid (5x10)", roi_grid)
                    cv2.waitKey(1) # in milliseconds
                    # Expire stored code
                    self.__expire_code_if_needed()

                    # Decode
                    decoded = self.__decode_roi()
                    # If decoder returned no results or only empty strings (e.g. {0: ''}), treat as no decode and continue to next frame.
                    if (not decoded) or (isinstance(decoded, dict) and all(not v for v in decoded.values())):
                        continue
                    
                    t3 = time.perf_counter()
                    logger.warning(f"Frame decode time: {(t3 - t2):.4f} s")         
                    self.flush_decoder_queues()
                    
                    # Keep decoded as a dict ordered by ROI index (ascending)
                    decoded = dict(sorted(decoded.items()))  # dict(int: str)
                    print(f"Decoded: {decoded}")
                    
                    for roi_idx, value in decoded.items():
                        if value:
                            self.persistent_results[roi_idx] = value
                            
                    final_results = {i: self.persistent_results.get(i, "") for i in range(total_rois)}
                    # print(f"Decoded final_results: {final_results}")
                            
                else: #! Multiple batches
                    # logger.debug(f"Multiple batch processing of {total_rois} ROIs")
                    
                    # Small-batch strategy: Process ROIs in small groups with adequate timeout per group
                    # This gives each ROI more dedicated thread time vs processing all 50 at once
                    start_time = time.time()
                    scan_timeout = 25.0 # Total scan timeout for all batches - results in 0.5 seconds per datamatrix
                    batch_size = 10  # Process 10 ROIs at a time
                    batch_timeout = 3.0  # 3 seconds per batch (0.3s per ROI avg)              
                    
                    self.first_pass(total_rois, start_time, scan_timeout, batch_size, batch_timeout, frame)
                    self.second_pass(total_rois, batch_size, start_time, scan_timeout, stream_iterator, batch_timeout)
                    self.third_pass(total_rois, start_time, scan_timeout, stream_iterator)
                    
                    # Validate decoded results - remove invalid strings (ruis/noise)
                    # Datamatrix codes should be mostly numeric, remove anything with invalid chars
                    for roi_idx in list(self.batch_results.keys()):
                        value = self.batch_results[roi_idx]
                        if value:
                            # Check if string contains invalid characters (special chars that shouldn't be in valid codes)
                            if any(c in value for c in ['<', '>', '{', '}', '|', '\\', '^', '`', ';', "'", '*', '!', '@', '#', '$', '%', '&']):
                                logger.critical(f"ROI {roi_idx+1}: Invalid characters detected in '{value}' - removing for retry")
                                self.batch_results[roi_idx] = ""  # Reset to empty so it can be retried
                    
                    num_decoded = sum(1 for v in self.batch_results.values() if v)
                    elapsed = time.time() - start_time
                    logger.debug(f"Batch processing complete: {num_decoded}/{total_rois} decoded in {elapsed:.1f}s")
                    
                    # Save successful decodes to persistent results
                    for roi_idx, value in self.batch_results.items():
                        if value:  # Only save successful decodes
                            self.persistent_results[roi_idx] = value
                                                        
                    # Output final results (from persistent storage)
                    num_decoded = sum(1 for v in self.persistent_results.values() if v)
                    total_rois = len(self.rois)
                    success_rate = (num_decoded / total_rois * 100) if total_rois > 0 else 0
                    elapsed = time.time() - start_time
                    
                    final_results = {i: self.persistent_results.get(i, "") for i in range(total_rois)}
                    final_results = dict(sorted(final_results.items()))
                    print(f"Decoded: {final_results}")
                    
                    logger.warning(f"Scan complete: {num_decoded}/{total_rois} ({success_rate:.1f}%) in {elapsed:.1f}s")
                    
                    # DO NOT reset persistent_results - they persist across scanning rounds! Only reset batch_results for next round
                    self.batch_results = {}
                    self.flush_decoder_queues()

            except Exception as e:
                logger.error(f"Exception in camera scanner main loop: {e}")
                self.dm_decoder.stop()
                self.barcode_decoder.stop()
                # break out of loop on unexpected exception to avoid spinning
                break
                                      
            # Display frames - only when we have final results
            if self.DEBUG:
                if frame is not None:
                    h, w = frame.shape[:2] 
                    
                    for i, roi_box in enumerate(self.rois):
                        decoded_str = None
                        
                        # Draw all ROIs in red, decoded ones in green
                        top, bottom, left, right = self.__roi_box_size(h, w, roi_box)
                        if final_results:    
                            decoded_str = final_results.get(i, "")
                            # print(f"ROI {i+1} decoded string: {decoded_str}")
                        color = (0, 255, 0) if decoded_str else (0, 0, 255) 
                        cv2.rectangle(frame, (left, top), (right, bottom), color, thickness=3)
                        if decoded_str:
                            cv2.putText(frame, decoded_str, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8*self.frame_scale, color, int(2*self.frame_scale))
                    
                    # Show image
                    cv2.imshow("Camera", resize_frame(frame))
                    cv2.waitKey(1)  # in milliseconds
                        
        # No longer running                
        logger.info("CameraScanner.run exiting")
        print(f"Number of detected codes: {len(self.persistent_results)} / {len(self.rois)}")
        self.persistent_results = dict(sorted(self.persistent_results.items()))
        for i in range(len(self.rois)):
            print(f"ROI {i+1}: {self.persistent_results.get(i, '<no code>')}")

    def __handle_key(self) -> None:
        """Process keyboard input from the capture loop."""          
        key = cv2.waitKey(1) & 0xFF
        if key == ord('f'): 
            self.configure_feed_camera_properties(self.profile, 'focus', cv2.CAP_PROP_FOCUS, -1)
        elif key == ord('g'): 
            self.configure_feed_camera_properties(self.profile, 'focus', cv2.CAP_PROP_FOCUS, +1)
        elif key == ord('e'): 
            self.configure_feed_camera_properties(self.profile, 'exposure', cv2.CAP_PROP_EXPOSURE, -1)
        elif key == ord('r'):
            self.configure_feed_camera_properties(self.profile, 'exposure', cv2.CAP_PROP_EXPOSURE, +1)
        elif key == ord('b'): 
            self.configure_feed_camera_properties(self.profile, 'brightness', cv2.CAP_PROP_BRIGHTNESS, -1)
        elif key == ord('n'): 
            self.configure_feed_camera_properties(self.profile, 'brightness', cv2.CAP_PROP_BRIGHTNESS, +1)

    def configure_feed_camera_properties(self, profile: 'ScanProfile', attr_name: str, cap_prop: int, delta: float) -> None:
        """Check which feed is currently active and set current_feed accordingly."""
        try: 
            self.feed_list[self.profile.camera_index].adjust_camera_settings(profile, attr_name, cap_prop, delta)
        except Exception as e:
            logger.error(f"Failed to adjust camera property {attr_name}: {e}")

    # =====================================================================
    #  Change profile (and camera if needed)
    # =====================================================================
    def flush_decoder_queues(self) -> None:
        """Flush both decoder queues."""
        self.dm_decoder.flush()
        self.barcode_decoder.flush()

    def switch_profile(self, new_profile: ScanProfile) -> None:
        """Look up a profile by name and switch to it."""
        
        # Add a check whether the profile is different from the current one
        if self.profile.name == new_profile.name:
            #print(f"Already using profile {new_profile.name}, no switch needed.")
            return

        logger.info(f"Profile switched from {self.profile.name} to {new_profile.name}, resetting persistent results")
        self.persistent_results.clear()        
        
        if self.profile.camera_index != new_profile.camera_index:
            # self.current_feed = (self.current_feed + 1) % len(self.feed_list)
            self.set_active(new_profile.camera_index)
        
        self.profile = new_profile

        # Apply all profile settings (excluding resolution to avoid MSMF errors)
        self.feed_list[self.profile.camera_index].configure_camera(profile=new_profile, set_resolution=False)
        self.__log_profile_settings(self.profile)
        
        # Flush decoder queues after camera hardware switch
        self.flush_decoder_queues()
        self.dm_decoder.stop()
        self.barcode_decoder.stop()
        
        self.rois = self.profile.rois
        self.switch_time = time.time()
        self.timeout_reached = False
        self.detected_all = False
        self.codes_retrieved = False
        
    @staticmethod
    def __log_profile_settings(profile) -> None: 
        """
            Prints the current profile settings to the console.
            Name, type, index, focus, exposure, brightness.
        """
        # Log the change
        print("\n" + "="*50)
        print(f"[PROFILE] Switched to {profile.name} ({profile.scan_type})")
        print(f" Index      -> {profile.camera_index}")
        print(f" Focus      -> {profile.focus}")
        print(f" Exposure   -> {profile.exposure}")
        print(f" Brightness -> {profile.brightness}")
        print("="*50+"\n")
        
    # ==============================================================
    # Roi handling
    # ==============================================================
    @staticmethod
    def __roi_box_size(h, w, roi_box):
        top, bottom, left, right = roi_box
        # Clip bounds
        top = max(0, min(top, h-1))
        bottom = max(top+1, min(bottom, h))
        left = max(0, min(left, w-1))
        right = max(left+1, min(right, w-1))
        return top, bottom, left, right
    
    # def test_low_contrast_wallet(self, frame: MatLike, min_adap_thresh_value: int = 9, max_adap_thresh_value: int = 399, adap_thresh_steps: int = 30, max_per_row: int = 18, thumb_h: int = 120, min_thresh_value: int = 95, max_thresh_value: int = 110, thresh_steps: int = 20):
    def test_low_contrast_wallet(self, frame: MatLike, thresh_values, adap_thresh_values, max_per_row: int = 8):
        """Show a set of simple and adaptive threshold variants for `frame`.

        - `min_norm`, `max_norm`, `steps_norm` control the simple (global) thresholds.
        - `min_block`, `max_block`, `steps` control adaptiveThreshold block sizes.
        """
        thumb_h: int = frame.shape[0]
        min_thresh_value, max_thresh_value, thresh_steps = thresh_values
        min_adap_thresh_value, max_adap_thresh_value, adap_thresh_steps = adap_thresh_values
        
        # Normal/global thresholds series
        normal_results = self._threshold_series(frame, mode='normal', min_val=min_thresh_value, max_val=max_thresh_value, steps_norm=thresh_steps)
        im_h1 = self._tile_images(normal_results, max_per_row=max_per_row, thumb_h=thumb_h)
        if im_h1 is not None and getattr(im_h1, 'size', 0) > 0:
            cv2.imshow("All normal Thresholds", im_h1)
        
        # Generate a series of adaptive thresholds between two odd block sizes
        adaptive_results = self._threshold_series(frame, mode='adaptive', min_block=min_adap_thresh_value, max_block=max_adap_thresh_value, steps=adap_thresh_steps, c=5)
        # Show concatenated result and return the finest (smallest blockSize) image
        # adaptive_results is produced in descending block-size order (max -> min)
        im_h2 = self._tile_images(adaptive_results, max_per_row=max_per_row, thumb_h=thumb_h)
        if im_h2 is not None and getattr(im_h2, 'size', 0) > 0:
            cv2.imshow("All adaptive Thresholds", im_h2)
        return adaptive_results[-2]

    def _threshold_series(self, frame: MatLike, mode: str = 'adaptive', *,
                          # adaptive params
                          min_block: int = 9, max_block: int = 399, steps: int = 10, c: int = 5, blocks: list | None = None,
                          # normal params
                          min_val: int = 95, max_val: int = 110, steps_norm: int = 4):
        """Generate a series of threshold images.

        mode: 'adaptive' or 'normal'.
        For adaptive: use min_block/max_block/steps (or explicit `blocks`) and CLAHE constant `c`.
        For normal: use min_val/max_val/steps_norm.
        Returns list of images ordered from largest-parameter -> smallest.
        """
        def make_odd(x: int) -> int:
            x = max(3, int(x))
            return x | 1

        results = []
        if mode == 'adaptive':
            if blocks is not None:
                raw_blocks = [make_odd(int(x)) for x in blocks]
            else:
                lo, hi = int(min_block), int(max_block)
                if lo > hi:
                    lo, hi = hi, lo
                raw = np.linspace(lo, hi, num=steps)
                raw_blocks = [make_odd(int(round(x))) for x in raw]

            uniq = list(dict.fromkeys(raw_blocks))
            uniq.sort(reverse=True)

            for bs in uniq:
                try:
                    results.append(cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, bs, c))
                except Exception:
                    _, th = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                    results.append(th)

        elif mode == 'normal':
            lo, hi = int(min_val), int(max_val)
            if lo > hi:
                lo, hi = hi, lo
            raw = np.linspace(lo, hi, num=steps_norm)
            vals = [int(round(x)) for x in raw]
            vals = list(dict.fromkeys(vals))
            vals.sort(reverse=True)

            for v in vals:
                try:
                    _, th = cv2.threshold(frame, v, 255, cv2.THRESH_BINARY)
                except Exception:
                    _, th = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                results.append(th)

        else:
            raise ValueError(f"Unknown mode for _threshold_series: {mode}")

        return results

    def _tile_images(self, images: list, max_per_row: int = 18, thumb_h: int = 120):
        """Arrange `images` into rows with up to `max_per_row` per row and fixed thumbnail height.

        Returns a single concatenated image (vconcat of hconcat rows) or an empty
        numpy array when input is empty.
        """
        if not images:
            return np.array([])

        # Resize each image to have height `thumb_h` (preserve aspect ratio)
        thumbs = []
        for im in images:
            if im is None or getattr(im, 'size', 0) == 0:
                continue
            h, w = im.shape[:2]
            if h == 0:
                continue
            scale = thumb_h / h
            new_w = max(1, int(round(w * scale)))
            thumbs.append(cv2.resize(im, (new_w, thumb_h)))

        rows = []
        for i in range(0, len(thumbs), max_per_row):
            chunk = thumbs[i:i+max_per_row]
            if len(chunk) == 1:
                rows.append(chunk[0])
            else:
                try:
                    rows.append(cv2.hconcat(chunk))
                except Exception:
                    rows.append(chunk[0])

        if not rows:
            return np.array([])
        if len(rows) == 1:
            return rows[0]

        # Ensure all rows have the same width by padding with black on the right
        widths = [r.shape[1] for r in rows]
        max_w = max(widths)
        padded_rows = []
        for r in rows:
            h, w = r.shape[:2]
            if w < max_w:
                pad_w = max_w - w
                padded = cv2.copyMakeBorder(r, 0, 0, 0, pad_w, cv2.BORDER_CONSTANT, value=0)
                padded_rows.append(padded)
            else:
                padded_rows.append(r)

        return cv2.vconcat(padded_rows)
            
    # ==============================================================
    # Decoders (per profile) and update code
    # ==============================================================
    def __decode_roi(self):
        # --- DataMatrix profiles ---
        if self.profile.scan_type == "datamatrix":
            # Wait for all ROI decodes to complete
            return self.dm_decoder.get_results()
        
        # --- Barcode profiles ---
        elif self.profile.scan_type == "barcode":
            return self.barcode_decoder.get_results()
        
        else:
            return {}

    def __expire_code_if_needed(self) -> None:
        """ Clear `last_code` when it has exceeded `profile.data_timeout`. """
        if self.last_code:
            elapsed = time.time() - self.last_code_time
            if elapsed > (self.profile.data_timeout or 0):
                logger.info(f"Code expired: {self.last_code}")
                self.last_code = ""

    # ==============================================================
    # Others
    # ==============================================================
    # Bastiaan waarom heb ik deze methode?
    def update_state(self, state: str) -> str:
        if (self.state != state):
            logger.info(f"State changed to: {state}")
            self.previous_state = self.state
            self.state = state
        return self.state
    
    # Gebruik deze methode voor het ophalen van de laatste code   
    def get_code(self) -> dict[int, str] | None: # | str | None:
        # Return the full persistent results once when a full decode has completed.
        # Use `codes_retrieved` to ensure the caller only receives the set once
        # and avoid toggling `detected_all` which causes the main loop to re-log.
        if self.profile == wallet_profile:
            scanWaarde = {1: 'ID001'}
            return scanWaarde
        else:
            scanWaarde = {
                1: "BOX001",
                2: "BOX002",
                3: "BOX003",
                4: "BOX004",
                5: "BOX005",
                6: "BOX006",
                7: "BOX007",
                8: "BOX008",
                9: "BOX009",
                10: "BOX0101",
                11: "BOX011",
                12: "BOX012",
                13: "BOX013",
                14: "BOX014",
                15: "BOX015",
                16: "BOX016",
                17: "BOX017",
                18: "BOX018",
                19: "BOX019",
                20: "BOX020",
                21: "BOX021",
                22: "BOX022",
                23: "BOX023",
                24: "BOX024",
                25: "BOX025",
                26: "BOX026",
                27: "BOX027",
                28: "BOX028",
                29: "BOX029",
                30: "BOX030",
                31: "BOX031",
                32: "BOX032",
                33: "BOX033",
                34: "BOX034",
                35: "BOX035",
                36: "BOX036",
                37: "BOX037",
                38: "BOX038",
                39: "BOX039",
                40: "BOX040",
                41: "BOX041",
                42: "BOX042",
                43: "BOX043",
                44: "BOX044",
                45: "BOX045",
                46: "BOX046",
                47: "BOX047",
                48: "BOX048",
                49: "BOX049",
                50: "BOX050",
            }
            return scanWaarde



        if self.detected_all and not self.codes_retrieved:
            self.codes_retrieved = True
            # return a shallow copy to avoid caller mutating internal state
            return dict(self.persistent_results)
            # if self.profile.name == "GiftBox":
            #     return self.datamatrixes    
            # else: 
            #     return self.last_code
        return None
    
    # =====================================================================
    #  Shutdown
    # =====================================================================
    def exit_loop(self) -> None:
        self.running = False
        