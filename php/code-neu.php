<?php
/** Neuen Bestaetigungscode anfordern. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

verlange_post();
$konto = angemeldet() ?: konto(feld('kennung'));
if ($konto && (int) $konto['bestaetigt'] !== 1) {
    code_senden($konto, 'bestaetigung');
}
weiter_zu('bestaetigen.php?meldung=' . urlencode('Ein neuer Code ist unterwegs.'));
