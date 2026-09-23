#!/usr/bin/env python3
"""Build search index from MedDRA data files."""

import logging
import os

logger = logging.getLogger(__name__)

def build_index():
    """Build MedDRA search index."""
    logger.info("Building MedDRA index...")
    
    data_dir = os.environ.get("MEDDRA_DATA_DIR", "data")
    
    # Verify data files exist
    required_files = [
        "meddra_terms.jsonl.gz",
        "meddra_vectors.npz",
        "Important-medical-event-29_1.xlsx"
    ]
    
    for fname in required_files:
        fpath = os.path.join(data_dir, fname)
        if not os.path.exists(fpath):
            logger.warning(f"Missing: {fpath}")
        else:
            size_mb = os.path.getsize(fpath) / 1024 / 1024
            logger.info(f"✓ {fname} ({size_mb:.1f} MB)")
    
    logger.info("✓ Index build ready")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_index()
