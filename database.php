<?php

class DatabaseConfig
{

    public static $servernaam = "localhost";
    public static $gebruikersnaam = "root";
    public static $wachtwoord = "your_password";
    public static $databasenaam = "your_database";

    public $iterator = 0;
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
    public function checkID($protectorID)
    {
        $dbid = $this->getID("protectors");
        if (!$dbid == null) {
            if ($protectorID == $dbid) {
                return true;
            } else {
                return false;
            }
        } else {
            return false;
        }

    }
    public function getID($table)
    {
        $sqlq = $this->conn->prepare("SELECT NUMBÈR, ID FROM $table WHERE NUMBER = ?");

        $sqlq->bind_param("i", $this->iterator);
        $sqlq->execute();
        $result = $sqlq->get_result();
        if ($result->num_rows > 0) {
            while ($row = $result->fetch_assoc()) {
                return $row["ID"];
            }
        } else {
            return null;
        }
    }
}
   ?>