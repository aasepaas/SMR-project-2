from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from mainwindow import mainWindow
import time
from threading import Event
import sys

from csvhandler import CSVHandler

from scanner import *
from databaserun import DatabaseRun
from NetworkClient import Network_client
import threading
from state_enum import state_enum
import time
from statuscontrol import StatusControl
from SMN import (
    Event as SMNEvent,
    CMD_TO_STATE,
    SMNState
)

from multiprocessing import Process, Queue

from feed import LiveFeed, VideoFeed
from camera_scanner import CameraScanner
from decoders import DataMatrixDecoder, BarcodeDecoder
from roi_auto_detector import ROIAutoDetector
#from profile_setup import wallet_profile, giftbox_profile, barcode_profile

# Initialize environment and logging before importing modules that use cv2/matplotlib
from logging_config import init_environment, set_up_logger
init_environment()
set_up_logger()
from decoders_zxingcpp import DataMatrixDecoder as DataMatrixDecoder


from worker import Worker
from profile_setup import standard_profile, wallet_profile, giftbox_profile




def main():
    database = DatabaseRun()
    csvReader = CSVHandler()
    status = StatusControl()
    # Verhoogd naar 8 threads voor 50 ROI's parallelle verwerking
    #matrix_decoder = DataMatrixDecoder(use_threads=True, num_threads=16)
    #barcode_decoder = BarcodeDecoder(num_threads=8, max_queue_size=100)    
    #roi_detector = ROIAutoDetector(expected_n_rois=50, DEBUG=True, DEBUGPROCESS=False)

    # feed_list = [
    #         LiveFeed("kiyo", True, 0),
    #         LiveFeed("4k", False, 1),
    #         LiveFeed("webcam", False, 2)
    #         # LiveFeed("Kiyo", True, 0),
    #         # LiveFeed("Webcam", False, 0),
    #         # LiveFeed("4K", False, 0)


    #         # dummy video om code te laten werken met wisselen profiel
    #         # VideoFeed("Recorded Video (Camera 4K Webcam)", False, "Jasmijn_code/videos/recorded_output3.avi", loop=True),
    #         # VideoFeed("1Recorded Video (Camera Kiyo)", True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi", loop=True),
    
    #         # scannen van 50 giftboxes
    #         # LiveFeed("Camera 4K Webcam", False, giftbox_profile.camera_index),
    #         # VideoFeed("Recorded Video (Camera 4K Webcam)", False, "Jasmijn_code/videos/testrecord_4kV4.avi", loop=True),
    #         # VideoFeed("Recorded Video (Camera 4K Webcam)", False, "Jasmijn_code/videos/test_mjpg_1.avi", loop=True), # deze
    #         # VideoFeed("Recorded Video (Camera 4K Webcam)", False, "Jasmijn_code/videos/test_raw.avi", loop=True),
            
    #         # scannen van 1 wallet per keer
    #         # VideoFeed("Recorded Video (Camera Original)", True, "Jasmijn_code/videos/record_of_wallets_Kiyo_30secV6.avi", loop=True),
    #         # LiveFeed("Camera Kiyo", True, 2), 
    #         # VideoFeed("2Recorded Video (Camera Kiyo)", True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi", loop=True),
    # ]    
    # scanner = CameraScanner(matrix_decoder, roi_detector, feed_list, debug = True)
    
    profiles = [ 
    #   Profile_instance | use_live_flag | first_active_flag | loop_flag | video_path               
        (standard_profile, True, True,  True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi"),
        (giftbox_profile,  True, False, True, "Jasmijn_code/videos/test_mjpg_1.avi"), 
        (wallet_profile,   True, False, True, "Jasmijn_code/videos/wallet_test_mjpg_1.avi"), 
    ]

    Feeds = []    
    for profile_instance, use_live_flag, first_active_flag, loop_flag, video_path in profiles:
        if use_live_flag:
            print(f"Using LIVE feed for profile '{profile_instance.name}' (Camera index {profile_instance.camera_index})")
            Feeds.append(LiveFeed(f"Camera {profile_instance.name}", first_active_flag, profile_instance.camera_index))
        else:
            print(f"Using RECORDED VIDEO for profile '{profile_instance.name}' (Camera index {profile_instance.camera_index}) from file: {video_path}")
            Feeds.append(VideoFeed(f"Recorded Video {profile_instance.name}", first_active_flag, video_path, profile_instance.camera_index, loop=loop_flag))
    
    feed_list = sorted(Feeds, key=lambda f: f.camera_index)
    print("Sorting feed_list in order of ascending camera index:")
    for feed in feed_list:
        print(f" - {feed.name} (Camera index {feed.camera_index})")
    
    # Set up decoder and ROI detector
    matrix_decoder = DataMatrixDecoder(use_threads=True, num_threads=16)
    roi_detector = ROIAutoDetector(
        expected_n_rois=50,
        threadhold_value=182,
        scaling_factor=2,
    )

    scanner = CameraScanner(matrix_decoder, roi_detector, feed_list, debug = True)


    global window
    app = QApplication(sys.argv)

    window = mainWindow()
    window.show()
    window.showFullScreen()

    # shared events
    error_event = Event()
    start_event = Event()
    scan_event = Event()
    done_event = Event()
    window.page2.set_done_event(done_event)

    client_socket = Network_client('192.168.0.101', 12344)  #('127.0.0.1', 12344)#('192.168.0.101', 12344)
    client_socket.strt_socket()

    # Thread aanmaken
    thread = QThread()
    worker = Worker(error_event, start_event, scan_event, done_event, client_socket, scanner, window, csvReader, database, status)
    worker.moveToThread(thread)

    # geef event ook door aan page2 zodat page2 het kan set/clear
    window.page2.set_error_event(error_event)

    # SIGNALS verbinden met GUI-functies
    worker.update_status.connect(window.page1.update_status)
    worker.update_box_status.connect(window.page2.update_wallet_status)

    # Wanneer scan klaar is: als resultaat True -> enable Start knop; altijd heractiveer Start Scan knop
    def handle_scan_result(ok: bool):
        window.page1.startScanButton.setEnabled(True)
        window.page1.startButton.setEnabled(ok)
        if ok:
            window.page1.update_status("Scan OK. Druk Start om te beginnen.")
        else:
            window.page1.update_status("Scan failed. Probeer opnieuw.")

    def handle_startScan_result(ok: bool):
        #window.page1.enable_start()
        window.page1.enable_startScan()
        window.page1.update_status("Robot verbonden. Druk Start Scan om de producten te scannen")

    '''def showError(tekst1, tekst2):
        window.page2.errorwindow(tekst1, tekst2)'''

    worker.showErrorWindow.connect(window.page2.errorwindow)

    worker.scan_finished.connect(handle_scan_result)
    worker.startScan.connect(handle_startScan_result)

    # verbind start_clicked naar lambda die start_event.set() doet (GUI-thread)
    window.page1.start_clicked.connect(lambda: start_event.set())
    # vervolgens de page-switch (ook in de GUI-thread)
    window.page1.start_clicked.connect(window.switch_to_page2)

    # verbind scan_requested naar een trigger die de knop tijdelijk disable't en de scan_event zet
    def trigger_scan():
        window.page1.startScanButton.setEnabled(False)
        window.page1.update_status("Status: Scannen...")
        scan_event.set()

    window.page1.scan_requested.connect(trigger_scan)

    def on_restart_requested():
        print("Main: restart requested — closing network sockets to unblock worker")
        worker.restart_triggered()
 

    # worker restart
    window.page2.restart_requested.connect(on_restart_requested)

    # START THREAD NU DIRECT zodat worker reageert op Start Scan ook op Page1
    thread.started.connect(worker.run)
    thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()