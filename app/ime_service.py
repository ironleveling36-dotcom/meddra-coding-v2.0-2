"""
Enhanced IME (Important Medical Events) Service
- Loads IME data from Excel
- Fast lookup for term classification
- Handles both term names and IDs
"""
import os
import logging
from functools import lru_cache
import pandas as pd

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MEDDRA_DATA_DIR", os.path.join(HERE, "..", "data"))

# IME Excel file path (automatically detected or configured)
IME_FILE = os.path.join(DATA_DIR, "Important-medical-event-29_1.xlsx")
if not os.path.exists(IME_FILE):
    # Fallback to alternative names
    for alt_name in ["IME.xlsx", "ime_list.xlsx", "important_medical_events.xlsx"]:
        alt_path = os.path.join(DATA_DIR, alt_name)
        if os.path.exists(alt_path):
            IME_FILE = alt_path
            break


class IMEIndex:
    """Fast lookup index for Important Medical Events."""

    def __init__(self, excel_file: str | None = None):
        """Initialize IME index from Excel file."""
        self.ime_terms: dict[int, dict] = {}  # By term ID
        self.ime_names: set[str] = set()  # Lowercase term names
        self.total_loaded = 0
        
        if excel_file:
            self._load_from_excel(excel_file)
        else:
            self._load_from_excel(IME_FILE)

    def _load_from_excel(self, file_path: str):
        """Load IME terms from Excel file."""
        if not os.path.exists(file_path):
            logger.warning(f"IME file not found: {file_path}")
            return

        try:
            logger.info(f"Loading IME data from {file_path}...")
            
            # Read Excel with proper skiprows
            df = pd.read_excel(
                file_path,
                sheet_name='29.1 IME List',
                header=None,
                skiprows=15  # Skip metadata/header rows
            )
            
            # Process records
            # Columns: 0=ID, 1=Name, 2=SOC, 3=Description, 4=Flag, 5=Empty
            for _, row in df.iterrows():
                try:
                    term_id = int(row[0])
                    term_name = str(row[1]).strip()
                    soc = str(row[2]).strip() if pd.notna(row[2]) else ""
                    description = str(row[3]).strip() if pd.notna(row[3]) else ""
                    ime_flag = str(row[4]).strip() if pd.notna(row[4]) else ""
                    
                    # Check if this is an IME (marked with 'X')
                    if ime_flag == 'X':
                        self.ime_terms[term_id] = {
                            "term_id": term_id,
                            "name": term_name,
                            "soc": soc,
                            "description": description,
                            "is_ime": True,
                        }
                        self.ime_names.add(term_name.lower())
                        self.total_loaded += 1
                
                except (ValueError, TypeError) as e:
                    # Skip rows with invalid data
                    continue
            
            logger.info(f"✅ Loaded {self.total_loaded} IME terms")
            
        except Exception as e:
            logger.error(f"Failed to load IME data: {e}")

    def is_ime(self, term_id: int | str, term_name: str | None = None) -> bool:
        """Check if a term is an IME.
        
        Args:
            term_id: MedDRA term ID
            term_name: Optional term name for additional verification
        
        Returns:
            True if term is in IME list
        """
        try:
            tid = int(term_id)
            if tid in self.ime_terms:
                # Double-check with name if provided
                if term_name:
                    ime_record = self.ime_terms[tid]
                    return term_name.lower() in self.ime_names
                return True
        except (ValueError, TypeError):
            pass
        
        # Fallback: check by name only
        if term_name:
            return term_name.lower() in self.ime_names
        
        return False

    def get_ime_info(self, term_id: int | str) -> dict | None:
        """Get detailed IME information."""
        try:
            return self.ime_terms.get(int(term_id))
        except (ValueError, TypeError):
            return None

    def get_all_imes(self) -> list[dict]:
        """Get all IME terms."""
        return list(self.ime_terms.values())

    def count(self) -> int:
        """Get total IME count."""
        return self.total_loaded


# Global singleton
_ime_index: IMEIndex | None = None


def get_ime_index() -> IMEIndex:
    """Get or create the global IME index."""
    global _ime_index
    if _ime_index is None:
        _ime_index = IMEIndex()
    return _ime_index


def is_ime(term_id: int | str, term_name: str | None = None) -> bool:
    """Quick function to check if term is IME."""
    return get_ime_index().is_ime(term_id, term_name)


def ime_info(term_id: int | str) -> dict | None:
    """Get IME information."""
    return get_ime_index().get_ime_info(term_id)
