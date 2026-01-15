import csv
import os

class CSVHandler():
    def __init__(self):
        self.data = None
        self.data_array = []
        self.currentWalletFilepath = None
        self.currentGiftboxFilepath = None
        self.chosenWallet = None
        self.chosenGiftbox = None
        pass

    def read_csv(self, filepath):
        """Reads a CSV file and returns its content as a list of dictionaries."""
        if filepath:
            with open(filepath, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                data = [row for row in reader]
            return data
        return None

    def selectwallettype(self, identifier):
        wallet_types = {
            '1': 'wallets.csv',
            '2': 'wallets.csv',
            '3': 'wallets.csv'}
        self.chosenWallet = wallet_types.get(identifier, 'wallets.csv')
        self.setfilepath(True)

    def selectgiftboxtype(self, identifier):
        giftbox_types = {
            '1': 'giftbox.csv',
            '2': 'giftbox.csv',
            '3': 'giftbox.csv'}
        self.chosenGiftbox = giftbox_types.get(identifier, 'giftbox.csv')
        self.setfilepath(False)

    def setfilepath(self, indicatorWallterOrGiftbox):
        dirpath = r"C:\Users\aashi\Downloads"
        if indicatorWallterOrGiftbox:
            filepath = str(dirpath + "\\" + self.chosenWallet)
            self.currentWalletFilepath = filepath
        else:
            filepath = str(dirpath + "\\" + self.chosenGiftbox)
            self.currentGiftboxFilepath = filepath
        return filepath

    '''def formatdata(self, indicatorWallterOrGiftbox):
        
        if indicatorWallterOrGiftbox:
            filepath = self.currentWalletFilepath
        else:
            filepath = self.currentGiftboxFilepath
        data = self.read_csv(filepath)
        result = []
        if  len(data) < 50:
            return False
        else:
            for row in data:
                if row[0] == '':
                    continue
                siggie, x, y, z, rx, ry, rz = float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[6])
                coordstosend = [siggie, x, y, z, rx, ry, rz]
                #self.data_array.append(coordstosend)
                result.append(coordstosend)



        return self.data_array'''
    def formatdata(self, indicatorWallterOrGiftbox):
        if indicatorWallterOrGiftbox:
            filepath = self.currentWalletFilepath
        else:
            filepath = self.currentGiftboxFilepath

        data = self.read_csv(filepath)
        if len(data) < 50:
            return False

        result = []   

        for row in data:
            if row[0] == '':
                continue

            siggie, x, y, z, rx, ry, rz = (
                float(row[0]), float(row[1]), float(row[2]),
                float(row[3]), float(row[4]), float(row[5]), float(row[6])
            )

            coordstosend = [siggie, x, y, z, rx, ry, rz]
            result.append(coordstosend)

        return result



   