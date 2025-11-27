<?php

class DatabaseConfig
{

    public static $servernaam = "localhost";
    public static $gebruikersnaam = "root";
    public static $wachtwoord = "your_password";
    public static $databasenaam = "your_database";

    public $iterator = 1;
    public $conn;

    function __construct($server, $gebr, $ww, $db)
    {
        $this->servernaam = $server;
        $this->gebruikersnaam = $gebr;
        $this->wachtwoord = $ww;
        $this->databasenaam = $db;
        $this->conn = $this->connect($server, $gebr, $ww, $db);
    }



    function connect($server, $gebruikersnaam, $wachtwoord, $db)
    {
        $conn = new mysqli($server, $gebruikersnaam, $wachtwoord, $db);
        if ($conn->connect_error) {
            die("Connection failed: " . $conn->connect_error);
        }
        return $conn;
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
    public function checkID($boxid, $id)
    {
        $dbid = $this->determineMatchingId($boxid);
        if ($dbid == null) {
            return false;
        } elseif ($dbid == $id) {
            return true;
        } else {
            return false;
        }
        


    }
    public function closeConnection()
    {
        $this->conn->close();
    }

}

   ?>
