<?php
/**
 * Sitzung, CSRF-Marke und die Sperre nach zu vielen Fehlversuchen.
 */

declare(strict_types=1);

const SITZUNGSNAME  = 'kitu_sitzung';
const SITZUNGSDAUER = 30 * 24 * 3600;
const FEHLVERSUCHE  = 10;
const SPERRZEIT     = 15 * 60;

function sitzung_starten(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    $konfig = konfig();
    $ordner = $konfig['daten'] . '/sitzungen';
    if (!is_dir($ordner)) {
        mkdir($ordner, 0770, true);
    }
    session_name(SITZUNGSNAME);
    session_save_path($ordner);
    session_set_cookie_params([
        'lifetime' => SITZUNGSDAUER,
        'path'     => '/',
        'httponly' => true,
        'samesite' => 'Lax',
        'secure'   => (bool) ($konfig['https'] ?? false),
    ]);
    session_start();
}

/** Nach dem Anmelden eine frische Marke - gegen untergeschobene Sitzungen. */
function sitzung_erneuern(string $kennung): void
{
    session_regenerate_id(true);
    $_SESSION['kennung'] = $kennung;
    $_SESSION['seit']    = time();
}

function sitzung_beenden(): void
{
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $keks = session_get_cookie_params();
        setcookie(session_name(), '', time() - 3600, $keks['path'], $keks['domain'],
            $keks['secure'], $keks['httponly']);
    }
    session_destroy();
}

/** CSRF-Marke dieser Sitzung. */
function marke(): string
{
    if (empty($_SESSION['marke'])) {
        $_SESSION['marke'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['marke'];
}

/** Bei POST: Marke pruefen, sonst ist hier Schluss. */
function marke_pruefen(): void
{
    $gesendet = (string) ($_POST['marke'] ?? '');
    if ($gesendet === '' || !hash_equals(marke(), $gesendet)) {
        notiere('marke-falsch', (string) ($_SESSION['kennung'] ?? ''), herkunft());
        meldeseite(
            'Bitte noch einmal',
            'Das Formular war zu alt oder kam von woanders her. '
            . '<a href="anmelden.php">Zurueck zur Anmeldung</a>',
            403
        );
    }
}

function herkunft(): string
{
    return (string) ($_SERVER['REMOTE_ADDR'] ?? '-');
}

function merkmal(string $kennung): string
{
    return herkunft() . '|' . $kennung;
}

/** Zu viele Fehlversuche in der letzten Viertelstunde? */
function zu_viele_versuche(string $merkmal): bool
{
    db_tue('DELETE FROM fehlversuche WHERE zeitpunkt < ?', [time() - SPERRZEIT]);
    return db_zahl('SELECT COUNT(*) FROM fehlversuche WHERE merkmal = ?', [$merkmal])
        >= FEHLVERSUCHE;
}

function fehlversuch(string $merkmal): void
{
    db_tue('INSERT INTO fehlversuche (merkmal, zeitpunkt) VALUES (?, ?)',
        [$merkmal, time()]);
}
