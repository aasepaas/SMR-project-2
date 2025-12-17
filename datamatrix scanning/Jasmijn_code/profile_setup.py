class ScanProfile:
    """Stores focus + exposure + brightness settings for a scan target."""
    def __init__(self, name: str, data_timeout: float, scan_type: str, camera_index: int = 0, focus: int | None = None, exposure: int | None = None, brightness: int | None = None, rois: list[tuple[int, int, int, int]] = list(), validate_n_times: int = 1) -> None:
        self.name = name
        self.camera_index = camera_index
                
        self.focus = focus
        self.exposure = exposure
        self.brightness = brightness
        
        self.data_timeout = data_timeout
        self.scan_type = scan_type # "datamatrix" or "barcode"
        self.rois = rois
        self.validate_n_times = validate_n_times

Wallet_Camera_Index = 1
Giftbox_Camera_Index = 1
Barcode_Camera_Index = 1

carton_box_focus = 80

# Standard profile
standard_profile = ScanProfile(
    name="Standard",
    camera_index = Wallet_Camera_Index,
    data_timeout=0.5,
    scan_type="datamatrix",
)

# Wallet profile
wallet_profile = ScanProfile(
    name="Wallet",
    camera_index = Wallet_Camera_Index,
    focus=140,
    # exposure=-5,
    # brightness=100,
    data_timeout=0.5,
    scan_type="datamatrix",
    rois=[(400, 420+100, 700, 700+100)], # top, bottom, left, right
    validate_n_times=1,
)

# Giftbox profile 
giftbox_profile = ScanProfile(
    name="GiftBox",
    camera_index=Giftbox_Camera_Index,
    focus=carton_box_focus,
    exposure=-9, # 0 of -6! THUIS 0
    brightness=195, # 200 of 195! THUIS 195
    # exposure=-6, # 0 of -6!
    # brightness=195, # 200 of 195!
    data_timeout=0.5,
    scan_type="datamatrix",
    validate_n_times=3,
)

# Barcode profile
barcode_profile = ScanProfile(
    name="Barcode",
    camera_index = Barcode_Camera_Index,
    focus=carton_box_focus,
    exposure=0,
    brightness=200,
    data_timeout=1.0,
    scan_type="barcode",
    rois=[(100, 300, 200, 350)], # top, bottom, left, right
)
