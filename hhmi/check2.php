<?php
require 'database.php';

$vals = json_decode($argv[1], true);
$boxid = $vals['boxid'];
$id = $vals['id'];
$db = new DatabaseConfig("192.168.1.105", "appuser", "StrongPassword123!", "test");
$result = $db->checkID($boxid, $id);
echo json_encode(["result" => $result]);
$db->closeConnection();
?>