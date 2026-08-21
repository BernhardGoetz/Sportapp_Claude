<?php
/** Code aus der Bestaetigungsmail eingeben. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$fehler = '';
$meldung = (string) ($_GET['meldung'] ?? '');
$konto = angemeldet();

if ($konto && (int) $konto['bestaetigt'] === 1) {
    weiter_zu('index.php');
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $ziel = $konto ?: konto(feld('kennung'));
    if (!$ziel) {
        $fehler = 'Zu dieser E-Mail gibt es kein Konto.';
    } elseif ((int) $ziel['bestaetigt'] === 1) {
        weiter_zu('index.php');
    } elseif (zu_viele_versuche(merkmal($ziel['kennung']))) {
        $fehler = 'Zu viele Versuche. Bitte spaeter erneut.';
    } elseif (!code_stimmt($ziel['kennung'], 'bestaetigung', feld('code'))) {
        fehlversuch(merkmal($ziel['kennung']));
        notiere('bestaetigung-falsch', $ziel['kennung']);
        $fehler = 'Dieser Code stimmt nicht oder ist abgelaufen.';
    } else {
        konto_feld_setzen($ziel['kennung'], 'bestaetigt', 1);
        notiere('bestaetigt', $ziel['kennung']);
        sitzung_erneuern($ziel['kennung']);
        weiter_zu('index.php');
    }
}

$wohin = $konto
    ? '<strong>' . htmlspecialchars($konto['kennung'], ENT_QUOTES, 'UTF-8') . '</strong>'
    : 'deine E-Mail';
$kennungsfeld = $konto ? '' :
    '<label for="kennung">E-Mail</label>'
    . '<input id="kennung" name="kennung" type="email" required autocomplete="username">';

zeige('bestaetigen', array_merge(balken($meldung, $fehler), [
    'marke'        => marke(),
    'wohin'        => $wohin,
    'minuten'      => CODE_MINUTEN,
    'kennung'      => $konto['kennung'] ?? '',
    'kennungsfeld' => $kennungsfeld,
]), 'Konto bestaetigen');
