"""Stammdaten und Vergleichsfassung des Kinderturnen-Stundenplaners.

Bedient wird das Programm im Browser (``web/kinderturnen.html``). Dieses
Paket liefert den Katalog (``data/``), aus dem die Browser-Fassung gebaut
wird, und dazu dieselbe Planungslogik in Python: Bedarfsrechnung inklusive
Absicherung, Flaechenbudget, Platzierung in der Halle, Stil-Lernen je
Altersgruppe und das Stundenbild als PDF. Es wird nicht ausgeliefert,
sondern dient dem Bauen (``werkzeuge/baue_web.py``) und den Tests.
"""

__version__ = "4.0.0"

__all__ = ["__version__"]
