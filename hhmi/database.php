<?php

class DatabaseConfig
{

    #public $servernaam = "192.168.1.105";
   #public $gebruikersnaam = "root";
    #public $wachtwoord = "your_password";
   #public $databasenaam = "your_database";'''

     public $servernaam = "127.0.0.1";
    public $gebruikersnaam = "aashish_de_furry";
    public $wachtwoord = "gekkedelftenaar";
    public $databasenaam = "test";

    public $iterator = 1;
    public $conn;

    function __construct($server, $gebr, $ww, $db)
    {
        $this->servernaam = $server;
        $this->gebruikersnaam = $gebr;
        $this->wachtwoord = (string) $ww;
        $this->databasenaam = $db;
        $this->conn = $this->connect($server, $gebr, $ww, $db);
    }



    function connect($server, $gebruikersnaam, $wachtwoord, $db)
    {
        $conn = new mysqli($server, $gebruikersnaam, (string) $wachtwoord, $db);
        if ($conn->connect_error) {
            die("Connection failed: " . $conn->connect_error);
        }

        return $conn;
    }

    public function insert_values($boxid, $id, $number)
    {
        $sqlq = $this->conn->prepare("INSERT INTO `premium-wallet` (`Number`, `BoxID`, `ID`) VALUES (?, ?, ?)");
        $sqlq->bind_param("ssi", $boxid, $id, $number);
        #$sqlq->bind_param("iss", $number, $boxid, $id);
        $sqlq->execute();
        $checkinsert = $sqlq->affected_rows;
        if ($checkinsert) {
            echo "values $boxid and $id inserted successfully.";
        } else {
            echo "Error inserting values: " . $this->conn->error;
        }
    }


    public function determineMatchingId($boxid)
    {
        $sqlq = $this->conn->prepare("SELECT * FROM `premium-wallet` WHERE `BoxID` = ?");
        $sqlq->bind_param("s", $boxid);
        $sqlq->execute();
        $result = $sqlq->get_result();
        if ($result->num_rows > 0) {
            if ($row = $result->fetch_assoc()) {
                return $row["ID"];
            }
        } else {
            return null;
        }
    }

    public function check_box_id($boxid)
    {
        $sqlq = $this->conn->prepare("SELECT * FROM `premium-wallet` WHERE `BoxID` = ?");
        $sqlq->bind_param("s", $boxid);
        $sqlq->execute();
        $result = $sqlq->get_result();
        if ($result->num_rows > 0) {
            return true;
        } else {
            return false;
        }
    }

    public function checkID($boxid, $id)
    {
        $dbid = $this->determineMatchingId($boxid);
        if ($dbid != $id) {
            $sqlq = $this->conn->prepare("UPDATE 'premium-wallet' SET 'Succesful_Match' = 'False' WHERE 'BoxID' = ? ");
            $sqlq->bind_param("s", $boxid);
            $sqlq->execute();
            return false;
        } else {
            $sqlq = $this->conn->prepare("UPDATE `premium-wallet` SET `Succesful_Match` = 'True' WHERE `BoxID` = ? ");
            $sqlq->bind_param("s", $boxid);
            $sqlq->execute();
            return true;
        }


    }
    public function closeConnection()
    {
        $this->conn->close();
    }

}

?>