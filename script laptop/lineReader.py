class LineReader:
    #####geef het bestandsnaam mee die geopend moet worden
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = open(filepath, 'r', encoding='utf-8')
        self.current_line_number = 0
    ####geeft de volgende line terug van het bestand als het er is anders none
    def get_next_line(self):
        line = self.file.readline()
        if not line:  # EOF
            return None
        self.current_line_number += 1
        return line.rstrip("\n")

    ###reset misschien handig als we door blijven loopen in een while ofzo
    def reset(self):
        self.file.seek(0)
        self.current_line_number = 0

    ###sluit het bestand
    def close(self):
        self.file.close()
