import cv2
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN

# Timer decorator that respects PRODUCTION_MODE
from config import create_timer_decorator
timer_func = create_timer_decorator("DBSCANFiltering")

class DBSCANFiltering:
    """
    OPTIMALISATIES:
    1. Cache DBSCAN results (grootste impact)
    2. Lazy matplotlib imports (alleen als visualisatie nodig)
    3. Vectorized operations waar mogelijk
    4. Reduced redundant fit() calls
    """
    
    def __init__(self, data, eps=20, min_samples=10) -> None:
        self.data = np.asarray(data)  # asarray is sneller dan array als data al numpy is
        self.eps = eps
        self.min_samples = min_samples
        
        # Cache voor DBSCAN resultaten
        self._labels_cache = {}  # {y_as: labels}
        self._dbscan_fitted = {}  # {y_as: DBSCAN object}
        
    @timer_func
    def get_filtered_indices(self, y_as: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Geef indices terug van punten die NIET als ruis zijn gelabeld."""
        labels = self._get_labels(y_as)
        
        # Numpy where is al geoptimaliseerd - geen verbetering nodig
        valid_indices = np.where(labels != -1)[0]
        
        return valid_indices, labels
    
    @timer_func
    def get_filtered_data(self, y_as: bool = True) -> np.ndarray:
        """ Geeft een nieuwe lijst terug met ALLEEN de 'goede' gefilterde data. """
        labels = self._get_labels(y_as)
        
        return self.data[labels != -1]
    
    @timer_func
    def get_filtered_data_with_indices(self, y_as: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Geef zowel gefilterde data als indices terug."""
        # Hergebruik get_filtered_indices om dubbel werk te voorkomen
        filtered_indices, labels = self.get_filtered_indices(y_as)
        
        # Direct indexeren is sneller dan opnieuw filteren
        filtered_data = self.data[filtered_indices]
        
        return filtered_data, filtered_indices
    
    def _get_labels(self, y_as: bool) -> np.ndarray:
        """
        Cache DBSCAN resultaten om herberekening te voorkomen.
        
        OPTIMALISATIE: Was O(n log n) elke keer, nu O(1) bij hergebruik
        """
        if y_as not in self._labels_cache:
            self._labels_cache[y_as] = self._apply_dbscan(y_as)
        
        return self._labels_cache[y_as]
    
    def _apply_dbscan(self, y_as: bool) -> np.ndarray:
        """
        Pas DBSCAN toe op gekozen as.
        
        OPTIMALISATIE: Gebruik fit_predict() in plaats van fit() + predict()
        - Was: 2x doorlopen van data
        - Nu: 1x doorlopen van data
        """
        # Select column: y (index 1) or x (index 0)
        features = self.data[:, 1 if y_as else 0].reshape(-1, 1)
        
        # fit_predict is sneller dan fit() gevolgd door predict()
        db = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = db.fit_predict(features)
        
        return labels
    
    def clear_cache(self):
        """Clear cached DBSCAN results als parameters veranderen."""
        self._labels_cache.clear()
        self._dbscan_fitted.clear()
    
    def visualize_dbscan_results(self, labels, flip_y: bool = True):
        """
        Plot DBSCAN input and results.
        If `flip_y` is True the y-axis will be inverted so the plot matches image coordinate system (origin at top-left).
        """
        # Sluit eventuele eerdere figuren
        plt.close('all')
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # --- GRAFIEK 1: Beginsituatie ---
        ax1.scatter(self.data[:, 0], self.data[:, 1], c='grey', s=20, alpha=0.6)
        ax1.set_title("Begin situation: Raw Data")
        ax1.set_xlabel("X-coordinate")
        ax1.set_ylabel("Y-coordinate")
        if flip_y:
            ax1.invert_yaxis()
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # --- GRAFIEK 2: Eindsituatie (DBSCAN Resultaat) ---
        unique_labels = np.unique(labels)
        
        # Pre-define colors (avoid repeated string concatenation)
        colors = [
            "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
        ]
        
        # OPTIMALISATIE: Plot alle clusters in één keer waar mogelijk
        outlier_mask = (labels == -1)
        if outlier_mask.any():
            xy_outliers = self.data[outlier_mask]
            ax2.scatter(xy_outliers[:, 0], xy_outliers[:, 1], 
                       c='k', marker='x', s=60, 
                       label="outlier (will be removed)", alpha=1.0)
        
        # Plot clusters
        cluster_labels = unique_labels[unique_labels != -1]
        for k in cluster_labels:
            col = colors[k % len(colors)]  # Wrap around if more clusters than colors
            class_member_mask = (labels == k)
            xy = self.data[class_member_mask]
            
            ax2.scatter(xy[:, 0], xy[:, 1], 
                       c=[col], marker='o', s=25,
                       label=f"Found line (Cluster {k+1})", 
                       alpha=0.6)
        
        ax2.set_title("Final situation: After DBSCAN")
        ax2.set_xlabel("X-coordinate")
        if flip_y:
            ax2.invert_yaxis()
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        return fig
    
    @staticmethod
    @timer_func
    def fig_to_cv2(fig):
        """
        Converteer Matplotlib figuur naar OpenCV image (BGR).
        
        OPTIMALISATIE: Direct buffer access zonder copy waar mogelijk
        """
        fig.canvas.draw()
        
        # Modern matplotlib uses buffer_rgba() instead of tostring_rgb()
        buf = np.asarray(fig.canvas.buffer_rgba())
        
        # buffer_rgba() gives RGBA, so convert to BGR for OpenCV
        img_bgr = cv2.cvtColor(buf, cv2.COLOR_RGBA2BGR)
        
        cv2.imshow("Show DBScan Algorithm", img_bgr)
                
if __name__ == "__main__":
    test_data = np.array([(671, 698), (775, 687), (982, 680), (874, 679), (1087, 667), (253, 449), (148, 448), (359, 442), (460, 430), (668, 425), (560, 418), (769, 401), (989, 396), (881, 395), (1104, 379), (142, 170), (249, 148), (448, 145), (351, 137), (673, 123), (555, 120), (777, 104), (882, 91), (989, 84), (1106, 83), (556, 20)])
    
    filterer = DBSCANFiltering(data=test_data, eps=50, min_samples=3)

    # gefilterd = filterer.get_filtered_data()
    # print("Original data points:", len(test_data))
    # print("Filtered data points:", len(gefilterd))
    
    gefilterd2, labels = filterer.get_filtered_indices(y_as=False)
    print("Original data points:", len(test_data))
    print("Filtered data points:", len(gefilterd2))
    
    fig = filterer.visualize_dbscan_results(labels)   
    while True: 
        DBSCANFiltering.fig_to_cv2(fig)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Exiting visualization...")
            break