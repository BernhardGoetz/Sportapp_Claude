<?php
/**
 * Gibt den Blockschluessel heraus - nur an angemeldete, bestaetigte Konten.
 * Der Lader in der Anwendung ruft diese Adresse beim Start auf.
 */

declare(strict_types=1);
require __DIR__ . '/inc/start.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

$konto = angemeldet();
$grund = darf_planen($konto);
if ($grund !== '') {
    http_response_code(401);
    notiere('freischalten-abgelehnt', $konto['kennung'] ?? herkunft(), $grund);
    echo json_encode(['fehler' => $grund]);
    exit;
}

notiere('freischalten', $konto['kennung']);
echo json_encode(['schluessel' => blockschluessel()]);
