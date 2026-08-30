-- AddressBook database schema
-- Run this once against a fresh MySQL database to set up all required tables.
-- Example: mysql -u root -p address_book < schema.sql

CREATE DATABASE IF NOT EXISTS address_book;
USE address_book;

CREATE TABLE IF NOT EXISTS users (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL UNIQUE,
    Password VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS Contacts (
    Contact_ID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Phone VARCHAR(20) NOT NULL,
    Email VARCHAR(150) NOT NULL,
    Address VARCHAR(255),
    City VARCHAR(100),
    User_ID INT NOT NULL,
    FOREIGN KEY (User_ID) REFERENCES users(ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Login_History (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    User_ID INT NOT NULL,
    Login_Time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (User_ID) REFERENCES users(ID) ON DELETE CASCADE
);
