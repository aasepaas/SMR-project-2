class ScanProfile:
    """Stores focus + exposure + brightness settings for a scan target."""
    def __init__(self, name: str, data_timeout: float, scan_type: str, camera_index: int = 0, focus: int | None = None, exposure: int | None = None, brightness: int | None = None, rois: list[tuple[int, int, int, int]] = list()) -> None:
        self.name = name
        self.camera_index = camera_index
                
        self.focus = focus
        self.exposure = exposure
        self.brightness = brightness
        
        self.data_timeout = data_timeout
        self.scan_type = scan_type # "datamatrix" or "barcode"
        self.rois = rois

Wallet_Camera_Index = 0
Giftbox_Camera_Index = 1
Barcode_Camera_Index = 1

carton_box_focus = 85

# Standard profile
standard_profile = ScanProfile(
    name="Standard",
    data_timeout=0.5,
    scan_type="datamatrix",
)

# Wallet profile
wallet_profile = ScanProfile(
    name="Wallet",
    camera_index = Wallet_Camera_Index,
    focus=175,
    exposure=-5,
    brightness=100,
    data_timeout=0.5,
    scan_type="datamatrix",
    rois=[(0, 200, 100, 300)] # top, bottom, left, right
)

# Giftbox profile 
giftbox_profile = ScanProfile(
    name="GiftBox",
    camera_index=Giftbox_Camera_Index,
    focus=carton_box_focus,
    exposure=-6, # 0 of -6! THUIS 0
    brightness=195, # 200 of 195! THUIS 195
    # exposure=-6, # 0 of -6!
    # brightness=195, # 200 of 195!
    data_timeout=0.5,
    scan_type="datamatrix"
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
    rois=[(100, 300, 200, 350)] # top, bottom, left, right
)
