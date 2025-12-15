import cv2
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN

class DBSCANFiltering:
    def __init__(self, data, eps=20, min_samples=10) -> None:
        self.data = np.array(data)
        self.eps = eps
        self.min_samples = min_samples
        
    def get_filtered_indices(self) -> tuple[np.ndarray, np.ndarray]:
        """ 
            Geef indices terug van punten die NIET als ruis zijn gelabeld.
            
            Als op plek 3 in de originele data ruis zat, dan zal die plek
            niet in de geretourneerde indices zitten.
        """
        
        labels = self.__DBSCAN_toepassen_op_y_as()
        
        # Filter indices waar label != -1 (dus geen ruis)
        valid_indices = np.where(labels != -1)[0]
                
        return valid_indices, labels
    
    def get_filtered_data(self) -> np.ndarray:
        """ Geeft een nieuwe lijst terug met ALLEEN de 'goede' gefilterde data. """
        
        labels = self.__DBSCAN_toepassen_op_y_as()

        # filter alles behalve ruis
        mask = labels != -1
        filtered_data = self.data[mask]
        
        return filtered_data
    
    def get_filtered_data_with_indices(self) -> tuple[np.ndarray, np.ndarray]:
        """Geef zowel gefilterde data als indices terug"""
        
        filtered_indices, labels = self.get_filtered_indices()
        filtered_data = self.get_filtered_data()
    
        return filtered_data, filtered_indices 
           
    def __DBSCAN_toepassen_op_y_as(self) -> np.ndarray:
        # We pakken alleen de Y-kolom (index 1) om op te clusteren
        # .reshape(-1, 1) is nodig omdat Scikit-learn een 2D kolom verwacht
        Y_features = self.data[:, 1].reshape(-1, 1)
        
        # Start DBSCAN
        db = DBSCAN(eps=self.eps, min_samples=self.min_samples).fit(Y_features)
        
        # De labels vertellen ons bij welke groep een punt hoort.
        # Label -1 betekent: Ruis (geen groep).
        labels = db.fit_predict(Y_features)
        
        return labels
    
    def visualize_dbscan_results(self, labels, flip_y: bool = True):
        """
        Plot DBSCAN input and results.
        If `flip_y` is True the y-axis will be inverted so the plot matches image coordinate system (origin at top-left).
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        # fig.canvas.mpl_connect('key_press_event', on_key)
         
        # --- GRAFIEK 1: Beginsituatie ---
        ax1.scatter(self.data[:, 0], self.data[:, 1], c='grey', s=20, alpha=0.6)
        ax1.set_title("Begin situation: Raw Data")
        ax1.set_xlabel("X-coordinate")
        ax1.set_ylabel("Y-coordinate")
        if flip_y:
            ax1.invert_yaxis()
        ax1.grid(True, linestyle='--', alpha=0.5)
         
        # --- GRAFIEK 2: Eindsituatie (DBSCAN Resultaat) ---
        unieke_labels = np.unique(labels)
 
        # Kleurenpalet
        colors = [
            "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"  
        ]

        for k, col in zip(unieke_labels, colors):
            if k == -1:
                # Dit is de RUIS. Kleur zwart, markering 'x'.
                col = 'k'
                marker = 'x'
                label_text = "outlier (will be removed)"
                size = 60
                alpha = 1.0
            else:
                # Dit is een CLUSTER (een lijn). Geef een kleur.
                marker = 'o'
                label_text = f"Found line (Cluster {k+1})"
                size = 25
                alpha = 0.6
         
            # Selecteer de punten die bij dit label horen
            class_member_mask = (labels == k)
            xy = self.data[class_member_mask]
            # Plot deze punten
            ax2.scatter(xy[:, 0], xy[:, 1], c=[col], marker=marker, s=size, label=label_text, alpha=alpha)
         
        ax2.set_title("Final situation: After DBSCAN")
        ax2.set_xlabel("X-coordinate")
        if flip_y:
            ax2.invert_yaxis()
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.5)
         
        plt.tight_layout()
        
        return fig 
    
    @staticmethod
    def fig_to_cv2(fig):
        """ Converteer Matplotlib figuur naar OpenCV image (BGR) """
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        img = np.asarray(renderer.buffer_rgba())
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        cv2.imshow("Show DBScan Algorithm", img ) 
        
if __name__ == "__main__":
    test_data = np.array([(671, 698), (775, 687), (982, 680), (874, 679), (1087, 667), (253, 449), (148, 448), (359, 442), (460, 430), (668, 425), (560, 418), (769, 401), (989, 396), (881, 395), (1104, 379), (142, 170), (249, 148), (448, 145), (351, 137), (673, 123), (555, 120), (777, 104), (882, 91), (989, 84), (1106, 83), (556, 20)])
    
    filterer = DBSCANFiltering(data=test_data, eps=50, min_samples=3)

    gefilterd = filterer.get_filtered_data()
    print("Original data points:", len(test_data))
    print("Filtered data points:", len(gefilterd))
    # print(gefilterd)
    
    # gefilterd2 = filterer.get_filtered_indices()
    # print("Original data points:", len(alle_data))
    # print("Filtered data points:", len(gefilterd2))
    # print(gefilterd2)
