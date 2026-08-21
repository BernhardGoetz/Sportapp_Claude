<?php
/**
 * Abo und Probeabo.
 *
 * Der kostenlose Zugang gilt dauerhaft und hat kein Ablaufdatum. Nur ein
 * gebuchtes Abo laeuft nach der gewaehlten Zeit ab; danach faellt das Konto
 * auf den kostenlosen Zugang zurueck. Das Abo bringt den Offline-Schluessel.
 */

declare(strict_types=1);

const ABOZEITEN = [
    'abo_monat' => [31, 'Monatsabo'],
    'abo_jahr'  => [365, 'Jahresabo'],
];
const PROBETAGE   = 14;   // Probeabo: das Kaufabo zum Ausprobieren
const PROBESPERRE = 365;  // danach erst im naechsten Jahr wieder

function abo_laeuft(array $konto): bool
{
    return $konto['abo_bis'] !== '' && $konto['abo_bis'] >= heute();
}

/** Ein gebuchtes Abo, dessen Zeit um ist. */
function abo_gelaufen(array $konto): bool
{
    return $konto['abo_bis'] !== '' && $konto['abo_bis'] < heute();
}

/** Verlaengern - haengt an ein laufendes Abo hinten an. */
function abo_verlaengern(array $konto, int $tage, string $art = 'Abo'): string
{
    $bis = in_tagen($tage, $konto['abo_bis']);
    db_tue('UPDATE konten SET abo_art = ?, abo_bis = ?, abo_seit = ? WHERE kennung = ?',
        [$art, $bis, $konto['abo_seit'] !== '' ? $konto['abo_seit'] : heute(),
         $konto['kennung']]);
    notiere('abo:' . $art, $konto['kennung'], $bis);
    return $bis;
}

/** Zurueck auf den kostenlosen Zugang - der bleibt dauerhaft offen. */
function abo_beenden(array $konto): void
{
    db_tue(
        'UPDATE konten SET abo_art = \'frei\', abo_bis = \'\', abo_seit = ?, offline = \'\'
         WHERE kennung = ?',
        [heute(), $konto['kennung']]
    );
    notiere('abo-beendet', $konto['kennung']);
}

/** Ein Probeabo je Konto und Jahr - und nur ohne laufendes Abo. */
function probe_moeglich(array $konto): bool
{
    if (abo_laeuft($konto)) {
        return false;
    }
    $zuletzt = $konto['probe_zuletzt'];
    return $zuletzt === '' || $zuletzt <= in_tagen(-PROBESPERRE);
}

/** Ab wann das naechste Probeabo moeglich ist. */
function probe_wieder_ab(array $konto): string
{
    return $konto['probe_zuletzt'] !== ''
        ? in_tagen(PROBESPERRE, $konto['probe_zuletzt'])
        : heute();
}

function probe_starten(array $konto): string
{
    $bis = in_tagen(PROBETAGE);
    db_tue(
        'UPDATE konten SET abo_art = \'Probeabo\', abo_seit = ?, abo_bis = ?,
                probe_zuletzt = ? WHERE kennung = ?',
        [heute(), $bis, heute(), $konto['kennung']]
    );
    notiere('probeabo', $konto['kennung'], $bis);
    return $bis;
}
