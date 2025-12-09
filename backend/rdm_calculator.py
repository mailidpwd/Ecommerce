"""
RDM Score Calculator

Computes a generic RDM score for any electronics / white goods:
RDM = 0.25*Price + 0.25*Rating + 0.20*Reviews + 0.20*Features + 0.10*Ownership

All sub-scores are 0–100 and normalized within the comparison group.
"""

import math
import re
from typing import Dict, List, Optional, Tuple


# ---------- Helpers ---------- #

def _safe_range(values: List[float], default_min: float, default_max: float) -> Tuple[float, float]:
    if not values:
        return default_min, default_max
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        # Avoid divide-by-zero; expand a tiny range
        return vmin, vmin + 1
    return vmin, vmax


def _normalize(value: Optional[float], vmin: float, vmax: float, default: float = 50.0) -> float:
    if value is None:
        return default
    if vmax == vmin:
        return default
    return max(0.0, min(100.0, 100.0 * (value - vmin) / (vmax - vmin)))


# ---------- Spec Extraction ---------- #

def extract_detailed_specs(title: str, specs: List[str], category: str) -> Dict:
    """
    Extract detailed specs from title/spec strings to feed RDM calculator.
    """
    text = f"{title} {' '.join(specs)}".lower()

    def _extract_int(pattern: str) -> Optional[int]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None

    # RAM (GB)
    ram_gb = _extract_int(r'(\d+)\s*gb\s*(?:ram|ddr)')

    # Storage (GB/TB)
    storage_match = re.search(r'(\d+)\s*(tb|gb)\s*(?:ssd|hdd|storage|emmc)?', text, re.IGNORECASE)
    storage_gb = None
    storage_type = None
    if storage_match:
        size = int(storage_match.group(1))
        unit = storage_match.group(2).lower()
        storage_gb = size * 1024 if unit == 'tb' else size
        if 'ssd' in text:
            storage_type = 'SSD'
        elif 'hdd' in text:
            storage_type = 'HDD'

    # Battery (mAh or WHR)
    battery_mah = _extract_int(r'(\d{3,5})\s*mAh')
    if battery_mah is None:
        # Try WHR -> rough convert to mAh assuming 3.8V
        whr = _extract_int(r'(\d{2,3})\s*whr')
        if whr:
            battery_mah = int((whr * 1000) / 3.8)

    # Display size (inches)
    display_size = None
    m = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*(?:\"|inch|in)', text, re.IGNORECASE)
    if m:
        display_size = float(m.group(1))

    # Display type
    display_type = None
    if re.search(r'4k|uhd', text, re.IGNORECASE):
        display_type = '4K'
    elif re.search(r'qhd|2k', text, re.IGNORECASE):
        display_type = 'QHD'
    elif re.search(r'fhd|full\s*hd|1080', text, re.IGNORECASE):
        display_type = 'FHD'
    elif re.search(r'hd\s*(ready)?|720', text, re.IGNORECASE):
        display_type = 'HD'

    # Processor
    processor = None
    processor_patterns = [
        r'(snapdragon\s+\d+\s*(?:gen\s*\d+)?)',
        r'(mediatek\s+dimensity\s*\d+)',
        r'(mediatek\s+\w+\d+)',
        r'(apple\s+[am]\d+)',
        r'(intel\s+core\s+i\d+)',
        r'(amd\s+ryzen\s+\d+)',
        r'(exynos\s*\d+)',
    ]
    for pat in processor_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            processor = m.group(1)
            break

    # Warranty (years)
    warranty_years = None
    wm = re.search(r'(\d+)\s*(year|yr)', text, re.IGNORECASE)
    if wm:
        warranty_years = int(wm.group(1))

    # Energy star (for appliances)
    energy_star = None
    em = re.search(r'(\d)\s*star', text, re.IGNORECASE)
    if em:
        try:
            energy_star = int(em.group(1))
        except Exception:
            energy_star = None

    # Performance score (heuristic from processor)
    performance_score = calculate_performance_score(processor, category)

    return {
        'ram_gb': ram_gb,
        'storage_gb': storage_gb,
        'storage_type': storage_type,
        'battery_mah': battery_mah,
        'display_size': display_size,
        'display_type': display_type,
        'processor': processor,
        'warranty_years': warranty_years,
        'energy_star': energy_star,
        'performance_score': performance_score,
    }


def calculate_performance_score(processor: Optional[str], category: str) -> int:
    """Heuristic performance score (0-100) from processor name."""
    if not processor:
        return 50
    p = processor.upper()

    if category in ['smartphone', 'phone']:
        # Phones
        if 'SNAPDRAGON 8' in p or 'APPLE A1' in p or 'DIMENSITY 9' in p:
            return 95
        if 'SNAPDRAGON 7' in p or 'DIMENSITY 8' in p:
            return 85
        if 'SNAPDRAGON 6' in p or 'DIMENSITY 7' in p:
            return 75
        if 'SNAPDRAGON 4' in p or 'DIMENSITY 6' in p:
            return 65
        return 60

    if category == 'laptop':
        # Laptops
        if 'I9' in p or 'RYZEN 9' in p:
            return 95
        if 'I7' in p or 'RYZEN 7' in p:
            return 85
        if 'I5' in p or 'RYZEN 5' in p:
            return 75
        if 'I3' in p or 'RYZEN 3' in p:
            return 65
        return 60

    # Generic
    return 60


# ---------- RDM Calculation ---------- #

def _ownership_score(warranty_years: Optional[int], energy_star: Optional[int]) -> float:
    # Warranty mapping
    w_score = 0
    if warranty_years is not None:
        if warranty_years >= 3:
            w_score = 100
        elif warranty_years == 2:
            w_score = 70
        elif warranty_years == 1:
            w_score = 40
        else:
            w_score = 20

    # Energy star mapping (1-5)
    e_score = 0
    if energy_star is not None:
        e_score = 20 * energy_star  # 1->20, 5->100

    if warranty_years is not None and energy_star is not None:
        return (w_score + e_score) / 2
    if warranty_years is not None:
        return w_score
    if energy_star is not None:
        return e_score
    return 40  # default comfort


def _feature_score(product: Dict, category: str, ranges: Dict) -> float:
    perf = product.get('performance_score') or 50

    if category in ['smartphone', 'phone']:
        ram = _normalize(product.get('ram_gb'), ranges['ram_min'], ranges['ram_max'])
        storage = _normalize(product.get('storage_gb'), ranges['storage_min'], ranges['storage_max'])
        battery = _normalize(product.get('battery_mah'), ranges['battery_min'], ranges['battery_max'])
        return (
            0.30 * perf +
            0.25 * ram +
            0.25 * storage +
            0.20 * battery
        )

    if category == 'laptop':
        ram = _normalize(product.get('ram_gb'), ranges['ram_min'], ranges['ram_max'])
        storage_type = product.get('storage_type')
        storage_type_score = 100 if storage_type == 'SSD' else 60 if storage_type == 'HDD' else 50
        display_type = product.get('display_type')
        display_score = 100 if display_type == '4K' else 80 if display_type == 'QHD' else 60 if display_type == 'FHD' else 50
        battery = _normalize(product.get('battery_mah'), ranges['battery_min'], ranges['battery_max'])
        return (
            0.30 * perf +
            0.25 * ram +
            0.20 * storage_type_score +
            0.15 * display_score +
            0.10 * battery
        )

    if category in ['tv', 'monitor', 'display']:
        size = _normalize(product.get('display_size'), ranges['size_min'], ranges['size_max'])
        display_type = product.get('display_type')
        display_score = 100 if display_type == '4K' else 80 if display_type == 'QHD' else 60 if display_type == 'FHD' else 50
        return 0.5 * display_score + 0.5 * size

    if category in ['ac', 'air conditioner']:
        energy = _normalize(product.get('energy_star'), 1, 5, default=50)
        return energy

    if category in ['fridge', 'refrigerator', 'washing machine', 'appliance']:
        energy = _normalize(product.get('energy_star'), 1, 5, default=50)
        return energy

    # Generic
    return perf


def calculate_rdm_scores(products: List[Dict], category: str) -> List[Dict]:
    """
    Calculate RDM scores for a list of products (dicts).
    Each product dict must include:
      - price_raw (int, paise)
      - rating_estimate (float)
      - rating_count_estimate (int)
      - specs (List[str])
      - title (str)
    Returns products with added rdm_score and rdm_breakdown.
    """
    if not products:
        return []

    # Extract detailed specs first
    enriched = []
    for p in products:
        details = extract_detailed_specs(p.get('title', ''), p.get('specs', []), category)
        enriched.append({**p, **details})

    # Build ranges for normalization
    prices = [p.get('price_raw', 0) / 100 for p in enriched if p.get('price_raw')]
    ratings = [p.get('rating_estimate') for p in enriched if p.get('rating_estimate')]
    reviews = []
    for p in enriched:
        rc = p.get('rating_count_estimate')
        if rc is None and p.get('rating_estimate'):
            rc = 10  # minimal fallback if rating exists but count missing
        if rc:
            reviews.append(rc)

    price_min, price_max = _safe_range(prices, 1, 2)
    rating_max = max(ratings) if ratings else 5.0
    review_counts_valid = [r for r in reviews if r and r >= 1]
    review_max = max(review_counts_valid) if review_counts_valid else 0

    ranges = {
        'ram_min': None, 'ram_max': None,
        'storage_min': None, 'storage_max': None,
        'battery_min': None, 'battery_max': None,
        'size_min': None, 'size_max': None,
    }

    def _set_range(name: str, values: List[float], dmin: float, dmax: float):
        vmin, vmax = _safe_range(values, dmin, dmax)
        ranges[f"{name}_min"], ranges[f"{name}_max"] = vmin, vmax

    # Ranges based on category
    if category in ['smartphone', 'phone']:
        _set_range('ram', [p['ram_gb'] for p in enriched if p.get('ram_gb')], 4, 12)
        _set_range('storage', [p['storage_gb'] for p in enriched if p.get('storage_gb')], 64, 512)
        _set_range('battery', [p['battery_mah'] for p in enriched if p.get('battery_mah')], 4000, 6000)
    elif category == 'laptop':
        _set_range('ram', [p['ram_gb'] for p in enriched if p.get('ram_gb')], 8, 32)
        _set_range('storage', [p['storage_gb'] for p in enriched if p.get('storage_gb')], 256, 2048)
        _set_range('battery', [p['battery_mah'] for p in enriched if p.get('battery_mah')], 3000, 8000)
    else:
        _set_range('ram', [p['ram_gb'] for p in enriched if p.get('ram_gb')], 4, 16)
        _set_range('storage', [p['storage_gb'] for p in enriched if p.get('storage_gb')], 64, 512)
        _set_range('battery', [p['battery_mah'] for p in enriched if p.get('battery_mah')], 4000, 6000)
        _set_range('size', [p['display_size'] for p in enriched if p.get('display_size')], 6, 55)

    # Compute scores
    for p in enriched:
        price = p.get('price_raw', 0) / 100
        rating = p.get('rating_estimate') or 0
        review_cnt = p.get('rating_count_estimate')
        if review_cnt is None and rating > 0:
            review_cnt = 10  # fallback
        review_cnt = review_cnt or 0

        price_score = 100 * (price_max - price) / (price_max - price_min) if price_max > price_min else 50
        rating_score = 20 * rating  # 0-100
        # ReviewScore: if we don’t have enough data, use neutral 50 to avoid skew
        if review_max <= 0 or len(review_counts_valid) < 2 or review_max < 50:
            review_score = 50.0
        else:
            review_score = 100 * math.log(1 + review_cnt) / math.log(1 + review_max) if review_cnt > 0 else 0
        ownership_score = _ownership_score(p.get('warranty_years'), p.get('energy_star'))
        feature_score = _feature_score(p, category, ranges)

        # Generic weights (can be adjusted per category)
        if category in ['smartphone', 'phone']:
            rdm = (
                0.20 * price_score +
                0.25 * rating_score +
                0.20 * review_score +
                0.25 * feature_score +
                0.10 * ownership_score
            )
        elif category == 'laptop':
            rdm = (
                0.20 * price_score +
                0.25 * rating_score +
                0.20 * review_score +
                0.25 * feature_score +
                0.10 * ownership_score
            )
        else:
            rdm = (
                0.25 * price_score +
                0.25 * rating_score +
                0.20 * review_score +
                0.20 * feature_score +
                0.10 * ownership_score
            )

        p['rdm_score'] = round(rdm, 1)
        p['rdm_breakdown'] = {
            'price_score': round(price_score, 1),
            'rating_score': round(rating_score, 1),
            'review_score': round(review_score, 1),
            'feature_score': round(feature_score, 1),
            'ownership_score': round(ownership_score, 1),
        }

    # Sort by RDM descending
    enriched.sort(key=lambda x: x.get('rdm_score', 0), reverse=True)
    return enriched


