-- ---------------------------------------------------------------------------
-- Ki Tu - Stundenplaner: Datenbank anlegen
--
-- Fuer MySQL 5.7+ / MariaDB 10.2+. Einspielen wahlweise
--
--   auf der Konsole:   mysql -u root -p < datenbank/kitu.sql
--   oder in phpMyAdmin: Reiter "Importieren" -> diese Datei waehlen
--
-- Danach in php/inc/konfig.php eintragen:
--
--   'dsn'         => 'mysql:host=localhost;dbname=kitu;charset=utf8mb4',
--   'db_nutzer'   => 'kitu',
--   'db_kennwort' => '...',
--
-- Hinweis: Die Anwendung legt fehlende Tabellen auch selbst an
-- (php/inc/db.php). Diese Datei ist der empfohlene Weg - sie bringt
-- zusaetzlich InnoDB, utf8mb4 und die passenden Schluessel mit.
--
-- Zum Aufraeumen aller Daten (Konten inbegriffen!) dient ganz unten der
-- auskommentierte Abschnitt.
-- ---------------------------------------------------------------------------

-- --- Datenbank und Zugang --------------------------------------------------
-- Wer die Datenbank im Kundenmenue des Hosters anlegt, ueberspringt diesen
-- Abschnitt und faengt bei "Tabellen" an.

CREATE DATABASE IF NOT EXISTS `kitu`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Kennwort bitte ersetzen, bevor das hier laeuft.
CREATE USER IF NOT EXISTS 'kitu'@'localhost'
    IDENTIFIED BY 'bitte-hier-ein-eigenes-kennwort';

GRANT SELECT, INSERT, UPDATE, DELETE ON `kitu`.* TO 'kitu'@'localhost';
FLUSH PRIVILEGES;

USE `kitu`;

-- --- Tabellen --------------------------------------------------------------

-- Konten: ein Datensatz je Uebungsleiterin oder Uebungsleiter.
-- Der kostenlose Zugang gilt dauerhaft (abo_bis leer); nur ein gebuchtes Abo
-- hat ein Ende. Der Offline-Schluessel gehoert zu genau diesem Konto.
CREATE TABLE IF NOT EXISTS `konten` (
    `kennung`       VARCHAR(190) NOT NULL COMMENT 'E-Mail, klein geschrieben',
    `name`          VARCHAR(190) NOT NULL DEFAULT '',
    `kennwort`      VARCHAR(255) NOT NULL COMMENT 'password_hash(), nie im Klartext',
    `rolle`         VARCHAR(20)  NOT NULL DEFAULT 'nutzer' COMMENT 'nutzer, wartung, verwalter',
    `angelegt`      VARCHAR(32)  NOT NULL DEFAULT '' COMMENT 'ISO-Zeitstempel (UTC)',
    `bestaetigt`    TINYINT      NOT NULL DEFAULT 0 COMMENT 'Mailcode eingeloest?',
    `gesperrt`      TINYINT      NOT NULL DEFAULT 0,
    `abo_art`       VARCHAR(20)  NOT NULL DEFAULT 'frei' COMMENT 'frei, Probeabo, Monatsabo, Jahresabo',
    `abo_seit`      VARCHAR(10)  NOT NULL DEFAULT '',
    `abo_bis`       VARCHAR(10)  NOT NULL DEFAULT '' COMMENT 'leer = kostenlos, dauerhaft',
    `probe_zuletzt` VARCHAR(10)  NOT NULL DEFAULT '' COMMENT 'Probeabo: einmal je Jahr',
    `offline`       VARCHAR(40)  NOT NULL DEFAULT '' COMMENT 'KITU-XXXX-XXXX-XXXX-XXXX',
    PRIMARY KEY (`kennung`),
    KEY `konten_abo` (`abo_bis`),
    KEY `konten_offen` (`bestaetigt`, `angelegt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Mailcodes fuer Bestaetigung und Kennwort - je Konto hoechstens einer,
-- gespeichert als HMAC, mit Ablaufzeit und Versuchszaehler.
CREATE TABLE IF NOT EXISTS `codes` (
    `kennung`  VARCHAR(190) NOT NULL,
    `art`      VARCHAR(20)  NOT NULL DEFAULT '' COMMENT 'bestaetigung oder kennwort',
    `hash`     VARCHAR(64)  NOT NULL DEFAULT '',
    `bis`      BIGINT       NOT NULL DEFAULT 0 COMMENT 'Unixzeit',
    `versuche` INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`kennung`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fehlversuche bei Anmeldung und Codeeingabe: nach zehn Stueck in einer
-- Viertelstunde ist Ruhe. Aeltere Zeilen raeumt die Anwendung selbst weg.
CREATE TABLE IF NOT EXISTS `fehlversuche` (
    `merkmal`   VARCHAR(190) NOT NULL COMMENT 'IP-Adresse und Konto',
    `zeitpunkt` BIGINT       NOT NULL COMMENT 'Unixzeit',
    KEY `fehlversuche_merkmal` (`merkmal`, `zeitpunkt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Protokoll: Registrierung, Bestaetigung, Anmeldung, Mailversand,
-- Freischaltung und jede Verwaltungshandlung. Die letzten Zeilen zeigt
-- wartung.php.
CREATE TABLE IF NOT EXISTS `protokoll` (
    `zeitpunkt` VARCHAR(32)  NOT NULL COMMENT 'ISO-Zeitstempel (UTC)',
    `was`       VARCHAR(60)  NOT NULL,
    `wer`       VARCHAR(190) NOT NULL DEFAULT '',
    `mehr`      VARCHAR(190) NOT NULL DEFAULT '',
    KEY `protokoll_zeit` (`zeitpunkt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Danach:
--
--   php php/einrichten.php
--
-- legt die beiden Dienstkonten (Verwaltung und Wartung) an und zeigt ihre
-- Kennwoerter einmalig auf der Konsole. Das erste ueber die Webseite
-- angelegte Konto wird ebenfalls Verwalter, falls noch keines existiert.
-- ---------------------------------------------------------------------------

-- --- Aufraeumen (nur bei Bedarf, loescht alle Konten!) ----------------------
-- DROP TABLE IF EXISTS `protokoll`, `fehlversuche`, `codes`, `konten`;
