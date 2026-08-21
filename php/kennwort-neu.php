<?php
/** Code und neues Kennwort eingeben. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$fehler = '';
$meldung = isset($_GET['gesendet'])
    ? 'Wenn es zu dieser E-Mail ein Konto gibt, ist ein Code unterwegs.' : '';
$kennung = kennung_normiert((string) ($_GET['kennung'] ?? ''));

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $meldung = '';
    $kennung = kennung_normiert(feld('kennung'));
    $kennwort = (string) ($_POST['kennwort'] ?? '');
    $konto = konto($kennung);

    if (mb_strlen($kennwort) < MINDESTKENNWORT) {
        $fehler = 'Das Kennwort braucht mindestens ' . MINDESTKENNWORT . ' Zeichen.';
    } elseif ($kennwort !== (string) ($_POST['kennwort2'] ?? '')) {
        $fehler = 'Die Kennwoerter stimmen nicht ueberein.';
    } elseif (zu_viele_versuche(merkmal($kennung))) {
        $fehler = 'Zu viele Versuche. Bitte spaeter erneut.';
    } elseif (!$konto || !code_stimmt($konto['kennung'], 'kennwort', feld('code'))) {
        fehlversuch(merkmal($kennung));
        notiere('kennwortcode-falsch', $kennung !== '' ? $kennung : '-');
        $fehler = 'Dieser Code stimmt nicht oder ist abgelaufen.';
    } else {
        kennwort_setzen($konto['kennung'], $kennwort);
        // Der Code kam ja an die Mailadresse - damit ist sie bestaetigt.
        konto_feld_setzen($konto['kennung'], 'bestaetigt', 1);
        notiere('kennwort-neu', $konto['kennung']);
        sitzung_erneuern($konto['kennung']);
        weiter_zu('index.php');
    }
}

zeige('kennwort-neu', array_merge(balken($meldung, $fehler), [
    'marke'   => marke(),
    'kennung' => $kennung,
    'mindest' => MINDESTKENNWORT,
]), 'Neues Kennwort');
