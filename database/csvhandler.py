import csv
import os

class CSVHandler():
    def __init__(self, file_path):
        self.data = None
        self.data_array = []
        pass

    def read_csv(self, filepath):
        """Reads a CSV file and returns its content as a list of dictionaries."""
        if filepath:
            with open(filepath, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.Reader(csvfile)
                data = [row for row in reader]
            return data
        return None

    def selectwallettype(self, identifier):
        wallet_types = {
            '1': 'personal_wallets.csv',
            '2': 'business_wallets.csv',
            '3': 'savings_wallets.csv'}
        return wallet_types.get(identifier, 'personal_wallets.csv')

    def getfilepath(self, wallettype):

        dirpath = r"C:\Users\basti\Documents\csvwallets"
        findfiles = os.listdir(dirpath)
        filepath = str(dirpath + "\\" + wallettype)
        return filepath

    def formatdata(self):
        filepath = self.getfilepath
        self.data = self.read_csv(filepath)
        if  len(self.data) < 50:
            return False
        else:
            for row in self.data:
                if row[0] == '':
                    continue

                siggie, x, y, z, rx, ry, rz = float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[6])
                coordstosend = [siggie, x, y, z, rx, ry, rz]
                self.data_array.append(coordstosend)


   