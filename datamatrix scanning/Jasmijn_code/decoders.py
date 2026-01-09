import threading
import queue
from abc import ABC, abstractmethod
from pylibdmtx.pylibdmtx import decode as dm_decode
from pyzbar.pyzbar import decode as qr_decode
import time

import random

# Debugging
from logging_config import set_up_loger
import logging
logger = logging.getLogger()
set_up_loger()

class DecoderBase(ABC):
    """Abstract base class containing shared decoder logic.

    Subclasses must implement `_decode(frame) -> list[str]` which performs a
    single-frame decode and returns a decoded object or `None`.
    """

    def __init__(self, num_threads: int = 2, max_queue_size: int = 50, name: str = "Decoder", max_decode_time: float = 5.0):
        self.num_threads = max(1, num_threads)
        self.name = name
        self.max_decode_time = max_decode_time

        self.input_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.items = 0
        self.lock = threading.Lock()
        self.results: dict[int, str] = {}
        self.active = True

        self.threads: list[threading.Thread] = []

        logger.debug(f"{self.name} started with {self.num_threads} thread(s), max decode time: {max_decode_time}s")
    
    def __del__(self):
        self.stop()
        logger.debug(f"{self.name} stopped")
        
    @abstractmethod
    def _decode(self, frame) -> list[str]:
        """Decode a single frame. Return decoded object or None."""

    def _worker(self, try_one_time: bool = False):
        
        while self.active:
            # #! Niet thread safe! (Tussen empty() en get() kan een andere thread het item al gepakt hebben.)
            # if self.input_queue.empty():
            #     time.sleep(0.01)
            #     continue
            # data = self.input_queue.get(timeout=0.5)
            
            #! Wel thread safe!
            try: 
                data = self.input_queue.get(timeout=0.5)
            except queue.Empty:
                time.sleep(0.01)
                continue
            
            
            try: 
                index = data["index"]
                frame = data["frame"]
                
                #-=x Original simple decode attempt
                if try_one_time:
                    # print("Trying single decode attempt")
                    decoded = self._decode(frame)
                    with self.lock:
                        # frame contains only one code so we take the first decoded result
                        self.results[index] = decoded[0] if decoded else ""
                        # Only log successful decodes
                        if decoded:
                            logger.approved(f"{self.name} - ✓ ROI {index+1:>2}: '{self.results[index]}'") # type: ignore
                        else: 
                            logger.denied(f"{self.name} - ✗ ROI {index+1}: Failed") # type: ignore
                        continue
                
                #-=x Enhanced decode with retries until timeout
                # print("Trying multiple decode attempt")

                start_time = time.time()
                decoded_value = ""
                attempts = 0
                
                # Keep trying to decode for max_decode_time seconds
                while attempts < 1: #time.time() - start_time < self.max_decode_time:
                    attempts += 1
                    
                    # Attempt decode
                    decoded = self._decode(frame)
                    
                    if decoded and decoded[0]:
                        decoded_value = decoded[0]
                        if any(c in decoded_value for c in ['<', '>', '{', '}', '|', '\\', '\',' '^', '`', ';', "'", '*', '!', '@', '#', '$', '%', '&']):
                            logger.critical(f"{self.name} - ROI {index+1:>2}: Suspicious characters in decoded value '{decoded_value}'")
                            continue
                        
                        if len(decoded_value) < 12:
                            logger.critical(f"{self.name} - ROI {index+1:>2}: Decoded value '{decoded_value}' is too short")
                            continue

                        with self.lock:
                            # Only update if not already set or was empty
                            if index not in self.results or not self.results[index]:
                                self.results[index] = decoded_value
                                elapsed = time.time() - start_time
                                logger.approved(f"{self.name} - ✓ ROI {index+1:>2}: '{decoded_value}' (attempt {attempts}, {elapsed*1000:.4f}ms)") # type: ignore
                        break
                    
                    # Small delay before retry to avoid hammering
                    time.sleep(0.01)
                
                # If still no result after timeout, store empty string
                if not decoded_value:
                    with self.lock:
                        if index not in self.results or not self.results[index]:
                            self.results[index] = ""
                            elapsed = time.time() - start_time
                            logger.denied(f"{self.name} - ✗ ROI {index+1:>2}: Failed after {attempts} attempts ({elapsed*1000:.4f}ms)") # type: ignore
                            
            except Exception as e:
                logger.error(f"{self.name} decode error for ROI {index+1:>2}: {e}", exc_info=True)
                with self.lock:
                    if index not in self.results or not self.results[index]:
                        self.results[index] = ""
            finally:
                try: 
                    self.input_queue.task_done()
                except ValueError:
                    print("Task already marked done")
                
    def get_results(self):
        """Get accumulated results, wait briefly for queue to process.
        
        Uses queue.join() with proper timeout handling.
        """
        self.input_queue.join()

        with self.lock:
            results = self.results.copy()
        
        # Only log summary
        successful = sum(1 for v in results.values() if v)
        logger.debug(f"{self.name} - Successfully decoded {successful}/{len(results)} ROIs")
        return results
            
    def flush(self) -> None:
        """Clear results and drain the queue."""
        with self.lock:
            self.results = {}
        
        # Drain the queue safely and mark tasks as done so join() won't block.
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.input_queue.task_done()
            except ValueError:
                print("Queue empty during flush")
                break

    
    def start(self) -> None:
        self.active = True
        for i in range(self.num_threads):
            t = threading.Thread(
                target=self._worker, 
                name=f"{self.name}-{i}", 
                daemon=True
            )
            t.start()
            self.threads.append(t)
                
    def stop(self) -> None:
        self.active = False
        self.flush()
        
        for t in self.threads.copy():
            t.join(timeout=1.0)
        self.threads.clear()



class DataMatrixDecoder(DecoderBase):
    """DataMatrix decoder: implements only `_decode` and compatibility aliases."""

    def __init__(self, num_threads: int = 1, max_queue_size: int = 50):
        super().__init__(num_threads=num_threads, max_queue_size=max_queue_size, 
                        name="DataMatrixDecoder")

    def _decode(self, frame) -> list[str]:
        decoded = dm_decode(frame)
        return [item.data.decode("utf-8") for item in decoded]
    
class BarcodeDecoder(DecoderBase):
    """Barcode decoder: implements only `_decode`."""

    def __init__(self, num_threads: int = 1, max_queue_size: int = 50, max_decode_time: float = 5.0):
        super().__init__(num_threads=num_threads, max_queue_size=max_queue_size, 
                        name="BarcodeDecoder", max_decode_time=max_decode_time)

    def _decode(self, frame) -> list[str]:
        decoded = qr_decode(frame)
        return [item.data.decode("utf-8") for item in decoded]
    
class PixelColorDecoder(DecoderBase):
    """Pixel color decoder: implements only `_decode`."""

    def __init__(self, num_threads: int = 1, max_queue_size: int = 50, max_decode_time: float = 5.0):
        super().__init__(num_threads=num_threads, max_queue_size=max_queue_size, 
                        name="PixelColorDecoder", max_decode_time=max_decode_time)

    def _decode(self, frame) -> list[str]:
        # Gemiddelde BGR-kleur
        mean_color = frame.mean(axis=(0, 1)).astype(int)  # BGR!

        # Omzetten naar RGB-string
        rgb_str = (f"   R{mean_color[2]:>3},   G{mean_color[1]:>3},   B{mean_color[0]:>3}")
        
        # Simulate decode time
        decode_time = random.uniform(0.1, 1)
        time.sleep(decode_time)
            
        return [rgb_str] if rgb_str else [""]
    
    
def test_decoders():
    import numpy as np
    import cv2

    # Make pixel list of 50 rgb pixels
    pixels = list({ (r, g, b) 
                    for r in range(0, 256, 32)
                    for g in range(0, 256, 32)
                    for b in range(0, 256, 32) })[:50]

    pixels = [list(p) for p in pixels]
    for i, p in enumerate(pixels):
        print(f"Pixel {i+1:>2}:   R{p[2]:>3},   G{p[1]:>3},   B{p[0]:>3}")

    
    # Grid-instellingen
    block_size = 100
    grid_width = 10
    grid_height = 5
    ROI_margin = -2

    frame_width = grid_width * block_size
    frame_height = grid_height * block_size

    # Frame maken
    frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)

    # Pixels in blokken tekenen
    for i, color in enumerate(pixels):
        col = i % grid_width
        row = i // grid_width

        x_start = col * block_size
        y_start = row * block_size

        frame[
            y_start:y_start + block_size,
            x_start:x_start + block_size
        ] = color

    # Tonen
    # cv2.imshow("Test Frame", frame)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    
    rois = []
    small_frames = []
    for i, color in enumerate(pixels):
        col = i % grid_width
        row = i // grid_width

        x_start = col * block_size
        y_start = row * block_size

        xmin = max(0, x_start - ROI_margin)
        ymin = max(0, y_start - ROI_margin)
        xmax = min(frame_width, x_start + block_size + ROI_margin)
        ymax = min(frame_height, y_start + block_size + ROI_margin)

        # ROI opslaan
        rois.append({
            "index": i,
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax
        })

        # Klein framepje (crop)
        roi_frame = frame[ymin:ymax, xmin:xmax].copy()
        small_frames.append(roi_frame)
        
        
    # Initialize decoder(s) with max 5 seconds per frame
    pixel_decoder = PixelColorDecoder(num_threads=8, max_queue_size=50, max_decode_time=5.0)

    # Start decoder(s)
    pixel_decoder.start()
    
    t1 = time.perf_counter()
    # Submit frame for decoding
    for i, pixel in enumerate(small_frames):
        pixel_decoder.input_queue.put({
            "index": i,
            "frame": pixel
        })
    t2 = time.perf_counter()
    print(f"\nSubmitted {len(small_frames)} frames for decoding in {(t2 - t1)*1000:.5f} milliseconds.\n")
    
    # Retrieve results
    pixel_results = pixel_decoder.get_results()
    t3 = time.perf_counter()
    print("\n\nPixel Color Decoder Results:")
    pixel_results_sorted = dict(sorted(pixel_results.items()))
    for index, result in pixel_results_sorted.items():
        print(f"Index {index+1:>2}: {result}")

    print(f"\nRetrieved results in {(t3 - t2):.5f} seconds.\n")
    
    # Stop decoder(s)
    pixel_decoder.stop()
    
if __name__ == "__main__":
    test_decoders()