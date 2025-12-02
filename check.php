<?php
require 'database.php';

$vals = json_decode($argv[1], true);
$boxid = $vals['boxid'];
$id = $vals['id'];
$db = new DatabaseConfig(DatabaseConfig::$servernaam, DatabaseConfig::$gebruikersnaam, DatabaseConfig::$wachtwoord, DatabaseConfig::$databasenaam);
$result = $db->checkID($boxid, $id);
echo $result;
$db->closeConnection();
?>
