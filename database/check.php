<?php
require 'database.php';

$function = $argv[1] ?? null;
$json_arg = $argv[2] ?? "{}";
$vals = json_decode($json_arg, true);
function check_boxid($vals)
{

    $boxid = $vals['boxid'];
    $db = new DatabaseConfig("localhost", "appuser", "StrongPassword123!", "test");
    $result = $db->check_box_id($boxid);
    echo json_encode(["result" => $result]);
    $db->closeConnection();
}
function final_check($vals)
{

    $boxid = $vals['boxid'];
    $id = $vals['id'];
    $db = new DatabaseConfig("localhost", "appuser", "StrongPassword123!", "test");
    $result = $db->checkID($boxid, $id);
    echo json_encode(["result" => $result]);
    $db->closeConnection();
}

if (function_exists($function)) {
    $function($vals);
} else {
    echo "Function does not exist";
}
?>