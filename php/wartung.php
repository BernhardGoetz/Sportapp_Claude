<?php
/** Wartung: der Zustand auf einen Blick - nur zum Schauen. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$konto = verlange_anmeldung('wartung.php');
verlange_rolle($konto, ['verwalter', 'wartung']);

$konten = konten_alle();
$laufend = 0;
$proben = 0;
$offline = 0;
foreach ($konten as $eintrag) {
    if (abo_laeuft($eintrag)) {
        $laufend++;
        if ($eintrag['abo_art'] === 'Probeabo') {
            $proben++;
        }
    }
    if ($eintrag['offline'] !== '') {
        $offline++;
    }
}

$pfad = konfig()['anwendung'];
$datei = is_file($pfad)
    ? round(filesize($pfad) / 1024) . ' KB, gebaut am ' . gmdate('Y-m-d H:i', filemtime($pfad)) . ' UTC'
    : 'fehlt';

$werte = [
    ['name' => 'Konten', 'wert' => (string) count($konten)],
    ['name' => 'davon bestaetigt',
     'wert' => (string) count(array_filter($konten, fn($k) => (int) $k['bestaetigt'] === 1))],
    ['name' => 'davon gesperrt',
     'wert' => (string) count(array_filter($konten, fn($k) => (int) $k['gesperrt'] === 1))],
    ['name' => 'laufende Abos', 'wert' => (string) $laufend],
    ['name' => 'davon Probeabos', 'wert' => (string) $proben],
    ['name' => 'Offline-Schluessel', 'wert' => (string) $offline],
    ['name' => 'offene Codes', 'wert' => (string) db_zahl('SELECT COUNT(*) FROM codes')],
    ['name' => 'kinderturnen.html', 'wert' => $datei],
    ['name' => 'Blockschluessel', 'wert' => substr(blockschluessel(), 0, 8) . '...'],
    ['name' => 'Datenbank', 'wert' => explode(':', konfig()['dsn'])[0]],
    ['name' => 'PHP', 'wert' => PHP_VERSION],
];

$letzte = db_zeilen('SELECT * FROM protokoll ORDER BY zeitpunkt DESC LIMIT 15');
$protokoll = '';
foreach (array_reverse($letzte) as $zeile) {
    $protokoll .= $zeile['zeitpunkt'] . "\t" . $zeile['was'] . "\t"
        . $zeile['wer'] . "\t" . $zeile['mehr'] . "\n";
}

[$vorlage, $zeilen] = bloecke(seite_laden('wartung'), 'zeile', $werte);
zeige_vorlage($vorlage, [
    'zeile'     => $zeilen,
    'protokoll' => $protokoll !== '' ? $protokoll : 'noch nichts',
], 'Wartung', $konto);
