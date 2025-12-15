from multiprocessing import Process, Queue
from pylibdmtx.pylibdmtx import decode as dm_decoder
from pylibdmtx.pylibdmtx import Decoded

import logging
import datetime
# ====================== Microsecond-safe logging ======================
class MicrosecondFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.datetime.fromtimestamp(record.created)
        return ct.strftime("%H:%M:%S.%f") 

# Library modules should not configure handlers at import time.
# Use a module-level logger and let the application configure handlers.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# =====================================================================
#  Data-Matrix Decoder Class
# =====================================================================
class DataMatrixDecoder:
    def __init__(self, processor: Process, input_queue: Queue, result_queue: Queue) -> None:
        self.input_queue = input_queue
        self.result_queue = result_queue
        self.proc = processor
        # Process(target=self.worker)
        self.proc.start()
        
    def __del__ (self) -> None:
        self.stop()

    @staticmethod
    def worker(input_queue: Queue, result_queue: Queue) -> None:
        while True:
            if input_queue.empty():
                continue

            frame = input_queue.get(timeout=0.1)
                        
            if result_queue.empty():
                try:
                    results = dm_decoder(frame)
                    result_queue.put(results[0] if results else None)
                except Exception as e:
                    logger.error(f"Decoder error: {e}")
                    result_queue.put(None)

    def dm_decoder_async(self, frame) -> None:
        if self.input_queue.empty():
            try:
                self.input_queue.put(frame, timeout=0.01)
            except Exception:
                pass

    def get_result(self) -> Decoded | None:
        if not self.result_queue.empty():
            try:
                return self.result_queue.get_nowait()
            except Exception:
                return None

    def flush_results(self) -> None:
        """Clear any pending results from the queue."""
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except Exception:
                break

    def flush_input(self) -> None:
        """Clear any pending input frames from the queue."""
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except Exception:
                break

    def stop(self) -> None:
        try:
            self.input_queue.put_nowait(None)
        except Exception:
            pass

        proc = self.proc
        proc.join(timeout=1.0)

        if proc.is_alive():
            proc.terminate()


