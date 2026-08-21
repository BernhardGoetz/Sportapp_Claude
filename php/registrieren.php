<?php
/** Neues Konto anlegen - danach wartet die Bestaetigung per Mail. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$fehler = '';
$name = '';
$kennung = '';

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $name = feld('name');
    $kennung = kennung_normiert(feld('kennung'));
    $kennwort = (string) ($_POST['kennwort'] ?? '');

    if (!preg_match('/^[^@\s]+@[^@\s]+\.[^@\s]+$/', $kennung)) {
        $fehler = 'Bitte eine gueltige E-Mail angeben.';
    } elseif (mb_strlen($kennwort) < MINDESTKENNWORT) {
        $fehler = 'Das Kennwort braucht mindestens ' . MINDESTKENNWORT . ' Zeichen.';
    } elseif ($kennwort !== (string) ($_POST['kennwort2'] ?? '')) {
        $fehler = 'Die Kennwoerter stimmen nicht ueberein.';
    } elseif (konto($kennung)) {
        $fehler = 'Zu dieser E-Mail gibt es schon ein Konto.';
    } else {
        $konto = konto_anlegen($kennung, $name, $kennwort);
        code_senden($konto, 'bestaetigung');
        sitzung_erneuern($konto['kennung']);
        weiter_zu('bestaetigen.php');
    }
}

zeige('registrieren', array_merge(balken('', $fehler), [
    'marke'   => marke(),
    'name'    => $name,
    'kennung' => $kennung,
    'mindest' => MINDESTKENNWORT,
]), 'Registrieren');
