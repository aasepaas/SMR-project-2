import mysql.connector

class Database:
    def __init__(self, server, user, password, database):
        self.server = server
        self.user = user
        self.password = password
        self.database = database
        self.conn = self.connect()

    def connect(self):
        return mysql.connector.connect(
            host=self.server,
            user=self.user,
            password=self.password,
            database=self.database
        )

    def determine_matching_id(self, boxid):
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM `premium-wallet` WHERE `BoxID` = %s", (boxid,))
        row = cursor.fetchone()
        return row["ID"] if row else None

    def check_id(self, boxid, id_value):
        dbid = self.determine_matching_id(boxid)
        return dbid == id_value

    def update_status(self, boxid, new_status):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE `premium-wallet` SET status = %s WHERE BoxID = %s", (new_status, boxid))
        self.conn.commit()

    def close_connection(self):
        self.conn.close()
