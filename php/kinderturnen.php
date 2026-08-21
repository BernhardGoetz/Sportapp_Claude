<?php
/**
 * Die persoenliche Kopie zum Mitnehmen: dieselbe Datei, aber mit der Huelle
 * dieses Kontos. Ohne Offline-Schluessel ist es die gewoehnliche Fassung.
 */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$konto = angemeldet();
$grund = darf_planen($konto);
if ($grund === 'anmeldung') {
    weiter_zu('anmelden.php?weiter=kinderturnen.php');
}
if ($grund === 'bestaetigung') {
    weiter_zu('bestaetigen.php');
}

notiere('datei-geladen', $konto['kennung']);
header('Content-Type: text/html; charset=utf-8');
header('Content-Disposition: attachment; filename="kinderturnen.html"');
header('Cache-Control: no-store');
echo persoenliche_datei($konto);
