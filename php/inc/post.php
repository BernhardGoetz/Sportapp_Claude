<?php
/**
 * Mailtexte und Versand.
 *
 * Zwei Faelle brauchen Post: die **Bestaetigung** einer neuen Registrierung
 * und das **Zuruecksetzen des Kennworts**. Beide laufen ueber einen
 * sechsstelligen Code, der eine halbe Stunde gilt.
 *
 * Versandwege (in der Konfiguration unter 'mail'):
 *   'mail'  - ueber die PHP-Funktion mail()
 *   'datei' - als Textdatei in daten/postfach (zum Ausprobieren und Testen)
 */

declare(strict_types=1);

const CODE_MINUTEN = 30;
const CODEDAUER    = CODE_MINUTEN * 60;
const GRUSS        = "Viele Gruesse\nKi Tu - Stundenplaner fuer das Kinderturnen";

function anrede(string $name): string
{
    $name = trim($name);
    return $name !== '' ? "Hallo $name," : 'Hallo,';
}

/** 123456 -> "123 456" - so liest es sich vom Bildschirm ab. */
function code_gruppiert(string $code): string
{
    return strlen($code) === 6 ? substr($code, 0, 3) . ' ' . substr($code, 3) : $code;
}

/** [Betreff, Text] fuer die Bestaetigung einer neuen Registrierung. */
function text_bestaetigung(string $name, string $code, string $adresse = ''): array
{
    $verweis = $adresse !== ''
        ? "\n" . rtrim($adresse, '/') . '/bestaetigen.php'
        : ' auf der Bestaetigungsseite.';
    $text = anrede($name) . "\n\n"
        . "schoen, dass du beim Ki-Tu-Stundenplaner dabei bist. Mit diesem Code\n"
        . "schaltest du dein Konto frei:\n\n"
        . '    ' . code_gruppiert($code) . "\n\n"
        . 'Der Code gilt ' . CODE_MINUTEN . " Minuten. Gib ihn auf der Seite ein, die nach der\n"
        . "Registrierung offen ist - oder hier:" . $verweis . "\n\n"
        . "Danach kann es losgehen: Ort und Gruppe waehlen, planen, Stundenbild als PDF\n"
        . "speichern.\n\n"
        . "Hast du dich nicht registriert? Dann ist diese Mail hinfaellig - ohne den\n"
        . "Code passiert nichts, und das Konto verfaellt von selbst.\n\n"
        . GRUSS . "\n";
    return ['Dein Bestaetigungscode fuer den Ki-Tu-Stundenplaner', $text];
}

/** [Betreff, Text] fuer ein vergessenes Kennwort. */
function text_kennwort(string $name, string $code, string $adresse = ''): array
{
    $verweis = $adresse !== ''
        ? "\n" . rtrim($adresse, '/') . '/kennwort-neu.php'
        : " auf der Seite 'Kennwort neu'.";
    $text = anrede($name) . "\n\n"
        . "du moechtest dein Kennwort fuer den Ki-Tu-Stundenplaner neu setzen. Dieser\n"
        . "Code macht den Weg frei:\n\n"
        . '    ' . code_gruppiert($code) . "\n\n"
        . 'Der Code gilt ' . CODE_MINUTEN . " Minuten und laesst sich nur einmal verwenden.\n"
        . "Gib ihn zusammen mit deinem neuen Kennwort hier ein:" . $verweis . "\n\n"
        . "Kam die Anfrage nicht von dir? Dann ignoriere diese Mail einfach - dein\n"
        . "bisheriges Kennwort bleibt unveraendert gueltig.\n\n"
        . GRUSS . "\n";
    return ['Neues Kennwort fuer den Ki-Tu-Stundenplaner', $text];
}

/** Verschickt die Mail - oder legt sie ins Postfach. */
function mail_senden(string $an, string $betreff, string $text): bool
{
    $konfig = konfig();
    $absender = $konfig['absender'] ?? 'Ki Tu <kitu@localhost>';

    if (($konfig['mail'] ?? 'mail') === 'datei') {
        $ordner = $konfig['daten'] . '/postfach';
        if (!is_dir($ordner)) {
            mkdir($ordner, 0770, true);
        }
        // Der Name muss streng aufsteigen, damit "die letzte Mail" eindeutig ist.
        $zeit = microtime(true);
        $name = gmdate('Ymd-His', (int) $zeit)
            . sprintf('-%06d', (int) round(($zeit - floor($zeit)) * 1000000))
            . '_' . preg_replace('/[^a-z0-9._-]+/', '_', mb_strtolower($an)) . '.txt';
        file_put_contents(
            $ordner . '/' . $name,
            "An: $an\nVon: $absender\nBetreff: $betreff\n\n$text"
        );
        return true;
    }

    $kopf = "From: $absender\r\n"
        . "Content-Type: text/plain; charset=utf-8\r\n"
        . "Content-Transfer-Encoding: 8bit\r\n";
    return mail($an, $betreff, $text, $kopf);
}

/** Der sechsstellige Code aus einem Mailtext - fuer Tests und Fehlersuche. */
function code_aus_text(string $text): string
{
    return preg_match('/^ {2,}(\d{3}) (\d{3})\s*$/m', $text, $treffer)
        ? $treffer[1] . $treffer[2]
        : '';
}
