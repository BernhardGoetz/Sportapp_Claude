<?php
/** Verwaltung: Konten, Abos, Offline-Schluessel, Rollen. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$konto = verlange_anmeldung('verwaltung.php');
verlange_rolle($konto, ['verwalter']);
$meldung = '';

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $tat = feld('tat');
    $ziel = konto(feld('konto'));

    if (!$ziel) {
        $meldung = 'Dieses Konto gibt es nicht.';
    } elseif ($tat === 'sperren') {
        konto_feld_setzen($ziel['kennung'], 'gesperrt', 1);
        $meldung = $ziel['kennung'] . ' ist gesperrt.';
    } elseif ($tat === 'entsperren') {
        konto_feld_setzen($ziel['kennung'], 'gesperrt', 0);
        $meldung = $ziel['kennung'] . ' ist wieder frei.';
    } elseif ($tat === 'offline_geben') {
        if (!abo_laeuft($ziel)) {
            $meldung = $ziel['kennung'] . ' hat kein laufendes Abo - offline geht '
                . 'nur mit Abo. Erst verlaengern, dann freigeben.';
        } else {
            $schluessel = offline_geben($ziel);
            $meldung = $ziel['kennung'] . ' kann jetzt offline arbeiten: '
                . $schluessel . ' (steht auch im Konto der Person, gilt bis '
                . $ziel['abo_bis'] . ').';
        }
    } elseif ($tat === 'offline_nehmen') {
        konto_feld_setzen($ziel['kennung'], 'offline', '');
        notiere('offline-entzogen', $ziel['kennung']);
        $meldung = $ziel['kennung'] . ' arbeitet wieder nur ueber den Server. Eine '
            . 'schon heruntergeladene Datei laeuft bis zum Ende des Abos weiter.';
    } elseif (isset(ABOZEITEN[$tat])) {
        [$tage, $art] = ABOZEITEN[$tat];
        $meldung = "$art von " . $ziel['kennung'] . ' laeuft bis '
            . abo_verlaengern($ziel, $tage, $art) . '.';
    } elseif ($tat === 'abo_stop') {
        abo_beenden($ziel);
        $meldung = 'Abo von ' . $ziel['kennung'] . ' ist beendet - das Konto plant '
            . 'kostenlos weiter, der Offline-Schluessel ist weg.';
    } elseif ($tat === 'probe') {
        if (!probe_moeglich($ziel)) {
            $meldung = $ziel['kennung'] . ' hatte im letzten Jahr schon ein Probeabo '
                . '(oder hat gerade ein laufendes Abo).';
        } else {
            $meldung = 'Probeabo fuer ' . $ziel['kennung'] . ' laeuft bis '
                . probe_starten($ziel) . '.';
        }
    } elseif ($tat === 'verwalter' || $tat === 'wartung' || $tat === 'nutzer') {
        konto_feld_setzen($ziel['kennung'], 'rolle', $tat);
        notiere('rolle:' . $tat, $konto['kennung'], $ziel['kennung']);
        $meldung = $ziel['kennung'] . ' hat jetzt die Rolle ' . $tat . '.';
    }
    $konto = konto($konto['kennung']);
}

/** Ein Knopf in der Tatenspalte. */
function knopf(string $tat, string $kennung, string $beschriftung): string
{
    return '<form method="post" action="verwaltung.php">'
        . '<input type="hidden" name="marke" value="' . marke() . '">'
        . '<input type="hidden" name="tat" value="' . htmlspecialchars($tat, ENT_QUOTES, 'UTF-8') . '">'
        . '<input type="hidden" name="konto" value="' . htmlspecialchars($kennung, ENT_QUOTES, 'UTF-8') . '">'
        . '<button class="leise">' . htmlspecialchars($beschriftung, ENT_QUOTES, 'UTF-8')
        . '</button></form> ';
}

$konten = konten_alle();
$saetze = [];
$laufend = 0;
foreach ($konten as $eintrag) {
    $kennung = $eintrag['kennung'];
    $taten = (int) $eintrag['gesperrt'] === 1
        ? knopf('entsperren', $kennung, 'Entsperren')
        : knopf('sperren', $kennung, 'Sperren');
    $taten .= $eintrag['offline'] !== ''
        ? knopf('offline_nehmen', $kennung, 'Offline entziehen')
        : knopf('offline_geben', $kennung, 'Offline freigeben');
    $taten .= knopf('abo_monat', $kennung, '+1 Monat');
    $taten .= knopf('abo_jahr', $kennung, '+1 Jahr');
    if (abo_laeuft($eintrag)) {
        $laufend++;
        $taten .= knopf('abo_stop', $kennung, 'Abo beenden');
        $abo = htmlspecialchars($eintrag['abo_art'], ENT_QUOTES, 'UTF-8') . ' bis '
            . htmlspecialchars($eintrag['abo_bis'], ENT_QUOTES, 'UTF-8');
    } elseif (abo_gelaufen($eintrag)) {
        $abo = 'kostenlos (Abo lief bis '
            . htmlspecialchars($eintrag['abo_bis'], ENT_QUOTES, 'UTF-8') . ')';
    } else {
        $abo = 'kostenlos';
    }
    $taten .= knopf('probe', $kennung, 'Probeabo geben');
    if ($eintrag['rolle'] !== 'verwalter') {
        $taten .= knopf('verwalter', $kennung, 'Zum Verwalter');
    }
    if ($eintrag['rolle'] === 'nutzer') {
        $taten .= knopf('wartung', $kennung, 'Zur Wartung');
    }
    if ($eintrag['probe_zuletzt'] !== '') {
        $abo .= '<br>Probe: ' . htmlspecialchars($eintrag['probe_zuletzt'], ENT_QUOTES, 'UTF-8');
    }
    $zustand = (int) $eintrag['gesperrt'] === 1 ? 'gesperrt' : $eintrag['rolle'];
    if ((int) $eintrag['bestaetigt'] !== 1) {
        $zustand .= ' (unbestaetigt)';
    }

    $saetze[] = [
        'name'    => $eintrag['name'] !== '' ? $eintrag['name'] : '-',
        'kennung' => $kennung,
        'zustand' => $zustand,
        'abo'     => $abo,
        'offline' => $eintrag['offline'] !== '' ? $eintrag['offline'] : '-',
        'taten'   => $taten,
    ];
}

[$vorlage, $zeilen] = bloecke(seite_laden('verwaltung'), 'zeile', $saetze);
zeige_vorlage($vorlage, array_merge(balken($meldung), [
    'zeile'   => $zeilen,
    'konten'  => count($konten),
    'laufend' => $laufend,
]), 'Verwaltung', $konto);
