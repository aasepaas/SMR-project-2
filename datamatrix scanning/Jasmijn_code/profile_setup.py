class ScanProfile:
    """Stores focus + exposure + brightness settings for a scan target."""

    def __init__(self, name: str, data_timeout: float, total_timeout: float, scan_type: str, rois: list[tuple[int, int, int, int] | None],
                 camera_index: int = 0, focus: int | None = None, exposure: int | None = None, brightness: int | None = None, validate_n_times: int = 1, ) -> None:
        self.name = name
        self.camera_index = camera_index
                
        self.focus = focus
        self.exposure = exposure
        self.brightness = brightness
        
        self.data_timeout = data_timeout
        self.total_timeout = total_timeout
        self.scan_type = scan_type # "datamatrix" or "barcode"
        self.rois = rois
        self.validate_n_times = validate_n_times



webcam = 1
webcam_4k = 2
webcam_kiyo1 = 0

carton_box_focus = 80

# Standard profile
standard_profile = ScanProfile(
    name="Standard",
    rois=[(100, 400, 100, 400)],
    camera_index = webcam_kiyo1,
    data_timeout=0.5,
    total_timeout=10.0,
    scan_type="datamatrix",
)

# Wallet profile
# top, left = 340, 570
# bottom, right = top+120, left+120
top, left = 340, 570
bottom, right = top+60, left+60
wallet_profile = ScanProfile(
    name="Wallet",
    camera_index = webcam_kiyo1,
    focus=140,
    # exposure=-5,
    # brightness=100,
    data_timeout=0.5,
    total_timeout=10.0,
    scan_type="datamatrix",
    rois=[(top, bottom, left, right)], # top, bottom, left, right
    # rois=[(380, 380+110, 660, 660+110)], # top, bottom, left, right
    validate_n_times=1,
)

# Giftbox profile 
giftbox_profile = ScanProfile(
    name="GiftBox",
    camera_index=webcam_4k,
    rois=[],
    # focus=carton_box_focus,
    # exposure=-9, # 0 of -6! THUIS 0
    # brightness=195, # 200 of 195! THUIS 195
    # exposure=-6, # 0 of -6!
    # brightness=195, # 200 of 195!
    data_timeout=0.5,
    total_timeout = 50.0, # 1 seconden per code bij 50 codes
    scan_type="datamatrix",
    validate_n_times=3,
)

# Barcode profile
barcode_profile = ScanProfile(
    name="Barcode",
    camera_index = webcam_4k,
    focus=carton_box_focus,
    exposure=0,
    brightness=200,
    data_timeout=1.0,
    total_timeout=10.0,
    scan_type="barcode",
    rois=[(150, 300, 100, 400)], # top, bottom, left, right
)
