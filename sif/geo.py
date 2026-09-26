"""Where a site is: a small gazetteer of Oil India's operating area in Upper Assam.

Reports name a site the way people on the ground do - "Duliajan OCS-4",
"Naharkatiya Rig-12", "Moran Gas Compressor Station". The risk map places
each one by the locality its name contains, at that town's approximate
coordinates; several installations in one locality are spread on a small
ring around it so each can be seen and clicked.

These are town-level positions for orientation, not surveyed coordinates of
installations. A site whose name contains no known locality is listed beside
the map rather than guessed at. :data:`LOCALITIES` is the place to add one.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["LOCALITIES", "TOWNS", "RIVERS", "ROADS", "locate", "place_sites", "km_per_degree"]

#: Locality -> (latitude, longitude), approximate town centres. Keys are matched
#: case-insensitively inside a site's name; aliases share a position.
LOCALITIES: Dict[str, Tuple[float, float]] = {
    "duliajan": (27.365, 95.317),
    "naharkatiya": (27.290, 95.340),
    "naharkatia": (27.290, 95.340),
    "nahorkatiya": (27.290, 95.340),
    "moran": (27.000, 94.930),
    "moranhat": (27.000, 94.930),
    "kumchai": (27.520, 95.900),
    "kharsang": (27.520, 95.880),
    "digboi": (27.390, 95.620),
    "tinsukia": (27.490, 95.360),
    "makum": (27.480, 95.440),
    "jorajan": (27.400, 95.400),
    "margherita": (27.290, 95.680),
    "dibrugarh": (27.480, 94.910),
    "sivasagar": (26.980, 94.640),
    "sibsagar": (26.980, 94.640),
    "lakwa": (26.930, 94.870),
    "doomdooma": (27.560, 95.570),
    "hapjan": (27.440, 95.500),
    "tengakhat": (27.330, 95.140),
}

#: Towns drawn for orientation (name, latitude, longitude).
TOWNS: Tuple[Tuple[str, float, float], ...] = (
    ("Dibrugarh", 27.480, 94.910), ("Tinsukia", 27.490, 95.360), ("Duliajan", 27.365, 95.317),
    ("Naharkatiya", 27.290, 95.340), ("Digboi", 27.390, 95.620), ("Margherita", 27.290, 95.680),
    ("Moran", 27.000, 94.930), ("Sivasagar", 26.980, 94.640), ("Doomdooma", 27.560, 95.570),
)

#: Rivers as (name, width in px, [(lat, lon), ...]) - drawn schematically.
RIVERS: Tuple[Tuple[str, float, Tuple[Tuple[float, float], ...]], ...] = (
    ("Brahmaputra", 9.0, ((26.78, 94.20), (26.93, 94.45), (27.10, 94.62), (27.30, 94.80),
                          (27.52, 94.95), (27.62, 95.15), (27.72, 95.40), (27.80, 95.62),
                          (27.86, 95.85), (27.90, 96.10))),
    ("Burhi Dihing", 3.5, ((27.55, 96.10), (27.40, 95.85), (27.33, 95.60), (27.33, 95.40),
                           (27.27, 95.20), (27.17, 95.02), (27.07, 94.80), (26.97, 94.55))),
    ("Disang", 2.5, ((27.05, 95.30), (26.98, 95.05), (26.95, 94.80), (26.97, 94.60))),
)

#: Main roads as polylines of (lat, lon).
ROADS: Tuple[Tuple[Tuple[float, float], ...], ...] = (
    ((26.98, 94.64), (27.00, 94.93), (27.20, 94.95), (27.48, 94.91)),          # Sivasagar - Moran - Dibrugarh
    ((27.48, 94.91), (27.49, 95.10), (27.49, 95.36), (27.48, 95.44), (27.43, 95.50),
     (27.39, 95.62), (27.29, 95.68)),                                           # Dibrugarh - Tinsukia - Makum - Digboi - Margherita
    ((27.00, 94.93), (27.15, 95.15), (27.290, 95.340), (27.365, 95.317),
     (27.49, 95.36)),                                                           # Moran - Naharkatiya - Duliajan - Tinsukia
    ((27.29, 95.68), (27.40, 95.80), (27.52, 95.90)),                          # Margherita - Kumchai
)


def km_per_degree(latitude: float) -> Tuple[float, float]:
    """Kilometres per degree of (latitude, longitude) at ``latitude``."""
    return 110.57, 111.32 * math.cos(math.radians(latitude))


def locate(site: str) -> Optional[Tuple[str, float, float]]:
    """(locality, latitude, longitude) for a site name, or None if it names none."""
    name = str(site or "").lower()
    best = None
    for locality, (lat, lon) in LOCALITIES.items():
        if locality in name and (best is None or len(locality) > len(best[0])):
            best = (locality, lat, lon)
    return best


def place_sites(sites: Sequence[str],
                ring_km: float = 2.6) -> Tuple[Dict[str, Tuple[float, float, str]], List[str]]:
    """Positions for every site that can be placed, and the names that cannot.

    Sites sharing a locality sit on a ring of ``ring_km`` around it, in name
    order, so the same corpus always draws the same map.
    """
    by_locality: Dict[str, List[str]] = {}
    unplaced: List[str] = []
    for site in sorted(set(sites)):
        found = locate(site)
        if found is None:
            unplaced.append(site)
        else:
            by_locality.setdefault(found[0], []).append(site)
    placed: Dict[str, Tuple[float, float, str]] = {}
    for locality, names in by_locality.items():
        lat, lon = LOCALITIES[locality]
        if len(names) == 1:
            placed[names[0]] = (lat, lon, locality)
            continue
        km_lat, km_lon = km_per_degree(lat)
        for index, name in enumerate(names):
            angle = 2 * math.pi * index / len(names) - math.pi / 2
            placed[name] = (lat + ring_km * math.sin(angle) / km_lat,
                            lon + ring_km * math.cos(angle) / km_lon, locality)
    return placed, unplaced
