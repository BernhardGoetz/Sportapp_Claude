<?php
/** Eigenes Konto: Abo, Offline-Schluessel, Kennwort aendern. */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

$konto = verlange_anmeldung('konto.php');
$fehler = '';
$meldung = (string) ($_GET['meldung'] ?? '');

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    marke_pruefen();
    $neu = (string) ($_POST['neu'] ?? '');
    if (!kennwort_stimmt($konto, (string) ($_POST['alt'] ?? ''))) {
        $fehler = 'Das bisherige Kennwort stimmt nicht.';
    } elseif (mb_strlen($neu) < MINDESTKENNWORT) {
        $fehler = 'Mindestens ' . MINDESTKENNWORT . ' Zeichen, bitte.';
    } elseif ($neu !== (string) ($_POST['neu2'] ?? '')) {
        $fehler = 'Die Kennwoerter stimmen nicht ueberein.';
    } else {
        kennwort_setzen($konto['kennung'], $neu);
        notiere('kennwort-geaendert', $konto['kennung']);
        $meldung = 'Das Kennwort ist geaendert.';
        $konto = konto($konto['kennung']);
    }
}

// -- Abo ---------------------------------------------------------------------
if (abo_laeuft($konto)) {
    $abotext = '<p><strong>' . htmlspecialchars($konto['abo_art'], ENT_QUOTES, 'UTF-8')
        . '</strong> - laeuft bis ' . htmlspecialchars($konto['abo_bis'], ENT_QUOTES, 'UTF-8')
        . '.</p><p class="klein">Danach geht es kostenlos weiter; nur der '
        . 'Offline-Schluessel braucht ein laufendes Abo.</p>';
} elseif (abo_gelaufen($konto)) {
    $abotext = '<p>Das Abo lief bis ' . htmlspecialchars($konto['abo_bis'], ENT_QUOTES, 'UTF-8')
        . ' - seitdem ist dieses Konto wieder <strong>kostenlos</strong> unterwegs.</p>'
        . '<p class="klein">Planen geht damit dauerhaft weiter. Fuer den '
        . 'Offline-Betrieb bitte beim Verwalter ein Abo anfragen.</p>';
} else {
    $abotext = '<p><strong>Kostenlos</strong> - dauerhaft, ohne Ablaufdatum.</p>'
        . '<p class="klein">Planen, Stundenbild als PDF, alles dabei. Ein Abo '
        . 'braucht nur, wer die Datei offline mitnehmen will.</p>';
}
if (!probe_moeglich($konto) && $konto['probe_zuletzt'] !== '') {
    $abotext .= '<p class="klein">Das Probeabo lief zuletzt am '
        . htmlspecialchars($konto['probe_zuletzt'], ENT_QUOTES, 'UTF-8')
        . (abo_laeuft($konto)
            ? '.</p>'
            : ' - ein neues gibt es ab '
              . htmlspecialchars(probe_wieder_ab($konto), ENT_QUOTES, 'UTF-8') . '.</p>');
}

// -- Offline -----------------------------------------------------------------
if ($konto['offline'] !== '') {
    $offlinetext = '<p>Dieser Schluessel gehoert zu <strong>genau diesem Konto</strong>: '
        . 'Datei herunterladen, oeffnen, E-Mail und Schluessel eingeben - danach '
        . 'laeuft der Stundenplaner ohne Verbindung.</p>'
        . '<p class="schluessel">' . htmlspecialchars($konto['offline'], ENT_QUOTES, 'UTF-8')
        . '</p><p><a href="kinderturnen.php">Datei herunterladen</a> - einmal '
        . 'speichern, danach genuegt ein Doppelklick. Ohne die E-Mail des Kontos '
        . 'ist der Schluessel wertlos.</p>';
} else {
    $offlinetext = '<p class="klein">Fuer dieses Konto ist kein Offline-Schluessel '
        . 'freigegeben. Solange laeuft das Programm nur ueber den Server.</p>';
}

// -- Seite bauen -------------------------------------------------------------
$vorlage = seite_laden('konto');
if (!probe_moeglich($konto)) {
    $vorlage = preg_replace('/<!-- probe -->.*?<!-- \/probe -->/s', '', $vorlage);
} else {
    $vorlage = str_replace(['<!-- probe -->', '<!-- /probe -->'], '', $vorlage);
}
zeige_vorlage($vorlage, array_merge(balken($meldung, $fehler), [
    'marke'       => marke(),
    'name'        => $konto['name'] !== '' ? $konto['name'] : '-',
    'kennung'     => $konto['kennung'],
    'rolle'       => $konto['rolle'],
    'abotext'     => $abotext,
    'offlinetext' => $offlinetext,
    'probetage'   => PROBETAGE,
]), 'Konto', $konto);
