<?php
/**
 * Vorlagen: Das Markup steht in ``seiten/*.html``, hier wird es nur gefuellt.
 *
 * * ``{{name}}``   - Wert, maskiert (fuer alles aus Nutzerhand)
 * * ``{{{name}}}`` - Wert roh (fuer bereits gebautes Markup, z. B. Zeilen)
 * * ``<!-- zeile --> ... <!-- /zeile -->`` - Block, der sich wiederholen laesst
 *
 * So bleibt in den PHP-Dateien die Logik und im HTML das Aussehen.
 */

declare(strict_types=1);

function seitenpfad(string $name): string
{
    return __DIR__ . '/../seiten/' . $name . '.html';
}

function seite_laden(string $name): string
{
    $pfad = seitenpfad($name);
    if (!is_file($pfad)) {
        throw new RuntimeException("Vorlage fehlt: $name");
    }
    return file_get_contents($pfad);
}

/** Platzhalter ersetzen. Nicht belegte Platzhalter fallen weg. */
function fuellen(string $text, array $werte, bool $aufraeumen = true): string
{
    foreach ($werte as $name => $wert) {
        $text = str_replace('{{{' . $name . '}}}', (string) $wert, $text);
        $text = str_replace(
            '{{' . $name . '}}',
            htmlspecialchars((string) $wert, ENT_QUOTES, 'UTF-8'),
            $text
        );
    }
    return $aufraeumen
        ? preg_replace('/\{\{\{?[a-z0-9_]+\}?\}\}/', '', $text)
        : $text;
}

/** Den Inhalt eines Blocks holen. */
function block(string $text, string $name): string
{
    $muster = '/<!-- ' . preg_quote($name, '/') . ' -->(.*?)<!-- \/' . preg_quote($name, '/') . ' -->/s';
    return preg_match($muster, $text, $treffer) ? $treffer[1] : '';
}

/** Den Block aus der Vorlage entfernen (er wird ja einzeln gefuellt). */
function ohne_block(string $text, string $name): string
{
    $muster = '/<!-- ' . preg_quote($name, '/') . ' -->.*?<!-- \/' . preg_quote($name, '/') . ' -->/s';
    return preg_replace($muster, '{{{' . $name . '}}}', $text);
}

/**
 * Einen Block je Datensatz wiederholen.
 *
 * @param array $saetze Liste von Wertelisten
 */
function bloecke(string $text, string $name, array $saetze): array
{
    $muster = block($text, $name);
    $gebaut = '';
    foreach ($saetze as $werte) {
        $gebaut .= fuellen($muster, $werte);
    }
    return [ohne_block($text, $name), $gebaut];
}

/**
 * Fertige Seite bauen: Inhalt aus ``seiten/$name.html`` in ``rahmen.html``.
 */
function seite(string $name, array $werte = [], string $titel = 'Ki Tu', ?array $konto = null): string
{
    return seite_aus(seite_laden($name), $werte, $titel, $konto);
}

/** Wie seite(), aber mit schon geladener Vorlage (z. B. ohne einen Block). */
function seite_aus(string $vorlage, array $werte = [], string $titel = 'Ki Tu', ?array $konto = null): string
{
    $inhalt = fuellen($vorlage, $werte);
    $rahmen = seite_laden('rahmen');

    $navigation = '';
    if ($konto) {
        $teile = block($rahmen, 'navigation');
        $navigation = fuellen($teile, [
            'name'       => $konto['name'] !== '' ? $konto['name'] : $konto['kennung'],
            'verwaltung' => $konto['rolle'] === 'verwalter'
                ? '<a href="verwaltung.php">Verwaltung</a>' : '',
            'wartung'    => in_array($konto['rolle'], ['verwalter', 'wartung'], true)
                ? '<a href="wartung.php">Wartung</a>' : '',
        ]);
    }
    $gebaut = fuellen(ohne_block($rahmen, 'navigation'), [
        'titel'      => $titel,
        'navigation' => $navigation,
    ], false);
    // Reste im Rahmen wegraeumen - {{{inhalt}}} bleibt stehen.
    $gebaut = preg_replace('/\{\{\{?(?!inhalt)[a-z0-9_]+\}?\}\}/', '', $gebaut);
    // Der Inhalt kommt zuletzt hinein - so wird darin nichts mehr ersetzt.
    return str_replace('{{{inhalt}}}', $inhalt, $gebaut);
}

/** Seite ausgeben und Schluss. */
function zeige(string $name, array $werte = [], string $titel = 'Ki Tu', ?array $konto = null, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Cache-Control: no-store');
    echo seite($name, $werte, $titel, $konto);
    exit;
}

/** Seite aus einer schon geladenen Vorlage ausgeben und Schluss. */
function zeige_vorlage(string $vorlage, array $werte = [], string $titel = 'Ki Tu', ?array $konto = null): void
{
    http_response_code(200);
    header('Content-Type: text/html; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Cache-Control: no-store');
    echo seite_aus($vorlage, $werte, $titel, $konto);
    exit;
}

/** Kurze Meldung mit Ueberschrift und Text. */
function meldeseite(string $ueberschrift, string $text, int $status = 200, ?array $konto = null): void
{
    zeige('meldung', ['ueberschrift' => $ueberschrift, 'text' => $text],
        $ueberschrift, $konto, $status);
}

/** Meldungsbalken (gruen) und Fehlerbalken (rot) als fertiges Markup. */
function balken(string $meldung = '', string $fehler = ''): array
{
    return [
        'meldung' => $meldung !== ''
            ? '<p class=gut>' . htmlspecialchars($meldung, ENT_QUOTES, 'UTF-8') . '</p>' : '',
        'fehler'  => $fehler !== ''
            ? '<p class=fehler>' . htmlspecialchars($fehler, ENT_QUOTES, 'UTF-8') . '</p>' : '',
    ];
}

/** Weiterleitung. */
function weiter_zu(string $ziel): void
{
    header('Location: ' . $ziel, true, 303);
    exit;
}
