import csvhandler

class databuffer:
    def __init__(self, coords):
        self.coords = coords
        self.ci = 0

    def collectfinalPos(self):    

        pos = self.coords.getVals(self.ci)
        
        if self.ci < len(self.coords.data_array):
            
            self.ci = self.ci + 1
            return pos
        else:
            return None
