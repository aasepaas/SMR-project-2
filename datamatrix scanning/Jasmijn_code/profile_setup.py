class ScanProfile:
    """Stores focus + exposure + brightness settings for a scan target."""

    def __init__(self, name: str, data_timeout: float, total_timeout: float, scan_type: str, rois: dict[int, tuple[int, int, int, int] | None],
                 camera_index: int = 0, focus: int | None = None, exposure: int | None = None, brightness: int | None = None ) -> None:
        self.name = name
        self.camera_index = camera_index
                
        self.focus = focus
        self.exposure = exposure
        self.brightness = brightness
        
        self.scan_type = scan_type
        self.rois: dict = rois
        self.data_timeout = data_timeout
        self.total_timeout = total_timeout

# Camera indices and focus settings for webcams
webcam = 1
webcam_4k = 2
webcam_kiyo = 0

webcam_kiyo_focus = 186

# Standard profile
standard_profile = ScanProfile(
    name="Standard (Laptop)",
    rois={},
    camera_index = webcam,
    data_timeout=0.5,
    total_timeout=0.5,
    scan_type="datamatrix",
)

# Wallet profile
width = 55-20+200
height = 45-20+200
# middentp, middenlr = 355-10+5, 950-10-10
middentp, middenlr = 685+20, 950-240
top, left = middentp-height, middenlr-width
bottom, right = middentp+height, middenlr+width
roi_dict = {}

for idx in range(50):
    roi_dict[idx+1] = (top, bottom, left, right)
    
wallet_profile = ScanProfile(
    name="Wallet (Kiyo)",
    camera_index = webcam_kiyo,
    focus=webcam_kiyo_focus,
    # exposure=-5,
    # brightness=100,
    data_timeout=10.0,
    total_timeout=5,
    scan_type="datamatrix",
    rois={1: (top, bottom, left, right)}, # top, bottom, left, right
    # rois= roi_dict, # top, bottom, left, right
)

# Giftbox profile 
giftbox_profile = ScanProfile(
    name="GiftBox (4K Webcam)",
    camera_index=webcam_4k,
    rois={},
    data_timeout=10.0,
    total_timeout = 15.0, 
    scan_type="datamatrix",
)
