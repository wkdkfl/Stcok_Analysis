"""
Sum-of-the-Parts (SOTP) Valuation.
Estimates value by applying appropriate multiples to each business segment.

For companies with multiple business lines, SOTP can reveal hidden value
that single-multiple approaches miss (conglomerate discount/premium).

Uses Yahoo Finance segment data when available.
Falls back to single-segment approach using industry benchmarks otherwise.
"""

import json
import os
from typing import Dict, Any, List

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_MULTIPLES_FALLBACK


# Industry → approximate EV/EBITDA multiples for SOTP
INDUSTRY_MULTIPLES = {
    # Technology sub-industries
    "Software—Infrastructure":        25.0,
    "Software—Application":           22.0,
    "Semiconductors":                 18.0,
    "Semiconductor Equipment & Materials": 16.0,
    "Consumer Electronics":           14.0,
    "Information Technology Services": 16.0,
    "Internet Content & Information": 20.0,
    "Electronic Components":          12.0,
    "Computer Hardware":              14.0,
    # Healthcare
    "Biotechnology":                  18.0,
    "Drug Manufacturers—General":     14.0,
    "Medical Devices":                20.0,
    "Health Information Services":    22.0,
    "Medical Instruments & Supplies": 18.0,
    "Diagnostics & Research":         16.0,
    # Consumer
    "Internet Retail":                22.0,
    "Specialty Retail":               12.0,
    "Auto Manufacturers":             8.0,
    "Restaurants":                    16.0,
    "Apparel Manufacturing":          12.0,
    "Packaged Foods":                 14.0,
    "Beverages—Non-Alcoholic":        18.0,
    "Household & Personal Products":  16.0,
    # Financial
    "Banks—Diversified":              10.0,
    "Insurance—Diversified":          10.0,
    "Asset Management":               14.0,
    "Financial Data & Stock Exchanges": 22.0,
    "Credit Services":                12.0,
    # Industrial
    "Aerospace & Defense":            16.0,
    "Railroads":                      14.0,
    "Industrial Distribution":        12.0,
    # Energy
    "Oil & Gas Integrated":           6.0,
    "Oil & Gas E&P":                  5.0,
    "Oil & Gas Refining & Marketing": 5.0,
    # Telecom
    "Telecom Services":               8.0,
    "Entertainment":                  14.0,
    "Advertising Agencies":           12.0,
    # Utilities
    "Utilities—Regulated Electric":   12.0,
    "Utilities—Diversified":          11.0,
    # Real Estate
    "REIT—Diversified":               16.0,
    "REIT—Industrial":                22.0,
}

# Sector → default EV/EBITDA when industry not found
SECTOR_DEFAULT_EV_EBITDA = {
    "Technology":             20.0,
    "Healthcare":             16.0,
    "Financial Services":     10.0,
    "Consumer Cyclical":      14.0,
    "Consumer Defensive":     14.0,
    "Industrials":            14.0,
    "Energy":                  6.0,
    "Communication Services": 12.0,
    "Utilities":              12.0,
    "Real Estate":            18.0,
    "Basic Materials":         8.0,
}


def compute_sotp(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fair value using Sum-of-the-Parts methodology.

    If segment data is available, values each segment separately.
    Otherwise, uses single-segment with industry-specific multiple.
    """
    result = {
        "model": "SOTP",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    ebitda = data.get("ebitda")
    sector = data.get("sector", "")
    industry = data.get("industry", "")

    if not current_price or not shares:
        result["confidence"] = "Insufficient Data"
        return result

    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0

    # Try to get segment data
    segments = _extract_segments(data)

    if segments and len(segments) > 1:
        # Multi-segment SOTP
        total_ev = 0
        segment_details = []

        for seg in segments:
            seg_name = seg.get("name", "Unknown")
            seg_revenue = seg.get("revenue", 0)
            seg_ebitda = seg.get("ebitda")

            # Estimate segment EBITDA if not available
            if seg_ebitda is None and seg_revenue > 0 and ebitda and data.get("revenue"):
                # Assume proportional EBITDA
                rev_share = seg_revenue / data["revenue"]
                seg_ebitda = ebitda * rev_share

            # Get appropriate multiple for this segment
            seg_mult = _get_segment_multiple(seg)

            if seg_ebitda and seg_ebitda > 0:
                seg_ev = seg_ebitda * seg_mult
                total_ev += seg_ev
                segment_details.append({
                    "name": seg_name,
                    "ebitda": seg_ebitda,
                    "multiple": seg_mult,
                    "implied_ev": round(seg_ev, 0),
                })

        if total_ev > 0:
            implied_equity = total_ev - total_debt + cash
            fair_value = implied_equity / shares if implied_equity > 0 else None

            if fair_value and fair_value > 0:
                result["fair_value"] = round(fair_value, 2)
                result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)
                result["confidence"] = "High" if len(segment_details) >= 2 else "Medium"

            result["details"] = {
                "method": "Multi-segment SOTP",
                "segments": segment_details,
                "total_ev": round(total_ev, 0),
                "num_segments": len(segment_details),
            }
            return result

    # Single-segment fallback using industry-specific multiple
    if ebitda and ebitda > 0:
        mult = INDUSTRY_MULTIPLES.get(industry,
               SECTOR_DEFAULT_EV_EBITDA.get(sector, 15.0))

        implied_ev = ebitda * mult
        implied_equity = implied_ev - total_debt + cash
        fair_value = implied_equity / shares if implied_equity > 0 else None

        if fair_value and fair_value > 0:
            result["fair_value"] = round(fair_value, 2)
            result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)
            result["confidence"] = "Medium"

        result["details"] = {
            "method": "Single-segment (industry multiple)",
            "industry": industry,
            "multiple_used": mult,
            "ebitda": ebitda,
        }
    else:
        result["confidence"] = "Insufficient Data"

    return result


def _extract_segments(data: Dict[str, Any]) -> List[Dict]:
    """
    Extract business segments from data.
    Yahoo Finance sometimes provides segment revenue breakdown.
    """
    segments = []

    # Check for segment data in the data dict
    raw_segments = data.get("business_segments") or data.get("segments")
    if raw_segments and isinstance(raw_segments, (list, dict)):
        if isinstance(raw_segments, dict):
            for name, info in raw_segments.items():
                seg = {"name": name}
                if isinstance(info, dict):
                    seg["revenue"] = info.get("revenue", 0)
                    seg["ebitda"] = info.get("ebitda")
                    seg["industry"] = info.get("industry", "")
                elif isinstance(info, (int, float)):
                    seg["revenue"] = info
                segments.append(seg)
        elif isinstance(raw_segments, list):
            segments = raw_segments

    return segments


def _get_segment_multiple(segment: Dict) -> float:
    """Get EV/EBITDA multiple for a business segment."""
    industry = segment.get("industry", "")
    if industry and industry in INDUSTRY_MULTIPLES:
        return INDUSTRY_MULTIPLES[industry]

    name = segment.get("name", "").lower()

    # Heuristic matching based on segment name
    name_multiples = {
        "cloud": 25.0,
        "aws": 25.0,
        "azure": 25.0,
        "saas": 22.0,
        "software": 22.0,
        "advertising": 18.0,
        "ads": 18.0,
        "hardware": 14.0,
        "devices": 14.0,
        "services": 14.0,
        "retail": 12.0,
        "streaming": 16.0,
        "gaming": 16.0,
        "search": 20.0,
        "fintech": 18.0,
        "payments": 18.0,
    }

    for keyword, mult in name_multiples.items():
        if keyword in name:
            return mult

    return 15.0  # Default
