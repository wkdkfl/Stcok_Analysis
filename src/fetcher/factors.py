"""
Fama-French factor data & Damodaran datasets fetcher.
Used for factor exposure analysis and industry benchmarks.
"""

import pandas as pd
import numpy as np
import io
import zipfile
import requests
import streamlit as st
from typing import Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import FF_FACTORS_URL, FF_MOMENTUM_URL, CACHE_TTL


@st.cache_data(ttl=86400, show_spinner=False)  # cache 24h
def fetch_ff_factors() -> Optional[pd.DataFrame]:
    """
    Fetch Fama-French 5 factors + Momentum daily data.
    Returns DataFrame with columns: Mkt-RF, SMB, HML, RMW, CMA, Mom, RF
    Index = date.
    """
    try:
        ff5 = _download_ff_csv(FF_FACTORS_URL)
        mom = _download_ff_csv(FF_MOMENTUM_URL)

        if ff5 is None:
            return None

        # FF5 columns: Mkt-RF, SMB, HML, RMW, CMA, RF
        # Convert from percent to decimal
        ff5 = ff5 / 100.0

        if mom is not None:
            mom = mom / 100.0
            # Rename momentum column
            if len(mom.columns) >= 1:
                mom.columns = ["Mom"] + list(mom.columns[1:])
            ff5 = ff5.join(mom[["Mom"]], how="left")

        return ff5
    except Exception:
        return None


def _download_ff_csv(url: str) -> Optional[pd.DataFrame]:
    """Download and parse a Fama-French CSV from a zip URL."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            csv_name = [n for n in z.namelist() if n.endswith(".CSV") or n.endswith(".csv")]
            if not csv_name:
                return None
            with z.open(csv_name[0]) as f:
                content = f.read().decode("utf-8")

        # Find where daily data starts (skip header lines)
        lines = content.strip().split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and len(stripped.split(",")[0].strip()) == 8:
                start_idx = i
                break

        # Find where data ends (blank line or annual data starts)
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped or (stripped[0].isdigit() and len(stripped.split(",")[0].strip()) == 6):
                end_idx = i
                break

        data_text = "\n".join(lines[start_idx:end_idx])
        # Get header from line before start_idx
        header_line = ""
        for i in range(start_idx - 1, -1, -1):
            if lines[i].strip() and "," in lines[i]:
                header_line = lines[i].strip()
                break

        if header_line:
            data_text = header_line + "\n" + data_text

        df = pd.read_csv(io.StringIO(data_text))
        # First column is date
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col].astype(str).str.strip(), format="%Y%m%d",
                                       errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col)
        # Remove any unnamed columns
        df = df[[c for c in df.columns if "Unnamed" not in str(c)]]
        # Convert to float
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df
    except Exception:
        return None
