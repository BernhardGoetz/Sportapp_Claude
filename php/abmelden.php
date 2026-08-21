<?php
/** Abmelden. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

verlange_post();
$konto = angemeldet();
if ($konto) {
    notiere('abmeldung', $konto['kennung']);
}
sitzung_beenden();
weiter_zu('anmelden.php');
