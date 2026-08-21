<?php
/**
 * Vorlage fuer die Konfiguration.
 *
 * Kopieren nach inc/konfig.php und anpassen. Die Kopie enthaelt Zugangsdaten
 * und gehoert nicht ins Versionsverzeichnis (steht in .gitignore).
 */

return [
    // -- Datenbank ---------------------------------------------------------
    'dsn'         => 'mysql:host=localhost;dbname=kitu;charset=utf8mb4',
    'db_nutzer'   => 'kitu',
    'db_kennwort' => '',

    // -- Serverschluessel fuer die Mailcodes -------------------------------
    // Einmal wuerfeln, z. B. mit: php -r "echo bin2hex(random_bytes(32));"
    'geheim'      => 'bitte-hier-einen-zufallswert-eintragen',

    // -- Adresse dieser Installation (fuer die Verweise in den Mails) ------
    'adresse'     => 'https://kitu.mein-verein.de',

    // -- Mailversand -------------------------------------------------------
    // 'mail'  = ueber die PHP-Funktion mail()
    // 'datei' = als Textdatei in daten/postfach (zum Ausprobieren und Testen)
    'mail'        => 'mail',
    'absender'    => 'Ki Tu - Stundenplaner <kitu@mein-verein.de>',

    // -- Pfade -------------------------------------------------------------
    // Die verschluesselte Anwendung liegt bewusst ausserhalb des
    // DocumentRoot: Nur PHP gibt sie heraus, nie der Webserver direkt.
    'daten'       => __DIR__ . '/../daten',
    'anwendung'   => __DIR__ . '/../../web/kinderturnen.html',
    'lizenzen'    => __DIR__ . '/../../web/lizenzen.json',

    // -- Betrieb -----------------------------------------------------------
    'https'       => true,   // Sitzungs-Cookie als "Secure" markieren
];
