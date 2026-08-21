<?php
/** Probeabo bestellen - einmal je Konto und Jahr. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

verlange_post();
$konto = verlange_anmeldung('konto.php');

if (!probe_moeglich($konto)) {
    weiter_zu('konto.php?meldung=' . urlencode(
        'Ein Probeabo gibt es einmal im Jahr - und nur, wenn gerade kein Abo laeuft.'
    ));
}

$bis = probe_starten($konto);
weiter_zu('konto.php?meldung=' . urlencode(
    "Probeabo laeuft bis $bis. Fuer den Offline-Betrieb bitte beim Verwalter "
    . 'den Schluessel anfordern.'
));
