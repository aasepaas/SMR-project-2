scirpt laptop:

database mysql script:

-- 1. Maak de database aan
CREATE DATABASE IF NOT EXISTS secrid;

-- 2. Gebruik de database
USE secrid;

-- 3. Maak de tabel aan met ID als VARCHAR en BoxID
CREATE TABLE IF NOT EXISTS `premium-wallet` (
    `ID` VARCHAR(255) PRIMARY KEY,
    `BoxID` VARCHAR(255) NOT NULL,
    `status` VARCHAR(20) DEFAULT 'unhandled'
);

-- 4. Voeg voorbeeldgegevens toe
INSERT INTO `premium-wallet` (`ID`, `BoxID`)
VALUES 
('121', 'BOX1223');

-- 5. Bekijk de inhoud van de tabel
SELECT * FROM `premium-wallet`;
