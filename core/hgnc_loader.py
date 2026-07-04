"""
HGNC Gene Loader - Publication Quality
Loads official human gene symbols from HGNC (Human Gene Nomenclature Committee)
Source: https://www.genenames.org/
"""

import os
import logging
import urllib.request
import pandas as pd
from typing import Set, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class HGNCGeneLoader:
    """
    Loads official HGNC-approved human gene symbols.
    This is the authoritative source for human gene nomenclature.
    """
    
    # CORRECT URL from HGNC downloads page (updated March 2026)
    HGNC_URL = "https://storage.googleapis.com/public-download-files/hgnc/hgnc_complete_set.txt"
    
    # Alternative: JSON format
    HGNC_JSON_URL = "https://storage.googleapis.com/public-download-files/hgnc/hgnc_complete_set.json"
    
    # Explicit mapping for common genes and their aliases
    EXPLICIT_MAPPING = {
        # Tumor suppressors
        'tp53': 'TP53',
        'p53': 'TP53',
        'brca1': 'BRCA1',
        'brca2': 'BRCA2',
        'brca': 'BRCA1',
        'pten': 'PTEN',
        'rb1': 'RB1',
        'apc': 'APC',
        
        # Oncogenes
        'egfr': 'EGFR',
        'kras': 'KRAS',
        'nras': 'NRAS',
        'hras': 'HRAS',
        'myc': 'MYC',
        'braf': 'BRAF',
        
        # Metabolic/endocrine
        'insulin': 'INS',
        'ins': 'INS',
        'cftr': 'CFTR',
        'apoe': 'APOE',
        'app': 'APP',
        
        # Neurological
        'snca': 'SNCA',
        'htt': 'HTT',
        'dmd': 'DMD',
        
        # Growth factors
        'vegf': 'VEGFA',
        'pdgfra': 'PDGFRA',
        'kit': 'KIT',
        
        # Cell cycle & DNA repair
        'atm': 'ATM',
        'atr': 'ATR',
        'chek1': 'CHEK1',
        'chek2': 'CHEK2',
        'rad51': 'RAD51',
        'parp1': 'PARP1',
        'mdm2': 'MDM2',
        
        # Immune
        'jak2': 'JAK2',
        'stat3': 'STAT3',
        'il6': 'IL6',
        'tnf': 'TNF',
    }
    
    def __init__(self, cache_dir: str = "data/hgnc/", force_download: bool = False):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "hgnc_complete_set.txt")
        
        self.genes: Set[str] = set()
        self.synonyms: Dict[str, str] = {}
        self.previous_symbols: Dict[str, str] = {}
        self.version: Optional[str] = None
        self.load_date: Optional[str] = None
        self.total_genes: int = 0
        
        self._load(force_download)
    
    def _load(self, force_download: bool = False):
        """Load HGNC data from file or download."""
        self.load_date = datetime.now().isoformat()
        
        if not os.path.exists(self.cache_file) or force_download:
            logger.info("Downloading HGNC gene list from official source...")
            success = self._download_file(self.HGNC_URL)
            if not success:
                logger.error("Failed to download HGNC file")
                self._load_fallback()
                return
        
        try:
            df = None
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    df = pd.read_csv(self.cache_file, sep='\t', encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if df is None:
                raise ValueError("Could not read file with any encoding")
            
            symbol_col = None
            for col in ['symbol', 'Approved symbol', 'gd_app_sym']:
                if col in df.columns:
                    symbol_col = col
                    break
            
            if symbol_col is None:
                symbol_col = df.columns[0]
            
            self.genes = set(df[symbol_col].dropna().astype(str).tolist())
            self.total_genes = len(self.genes)
            
            prev_col = None
            for col in ['prev_symbol', 'Previous symbols', 'gd_prev_sym']:
                if col in df.columns:
                    prev_col = col
                    break
            
            alias_col = None
            for col in ['alias_symbol', 'Synonyms', 'gd_aliases']:
                if col in df.columns:
                    alias_col = col
                    break
            
            for _, row in df.iterrows():
                symbol = row.get(symbol_col)
                if pd.notna(symbol):
                    symbol = str(symbol)
                    
                    if prev_col:
                        prev_symbols = row.get(prev_col, '')
                        if pd.notna(prev_symbols):
                            for prev in str(prev_symbols).split('|'):
                                if prev and prev.strip():
                                    self.previous_symbols[prev.strip().lower()] = symbol
                    
                    if alias_col:
                        aliases = row.get(alias_col, '')
                        if pd.notna(aliases):
                            for alias in str(aliases).split('|'):
                                if alias and alias.strip():
                                    self.synonyms[alias.strip().lower()] = symbol
            
            # Add explicit mappings to synonyms
            for alias, canonical in self.EXPLICIT_MAPPING.items():
                if alias not in self.synonyms:
                    self.synonyms[alias] = canonical
            
            self.version = f"HGNC_{self.load_date[:10]}"
            
            logger.info(f"✓ Loaded {self.total_genes:,} HGNC-approved gene symbols")
            logger.info(f"  - Version: {self.version}")
            logger.info(f"  - Synonyms: {len(self.synonyms)}")
            logger.info(f"  - Previous symbols: {len(self.previous_symbols)}")
            
        except Exception as e:
            logger.error(f"Failed to parse HGNC file: {e}")
            self._load_fallback()
    
    def _download_file(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'BioNLI/2.0'})
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(self.cache_file, 'wb') as f:
                    f.write(response.read())
            logger.info(f"✓ Downloaded from {url}")
            return True
        except Exception as e:
            logger.warning(f"Download failed: {e}")
            return False
    
    def _load_fallback(self):
        logger.warning("Using fallback critical gene list")
        
        critical_genes = {
            'TP53', 'BRCA1', 'BRCA2', 'EGFR', 'KRAS', 'NRAS', 'HRAS', 'BRAF', 'PIK3CA', 'PTEN',
            'MYC', 'MYCN', 'CCND1', 'CDKN2A', 'RB1', 'APC', 'CTNNB1', 'SMAD4', 'VHL', 'NF1', 'NF2',
            'ERBB2', 'MET', 'ALK', 'ROS1', 'RET', 'FGFR1', 'FGFR2', 'FGFR3', 'PDGFRA', 'KIT',
            'IDH1', 'IDH2', 'NTRK1', 'NTRK2', 'NTRK3',
            'INS', 'CFTR', 'APOE', 'LDLR', 'HMGCR', 'PPARG', 'GCK', 'HNF1A', 'HNF4A',
            'APP', 'SNCA', 'HTT', 'MAPT', 'LRRK2', 'PARK2', 'PINK1', 'GRN', 'C9orf72',
            'DMD', 'MYH7', 'MYBPC3', 'TNNT2', 'TNNI3', 'LMNA', 'SCN5A', 'KCNQ1', 'KCNH2',
            'JAK2', 'STAT3', 'STAT1', 'IL6', 'TNF', 'IFNG', 'CD4', 'CD8A',
            'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'PARP1', 'MDM2', 'MDM4',
            'NOTCH1', 'NOTCH2', 'WNT1', 'SHH', 'SOX2', 'OCT4', 'NANOG'
        }
        
        self.genes = critical_genes
        self.total_genes = len(critical_genes)
        self.version = "fallback"
        
        for alias, canonical in self.EXPLICIT_MAPPING.items():
            if canonical in self.genes:
                self.synonyms[alias] = canonical
    
    def is_gene(self, term: str) -> bool:
        return term.upper() in self.genes
    
    # ========== KEEP ONLY THIS get_canonical METHOD ==========
    # DELETE THE DUPLICATE ONE AT THE END OF THE FILE
    def get_canonical(self, term: str) -> Optional[str]:
        """
        Get canonical HGNC symbol for a term.
        This method is CRITICAL for correct gene mapping.
        """
        term_lower = term.lower().strip()
        
        # First check explicit mapping (highest priority)
        if term_lower in self.EXPLICIT_MAPPING:
            canonical = self.EXPLICIT_MAPPING[term_lower]
            logger.debug(f"Explicit mapping: {term} → {canonical}")
            return canonical
        
        # Check if it's already an approved symbol
        term_upper = term.upper()
        if term_upper in self.genes:
            return term_upper
        
        # Check synonyms
        if term_lower in self.synonyms:
            canonical = self.synonyms[term_lower]
            logger.debug(f"Synonym mapping: {term} → {canonical}")
            return canonical
        
        # Check previous symbols
        if term_lower in self.previous_symbols:
            canonical = self.previous_symbols[term_lower]
            logger.debug(f"Previous symbol mapping: {term} → {canonical}")
            return canonical
        
        logger.debug(f"No canonical symbol found for: {term}")
        return None
    # ========== END OF get_canonical ==========
    
    def search(self, term: str) -> list:
        term_upper = term.upper()
        matches = []
        for gene in self.genes:
            if term_upper in gene or gene in term_upper:
                matches.append(gene)
        return matches[:10]
    
    def get_stats(self) -> dict:
        return {
            'total_genes': self.total_genes,
            'synonyms': len(self.synonyms),
            'previous_symbols': len(self.previous_symbols),
            'version': self.version,
            'load_date': self.load_date,
            'source': 'HGNC (https://www.genenames.org)'
        }