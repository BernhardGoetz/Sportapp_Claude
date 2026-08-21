<?php
/**
 * Datenbank: Verbindung und Schema.
 *
 * Gedacht ist MySQL/MariaDB; das Schema ist aber bewusst schlicht gehalten
 * (Textspalten, kennung als Schluessel, kein AUTO_INCREMENT), damit es auch
 * ueber PDO/SQLite laeuft - so kommen die Tests ohne Datenbankserver aus.
 */

declare(strict_types=1);

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    $konfig = konfig();
    $pdo = new PDO(
        $konfig['dsn'],
        $konfig['db_nutzer'] ?? null,
        $konfig['db_kennwort'] ?? null,
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]
    );
    schema_anlegen($pdo);
    return $pdo;
}

/** Legt die Tabellen an, falls sie fehlen - schadet sonst nicht. */
function schema_anlegen(PDO $pdo): void
{
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS konten (
            kennung       VARCHAR(190) NOT NULL,
            name          VARCHAR(190) NOT NULL DEFAULT \'\',
            kennwort      VARCHAR(255) NOT NULL,
            rolle         VARCHAR(20)  NOT NULL DEFAULT \'nutzer\',
            angelegt      VARCHAR(32)  NOT NULL DEFAULT \'\',
            bestaetigt    INTEGER      NOT NULL DEFAULT 0,
            gesperrt      INTEGER      NOT NULL DEFAULT 0,
            abo_art       VARCHAR(20)  NOT NULL DEFAULT \'frei\',
            abo_seit      VARCHAR(10)  NOT NULL DEFAULT \'\',
            abo_bis       VARCHAR(10)  NOT NULL DEFAULT \'\',
            probe_zuletzt VARCHAR(10)  NOT NULL DEFAULT \'\',
            offline       VARCHAR(40)  NOT NULL DEFAULT \'\',
            PRIMARY KEY (kennung)
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS codes (
            kennung  VARCHAR(190) NOT NULL,
            art      VARCHAR(20)  NOT NULL DEFAULT \'\',
            hash     VARCHAR(64)  NOT NULL DEFAULT \'\',
            bis      INTEGER      NOT NULL DEFAULT 0,
            versuche INTEGER      NOT NULL DEFAULT 0,
            PRIMARY KEY (kennung)
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS fehlversuche (
            merkmal   VARCHAR(190) NOT NULL,
            zeitpunkt INTEGER      NOT NULL
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS protokoll (
            zeitpunkt VARCHAR(32)  NOT NULL,
            was       VARCHAR(60)  NOT NULL,
            wer       VARCHAR(190) NOT NULL DEFAULT \'\',
            mehr      VARCHAR(190) NOT NULL DEFAULT \'\'
        )'
    );
}

/** Eine Zeile holen - oder null. */
function db_zeile(string $sql, array $werte = []): ?array
{
    $abfrage = db()->prepare($sql);
    $abfrage->execute($werte);
    $zeile = $abfrage->fetch();
    return $zeile === false ? null : $zeile;
}

/** Alle Zeilen holen. */
function db_zeilen(string $sql, array $werte = []): array
{
    $abfrage = db()->prepare($sql);
    $abfrage->execute($werte);
    return $abfrage->fetchAll();
}

/** Schreiben; gibt die Zahl der betroffenen Zeilen zurueck. */
function db_tue(string $sql, array $werte = []): int
{
    $abfrage = db()->prepare($sql);
    $abfrage->execute($werte);
    return $abfrage->rowCount();
}

/** Eine einzelne Zahl abfragen. */
function db_zahl(string $sql, array $werte = []): int
{
    $abfrage = db()->prepare($sql);
    $abfrage->execute($werte);
    return (int) $abfrage->fetchColumn();
}

/** Zeile fuers Protokoll. */
function notiere(string $was, string $wer = '', string $mehr = ''): void
{
    db_tue(
        'INSERT INTO protokoll (zeitpunkt, was, wer, mehr) VALUES (?, ?, ?, ?)',
        [zeitstempel(), $was, mb_substr($wer, 0, 190), mb_substr($mehr, 0, 190)]
    );
}
