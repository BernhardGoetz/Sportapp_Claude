<?php
/**
 * Einrichtung auf der Kommandozeile - nicht ueber den Browser aufrufbar.
 *
 *   php einrichten.php                     Schema anlegen, Dienstkonten anlegen
 *   php einrichten.php mail@x.de wartung   einzelnes Konto mit Rolle anlegen
 *
 * Die Adressen der Dienstkonten kommen aus den Umgebungsvariablen
 * KITU_VERWALTER und KITU_WARTUNG, sonst heissen sie verwaltung@kitu.local
 * und wartung@kitu.local. Die Kennwoerter werden gewuerfelt und erscheinen
 * genau einmal - hier auf der Konsole.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Diese Datei laeuft nur auf der Kommandozeile.\n");
}

require __DIR__ . '/inc/start.php';

function zeige_zugang(array $konto, string $kennwort): void
{
    printf("  %-10s %s\n", $konto['rolle'], $konto['kennung']);
    printf("  %-10s %s\n\n", 'Kennwort',
        $kennwort !== '' ? $kennwort : '(unveraendert - Konto gab es schon)');
}

db();  // legt das Schema an, falls es fehlt
echo "Datenbank steht.\n\n";

if ($argc > 1) {
    $kennung = $argv[1];
    $rolle = $argv[2] ?? 'nutzer';
    if (!in_array($rolle, ROLLEN, true)) {
        exit("Unbekannte Rolle: $rolle (moeglich: " . implode(', ', ROLLEN) . ")\n");
    }
    [$konto, $kennwort] = dienstkonto($kennung, $argv[3] ?? $kennung, $rolle);
    zeige_zugang($konto, $kennwort);
    exit(0);
}

echo "Zwei Dienstkonten - Kennwoerter bitte gleich notieren, sie stehen nirgends sonst:\n\n";
foreach ([
    [getenv('KITU_VERWALTER') ?: 'verwaltung@kitu.local', 'Verwaltung', 'verwalter'],
    [getenv('KITU_WARTUNG') ?: 'wartung@kitu.local', 'Wartung', 'wartung'],
] as [$kennung, $name, $rolle]) {
    [$konto, $kennwort] = dienstkonto($kennung, $name, $rolle);
    zeige_zugang($konto, $kennwort);
}
echo "Nach der ersten Anmeldung bitte unter konto.php ein eigenes Kennwort setzen.\n";
