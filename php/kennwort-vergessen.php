<?php
/**
 * Code fuer ein neues Kennwort anfordern.
 *
 * Ob es zu einer Adresse ein Konto gibt, verraet die Seite nicht.
 */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $kennung = kennung_normiert(feld('kennung'));
    $konto = konto($kennung);
    if ($konto && (int) $konto['gesperrt'] !== 1) {
        code_senden($konto, 'kennwort');
    } else {
        notiere('kennwortcode-ins-leere', $kennung !== '' ? $kennung : '-');
    }
    weiter_zu('kennwort-neu.php?kennung=' . urlencode($kennung) . '&gesendet=1');
}

zeige('kennwort-vergessen', array_merge(balken(), ['marke' => marke()]),
    'Kennwort vergessen');
