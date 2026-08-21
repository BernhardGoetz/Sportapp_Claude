<?php
/**
 * Gemeinsamer Vorlauf: Konfiguration, Datenbank, Sitzung, Hilfen.
 *
 * Jede Seite im Verzeichnis darueber beginnt mit
 * ``require __DIR__ . '/inc/start.php';``.
 */

declare(strict_types=1);

mb_internal_encoding('UTF-8');
date_default_timezone_set('UTC');

/** Die Konfiguration - aus KITU_KONFIG oder inc/konfig.php. */
function konfig(): array
{
    static $konfig = null;
    if ($konfig !== null) {
        return $konfig;
    }
    $pfad = getenv('KITU_KONFIG') ?: __DIR__ . '/konfig.php';
    if (!is_file($pfad)) {
        http_response_code(500);
        header('Content-Type: text/plain; charset=utf-8');
        exit(
            "Die Konfiguration fehlt.\n\n"
            . "Bitte php/inc/konfig.beispiel.php nach php/inc/konfig.php kopieren\n"
            . "und die Zugangsdaten eintragen.\n"
        );
    }
    $konfig = require $pfad;
    $konfig['daten'] = rtrim($konfig['daten'] ?? (__DIR__ . '/../daten'), '/');
    if (!is_dir($konfig['daten'])) {
        mkdir($konfig['daten'], 0770, true);
    }
    return $konfig;
}

require __DIR__ . '/db.php';
require __DIR__ . '/vorlage.php';
require __DIR__ . '/sitzung.php';
require __DIR__ . '/post.php';
require __DIR__ . '/konten.php';
require __DIR__ . '/abo.php';
require __DIR__ . '/lizenz.php';

// -- Zeit -------------------------------------------------------------------

function zeitstempel(): string
{
    return gmdate('Y-m-d\TH:i:s+00:00');
}

function heute(): string
{
    return gmdate('Y-m-d');
}

/** Datum in ``tage`` Tagen - gerechnet ab heute oder ab ``ab``. */
function in_tagen(int $tage, string $ab = ''): string
{
    $start = time();
    if ($ab !== '') {
        $start = max($start, (int) strtotime($ab . ' 00:00:00 UTC'));
    }
    return gmdate('Y-m-d', $start + $tage * 86400);
}

// -- Zugang -----------------------------------------------------------------

/** Das angemeldete Konto - oder null. */
function angemeldet(): ?array
{
    $kennung = $_SESSION['kennung'] ?? '';
    if ($kennung === '') {
        return null;
    }
    $konto = konto($kennung);
    if (!$konto || (int) $konto['gesperrt'] === 1) {
        return null;
    }
    return $konto;
}

/**
 * Darf dieses Konto planen? Leer heisst ja, sonst steht hier der Grund.
 * Der kostenlose Zugang gilt dauerhaft - das Abo entscheidet nicht mit.
 */
function darf_planen(?array $konto): string
{
    if (!$konto) {
        return 'anmeldung';
    }
    if ((int) $konto['bestaetigt'] !== 1) {
        return 'bestaetigung';
    }
    return '';
}

/** Angemeldetes Konto verlangen - sonst zur Anmeldung. */
function verlange_anmeldung(string $weiter = ''): array
{
    $konto = angemeldet();
    if (!$konto) {
        weiter_zu('anmelden.php' . ($weiter !== '' ? '?weiter=' . urlencode($weiter) : ''));
    }
    return $konto;
}

/** Rolle verlangen - sonst 403. */
function verlange_rolle(array $konto, array $rollen): void
{
    if (!in_array($konto['rolle'], $rollen, true)) {
        meldeseite('Kein Zutritt',
            'Diese Seite ist der Verwaltung vorbehalten.', 403, $konto);
    }
}

/** Nur POST zulassen (fuer die Formularziele). */
function verlange_post(): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
        meldeseite('Nicht erlaubt', 'Diese Adresse nimmt nur Formulare entgegen.', 405);
    }
    marke_pruefen();
}

function feld(string $name): string
{
    return trim((string) ($_POST[$name] ?? ''));
}

/** Weiterleitungsziel aus dem Formular - nur innerhalb dieser Seite. */
function sicheres_ziel(string $ziel): string
{
    if ($ziel === '' || str_contains($ziel, '//') || str_contains($ziel, ':')) {
        return 'index.php';
    }
    return ltrim($ziel, '/');
}

sitzung_starten();
