<?php
/** Anmeldung. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$fehler = '';
$kennung = '';
$weiter = sicheres_ziel((string) ($_GET['weiter'] ?? $_POST['weiter'] ?? 'index.php'));

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $kennung = kennung_normiert(feld('kennung'));
    $kennwort = (string) ($_POST['kennwort'] ?? '');

    if (zu_viele_versuche(merkmal($kennung))) {
        notiere('anmeldung-gesperrt', $kennung, herkunft());
        $fehler = 'Zu viele Fehlversuche. Bitte in einer Viertelstunde erneut.';
    } else {
        $konto = konto($kennung);
        if (!$konto || !kennwort_stimmt($konto, $kennwort)) {
            fehlversuch(merkmal($kennung));
            notiere('anmeldung-falsch', $kennung, herkunft());
            $fehler = 'E-Mail oder Kennwort stimmt nicht.';
        } elseif ((int) $konto['gesperrt'] === 1) {
            notiere('anmeldung-gesperrtes-konto', $kennung);
            $fehler = 'Dieses Konto ist gesperrt.';
        } else {
            sitzung_erneuern($konto['kennung']);
            notiere('anmeldung', $konto['kennung']);
            if ((int) $konto['bestaetigt'] !== 1) {
                code_senden($konto, 'bestaetigung');
                weiter_zu('bestaetigen.php');
            }
            weiter_zu($weiter);
        }
    }
}

zeige('anmelden', array_merge(balken('', $fehler), [
    'marke'   => marke(),
    'weiter'  => $weiter,
    'kennung' => $kennung,
]), 'Anmelden');
