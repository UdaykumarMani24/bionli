"""
PDB + UniProt Structure Data Source
====================================
Fetches real structural biology data for a gene/protein:
  - Sequence length and mass  (UniProt)
  - Functional domains        (UniProt via InterPro)
  - AlphaFold model link      (AlphaFold DB)
  - Experimental PDB entries  (RCSB PDB search API)

Add to your data_sources.py by copy-pasting the PDBDataSource class
at the bottom, then register it in qa_engine.py and intent_router.py
as shown in INTEGRATION.md.
"""

import requests
import logging
import time
import os
import json
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PDBDataSource:
    """
    Fetches protein structure data from:
      - UniProt  (sequence length, mass, domains)
      - AlphaFold DB (predicted 3D model)
      - RCSB PDB (experimental crystal / cryo-EM structures)
    """

    UNIPROT_BASE   = "https://rest.uniprot.org"
    ALPHAFOLD_BASE = "https://alphafold.ebi.ac.uk/api/v4"
    PDB_SEARCH     = "https://search.rcsb.org/rcsbsearch/v2/query"
    PDB_ENTRY      = "https://data.rcsb.org/rest/v1/core/entry"

    # Hard-coded UniProt accessions for the most-queried genes
    # so we don't need an extra lookup round-trip
    KNOWN_ACCESSIONS = {
        'BRCA1': 'P38398', 'BRCA2': 'P51587', 'TP53': 'P04637',
        'EGFR':  'P00533', 'KRAS':  'P01116', 'PTEN': 'P60484',
        'MYC':   'P01106', 'BRAF':  'P15056', 'APC':  'P25054',
        'RB1':   'P06400', 'ERBB2': 'P04626', 'ALK':  'Q9UM73',
        'IDH1':  'O75874', 'IDH2':  'P48735', 'ATM':  'Q13315',
        'CHEK2': 'O96017', 'RAD51': 'Q06609', 'PARP1':'P09874',
        'INS':   'P01308', 'CFTR':  'P13569', 'APOE': 'P02649',
        'APP':   'P05067', 'HTT':   'P42858', 'SNCA': 'P37840',
        'DMD':   'P11532', 'JAK2':  'O60674', 'STAT3':'P40763',
    }

    def __init__(self):
        self.name       = "PDB"
        self.rate_limit = 0.5
        self._last_req  = 0.0
        self.cache_dir  = "data/cache/"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.stats      = {'queries': 0}

    # ── helpers ──────────────────────────────────────────────────────────

    def _wait(self):
        elapsed = time.time() - self._last_req
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_req = time.time()

    def _cache_path(self, key: str) -> str:
        safe = key.replace('/', '_').replace(':', '_')
        return os.path.join(self.cache_dir, f"pdb_{safe}.json")

    def _cache_get(self, key: str) -> Optional[str]:
        path = self._cache_path(key)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cached = json.load(f)
                if time.time() - cached.get('timestamp', 0) < 86400:
                    return cached['data']
            except Exception:
                pass
        return None

    def _cache_set(self, key: str, data: str):
        path = self._cache_path(key)
        try:
            with open(path, 'w') as f:
                json.dump({'timestamp': time.time(), 'data': data}, f)
        except Exception:
            pass

    def _get(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """GET with error handling — returns parsed JSON or None."""
        self._wait()
        try:
            h = {'User-Agent': 'BioNLI/2.0 (research; python-requests)',
                 'Accept':     'application/json'}
            if headers:
                h.update(headers)
            r = requests.get(url, params=params, headers=h, timeout=15)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"PDB source HTTP {r.status_code} for {url}")
        except Exception as e:
            logger.warning(f"PDB source request failed: {e}")
        return None

    # ── UniProt accession lookup ─────────────────────────────────────────

    def _get_accession(self, gene: str) -> Optional[str]:
        """Return UniProt accession for a human gene symbol."""
        if gene in self.KNOWN_ACCESSIONS:
            return self.KNOWN_ACCESSIONS[gene]

        data = self._get(
            f"{self.UNIPROT_BASE}/uniprotkb/search",
            params={'query':  f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
                    'format': 'json', 'size': 1,
                    'fields': 'accession'}
        )
        if data and data.get('results'):
            return data['results'][0].get('primaryAccession')
        return None

    # ── UniProt structure fields ─────────────────────────────────────────

    def _fetch_uniprot_structure(self, accession: str) -> dict:
        """
        Fetch sequence length, mass, and domain annotations from UniProt.
        Returns a dict with keys: length, mass, domains, isoforms
        """
        fields = 'sequence,mass,ft_domain,ft_region,cc_domain,xref_pdb'
        data   = self._get(
            f"{self.UNIPROT_BASE}/uniprotkb/{accession}",
            params={'format': 'json', 'fields': fields}
        )
        if not data:
            return {}

        result = {}

        # Sequence length
        seq = data.get('sequence', {})
        if seq.get('length'):
            result['length'] = seq['length']
        if seq.get('molWeight'):
            result['mass'] = round(seq['molWeight'] / 1000, 1)  # kDa

        # Domain annotations from feature table
        domains = []
        for feature in data.get('features', []):
            ftype = feature.get('type', '')
            if ftype in ('Domain', 'Region', 'Motif', 'Zinc finger',
                         'DNA binding', 'Coiled coil'):
                desc     = feature.get('description', '')
                start    = feature.get('location', {}).get('start', {}).get('value', '')
                end      = feature.get('location', {}).get('end', {}).get('value', '')
                if desc:
                    pos = f" ({start}–{end} aa)" if start and end else ""
                    domains.append(f"{desc}{pos}")

        # Also check cc_domain comment
        for comment in data.get('comments', []):
            if comment.get('commentType') == 'DOMAIN':
                for txt in comment.get('texts', []):
                    val = txt.get('value', '')
                    if val and val not in domains:
                        domains.append(val[:150])

        result['domains'] = domains[:8]  # cap at 8

        # Count experimental PDB cross-references
        pdb_refs = [x for x in data.get('uniProtKBCrossReferences', [])
                    if x.get('database') == 'PDB']
        result['pdb_count'] = len(pdb_refs)
        result['pdb_ids']   = [x.get('id') for x in pdb_refs[:3]]

        return result

    # ── AlphaFold ────────────────────────────────────────────────────────

    def _fetch_alphafold(self, accession: str) -> Optional[str]:
        """Return AlphaFold model URL if available."""
        data = self._get(f"{self.ALPHAFOLD_BASE}/prediction/{accession}")
        if data and isinstance(data, list) and data:
            entry = data[0]
            return entry.get('pdbUrl') or entry.get('cifUrl')
        return None

    # ── Main query ───────────────────────────────────────────────────────

    def query(self, params: Dict) -> str:
        gene = params.get('gene', '').upper().strip()
        if not gene:
            return ""

        self.stats['queries'] += 1

        cached = self._cache_get(gene)
        if cached:
            return cached

        # 1. Get UniProt accession
        accession = self._get_accession(gene)
        if not accession:
            return f"No UniProt entry found for '{gene}'."

        logger.info(f"PDB source: {gene} → UniProt {accession}")

        # 2. Fetch structure fields from UniProt
        uni = self._fetch_uniprot_structure(accession)

        # 3. Fetch AlphaFold model link
        af_url = self._fetch_alphafold(accession)

        # 4. Build output string
        lines = []
        lines.append(f"STRUCTURE_DATA_START")   # marker for formatter
        lines.append(f"Gene: {gene}")
        lines.append(f"UniProt: {accession}")

        if uni.get('length'):
            lines.append(f"Sequence_Length: {uni['length']} amino acids")
        if uni.get('mass'):
            lines.append(f"Molecular_Mass: {uni['mass']} kDa")

        if uni.get('domains'):
            lines.append(f"Domains: {' | '.join(uni['domains'])}")

        if uni.get('pdb_count', 0) > 0:
            lines.append(f"Experimental_Structures: {uni['pdb_count']} structures in PDB")
            if uni.get('pdb_ids'):
                ids = ', '.join(uni['pdb_ids'])
                lines.append(f"PDB_IDs: {ids}")
        else:
            lines.append(f"Experimental_Structures: No experimental structures in PDB")

        if af_url:
            lines.append(f"AlphaFold_URL: {af_url}")
        lines.append(
            f"AlphaFold_Page: https://alphafold.ebi.ac.uk/entry/{accession}"
        )
        lines.append(
            f"UniProt_Page: https://www.uniprot.org/uniprot/{accession}"
        )
        lines.append(f"STRUCTURE_DATA_END")

        output = "\n".join(lines)
        self._cache_set(gene, output)
        return output

    def get_stats(self) -> dict:
        return {'name': self.name, **self.stats}
