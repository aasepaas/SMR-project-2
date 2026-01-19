import cv2
import zxingcpp
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import numpy as np

# Install zxingcpp with: pip install zxing-cpp
class DataMatrixDecoder:
    def __init__(self, use_threads=True, num_threads=10):
        self.use_threads = use_threads 
        self.num_threads = num_threads
        
    @staticmethod
    def process_box(crop_box):
        datamatrices = zxingcpp.read_barcodes(crop_box)
        if datamatrices:
            datamatrix = datamatrices[0]
            return {
                'text': datamatrix.text, # String content of the datamatrix
                'format': str(datamatrix.format), # Format type, e.g. "DataMatrix"
                'content_type': str(datamatrix.content_type), # 
                'position': datamatrix.position # 
            }
        else:
            return {
                'text': None,
                'format': None,
                'content_type': None,
                'position': None
            }

    def decode_datamatrices(self, boxes: dict):
        results: dict = {}
        if self.use_threads:
            with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                future_to_idx = {executor.submit(self.process_box, box): idx for idx, box in boxes.items()}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    results[idx] = future.result()
        else:
            for idx, box in boxes.items():
                results[idx] = self.process_box(box)
        self.results = results

    def get_results(self) -> dict[int, str]:
        if not hasattr(self, 'results') or not self.results:
            return {}
        return {idx: entry.get('text') for idx, entry in self.results.items()}

def main():
    # --- Config ---
    USE_THREADS = True  # Set to False for single-threaded processing
    NUM_THREADS = 10

    # --- Load image and boxes ---
    img = cv2.imread('test_raw_20.png')
    if img is None:
        raise FileNotFoundError("Image 'test_raw_20.png' not found.")
    with open('test_raw_20_boxes.json', 'r') as f:
        boxes = json.load(f)

    crops: dict[int, np.ndarray] = {}
    for idx, box in enumerate(boxes):
        x1, y1, x2, y2 = box['x1'], box['y1'], box['x2'], box['y2']
        crops[idx+1] = img[y1:y2, x1:x2]

    test_decoder = DataMatrixDecoder(use_threads=USE_THREADS, num_threads=NUM_THREADS)
    start_time = time.perf_counter()
    test_decoder.decode_datamatrices(crops) # Send all crops at once
    results = test_decoder.get_results()
    end_time = time.perf_counter()
    processing_time = end_time - start_time
    # print(f"Datamatrix processing time: {processing_time:.3f} seconds")
    print(f"Datamatrix processing time: {processing_time*1000:.3f} milliseconds")

    for idx, box in enumerate(boxes):
        res = results[idx+1]
        print(f"Box {idx+1}: {res}")
        
    # --- Visualize barcode text on original image with OpenCV imshow ---
    img_vis = img.copy()
    results = dict(sorted(results.items()))  # Sort results by index
    for idx in results.keys():
        res = results.get(idx)
        box = boxes[idx-1]
        if res:
            x1, y1, x2, y2 = box['x1'], box['y1'], box['x2'], box['y2']
            cv2.rectangle(img_vis, (x1, y1), (x2, y2), (0, 255, 0), 2*2)
            cv2.putText(img_vis, res, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5*2, (0,0,255), 2*2)

    cv2.namedWindow('image', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('image', 1920//2, 1080//2)  # Set display window size, but image stays original resolution
    cv2.moveWindow('image', 0, 0)  # Move window to top-left corner
    # cv2.resizeWindow('image', 1920*2, 1080*2)  # Set display window size, but image stays original resolution
    # cv2.moveWindow('image', -1920*2, -540)  # Move window to top-left corner
    cv2.imshow('image', img_vis)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    main()