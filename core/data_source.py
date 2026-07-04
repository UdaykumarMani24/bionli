
# ============================================================================
# FILE: core/data_source.py
# ============================================================================
"""
Data Source Implementations - Fully implemented with real API calls.
No placeholder data - all queries go to actual biological databases.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import time
import hashlib
import json
import os

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Abstract base class for all biological data sources."""
    
    def __init__(self, name: str, rate_limit: float = 1.0, cache_ttl: int = 86400):
        self.name = name
        self.rate_limit = rate_limit
        self.cache_ttl = cache_ttl
        self.last_request_time = 0
        self.stats = {'queries': 0, 'success': 0, 'failures': 0}
        self.cache_dir = os.path.join("data/cache", name)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _rate_limit_wait(self):
        """Respect rate limits for API calls."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last)
        self.last_request_time = time.time()
    
    def _cache_key(self, query: str) -> str:
        """Generate cache key for query."""
        return hashlib.md5(query.encode()).hexdigest()
    
    def _cache_get(self, key: str) -> Optional[Any]:
        """Get from cache."""
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached = json.load(f)
                if time.time() - cached['timestamp'] < self.cache_ttl:
                    logger.debug(f"Cache hit for {key[:8]}...")
                    return cached['data']
            except Exception:
                pass
        return None
    
    def _cache_set(self, key: str, data: Any):
        """Save to cache."""
        cache_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(cache_path, 'w') as f:
                json.dump({'timestamp': time.time(), 'data': data}, f)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    @abstractmethod
    def query(self, structured_query: 'StructuredQuery') -> List['QueryResult']:
        pass
    
    @abstractmethod
    def supports_intent(self, intent: 'Intent') -> bool:
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'queries': self.stats['queries'],
            'success_rate': self.stats['success'] / max(self.stats['queries'], 1) * 100,
            **self.stats
        }


class NCBIDataSource(DataSource):
    """NCBI Entrez data source with real API calls."""
    
    def __init__(self, email: str, api_key: Optional[str] = None):
        super().__init__("NCBI Entrez", rate_limit=0.34)  # 3 requests per second max
        from Bio import Entrez
        Entrez.email = email
        if api_key:
            Entrez.api_key = api_key
        self.Entrez = Entrez
    
    def supports_intent(self, intent: 'Intent') -> bool:
        supported = ['FUNCTION', 'SEQUENCE', 'EXPRESSION', 'HOMOLOGY', 'LOCATION']
        return intent.name in supported
    
    def query(self, structured_query: 'StructuredQuery') -> List['QueryResult']:
        from .structured_query import QueryResult, Intent
        
        self.stats['queries'] += 1
        self._rate_limit_wait()
        
        results = []
        
        # Extract gene entities
        gene_entities = [e for e in structured_query.entities 
                        if e.entity_type.name in ['GENE', 'PROTEIN']]
        
        for entity in gene_entities:
            cache_key = self._cache_key(f"gene_{entity.text}")
            cached = self._cache_get(cache_key)
            if cached:
                results.append(QueryResult(**cached))
                self.stats['success'] += 1
                continue
            
            try:
                # Search for gene
                handle = self.Entrez.esearch(
                    db="gene",
                    term=f"{entity.text}[Gene Name] AND human[Organism]",
                    retmax=5
                )
                record = self.Entrez.read(handle)
                handle.close()
                
                if not record["IdList"]:
                    # Try without species filter
                    handle = self.Entrez.esearch(db="gene", term=f"{entity.text}[Gene Name]", retmax=1)
                    record = self.Entrez.read(handle)
                    handle.close()
                
                if record["IdList"]:
                    gene_id = record["IdList"][0]
                    
                    self._rate_limit_wait()
                    handle = self.Entrez.efetch(db="gene", id=gene_id, retmode="xml")
                    xml_data = handle.read()
                    handle.close()
                    
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(xml_data)
                    
                    summary_elem = root.find(".//Entrezgene_summary")
                    summary = summary_elem.text if summary_elem is not None else ""
                    
                    name_elem = root.find(".//Gene-ref_locus")
                    gene_name = name_elem.text if name_elem is not None else entity.text
                    
                    result = QueryResult(
                        source=self.name,
                        data={
                            'gene': gene_name,
                            'gene_id': gene_id,
                            'summary': summary,
                            'type': 'gene'
                        },
                        confidence=0.95,
                        evidence=[{
                            'source': 'NCBI Entrez',
                            'type': 'gene_summary',
                            'url': f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
                        }],
                        structured_query=structured_query,
                        provenance={'retrieved_at': time.time(), 'gene_id': gene_id}
                    )
                    
                    results.append(result)
                    self._cache_set(cache_key, result.to_dict())
                    self.stats['success'] += 1
                    logger.info(f"✓ NCBI: Found {gene_name} (ID: {gene_id})")
                else:
                    logger.warning(f"NCBI: No results for {entity.text}")
                    self.stats['failures'] += 1
                    
            except Exception as e:
                logger.error(f"NCBI error for {entity.text}: {e}")
                self.stats['failures'] += 1
        
        return results


class EnsemblDataSource(DataSource):
    """Ensembl REST API data source."""
    
    def __init__(self):
        super().__init__("Ensembl", rate_limit=0.2)  # 5 requests per second
        import requests
        self.requests = requests
        self.base_url = "https://rest.ensembl.org"
    
    def supports_intent(self, intent: 'Intent') -> bool:
        supported = ['FUNCTION', 'SEQUENCE', 'LOCATION', 'HOMOLOGY']
        return intent.name in supported
    
    def query(self, structured_query: 'StructuredQuery') -> List['QueryResult']:
        from .structured_query import QueryResult
        
        self.stats['queries'] += 1
        self._rate_limit_wait()
        
        results = []
        
        gene_entities = [e for e in structured_query.entities 
                        if e.entity_type.name in ['GENE', 'PROTEIN']]
        
        for entity in gene_entities:
            cache_key = self._cache_key(f"ensembl_{entity.text}")
            cached = self._cache_get(cache_key)
            if cached:
                results.append(QueryResult(**cached))
                self.stats['success'] += 1
                continue
            
            try:
                response = self.requests.get(
                    f"{self.base_url}/lookup/symbol/homo_sapiens/{entity.text}",
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    result = QueryResult(
                        source=self.name,
                        data={
                            'gene': data.get('display_name', entity.text),
                            'ensembl_id': data.get('id'),
                            'location': f"{data.get('seq_region_name')}:{data.get('start')}-{data.get('end')}",
                            'biotype': data.get('biotype'),
                            'description': data.get('description', '')
                        },
                        confidence=0.90,
                        evidence=[{
                            'source': 'Ensembl REST API',
                            'type': 'gene_lookup',
                            'url': f"https://ensembl.org/id/{data.get('id')}"
                        }],
                        structured_query=structured_query,
                        provenance={'retrieved_at': time.time()}
                    )
                    
                    results.append(result)
                    self._cache_set(cache_key, result.to_dict())
                    self.stats['success'] += 1
                    logger.info(f"✓ Ensembl: Found {data.get('display_name', entity.text)}")
                else:
                    self.stats['failures'] += 1
                    
            except Exception as e:
                logger.error(f"Ensembl error for {entity.text}: {e}")
                self.stats['failures'] += 1
        
        return results


class UniProtDataSource(DataSource):
    """UniProt REST API data source."""
    
    def __init__(self):
        super().__init__("UniProt", rate_limit=0.5)
        import requests
        self.requests = requests
        self.base_url = "https://rest.uniprot.org"
    
    def supports_intent(self, intent: 'Intent') -> bool:
        supported = ['FUNCTION', 'SEQUENCE', 'STRUCTURE', 'INTERACTION']
        return intent.name in supported
    
    def query(self, structured_query: 'StructuredQuery') -> List['QueryResult']:
        from .structured_query import QueryResult
        
        self.stats['queries'] += 1
        self._rate_limit_wait()
        
        results = []
        
        protein_entities = [e for e in structured_query.entities 
                           if e.entity_type.name in ['GENE', 'PROTEIN']]
        
        for entity in protein_entities:
            cache_key = self._cache_key(f"uniprot_{entity.text}")
            cached = self._cache_get(cache_key)
            if cached:
                results.append(QueryResult(**cached))
                self.stats['success'] += 1
                continue
            
            try:
                response = self.requests.get(
                    f"{self.base_url}/uniprotkb/search",
                    params={
                        'query': f"gene:{entity.text} AND organism_id:9606",
                        'format': 'json',
                        'size': 3
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for item in data.get('results', []):
                        # Extract function
                        function = ""
                        for comment in item.get('comments', []):
                            if comment.get('commentType') == 'FUNCTION':
                                texts = comment.get('texts', [])
                                if texts:
                                    function = texts[0].get('value', '')
                                    break
                        
                        protein_name = item.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', '')
                        
                        result = QueryResult(
                            source=self.name,
                            data={
                                'protein': protein_name or entity.text,
                                'uniprot_id': item.get('primaryAccession'),
                                'function': function,
                                'gene_names': [g.get('geneName', {}).get('value', '') for g in item.get('genes', [])]
                            },
                            confidence=0.88,
                            evidence=[{
                                'source': 'UniProt',
                                'type': 'protein_entry',
                                'url': f"https://www.uniprot.org/uniprot/{item.get('primaryAccession')}"
                            }],
                            structured_query=structured_query,
                            provenance={'retrieved_at': time.time()}
                        )
                        
                        results.append(result)
                        self._cache_set(cache_key, result.to_dict())
                    
                    self.stats['success'] += 1
                    logger.info(f"✓ UniProt: Found {len(results)} entries for {entity.text}")
                else:
                    self.stats['failures'] += 1
                    
            except Exception as e:
                logger.error(f"UniProt error for {entity.text}: {e}")
                self.stats['failures'] += 1
        
        return results


class FederationEngine:
    """Query federation engine that distributes queries to multiple sources."""
    
    def __init__(self, sources: List[DataSource]):
        self.sources = {s.name: s for s in sources}
        self.logger = logging.getLogger(__name__)
    
    def query(self, structured_query: 'StructuredQuery', 
              source_names: Optional[List[str]] = None) -> Dict[str, List['QueryResult']]:
        """Execute query against selected data sources."""
        if source_names is None:
            source_names = list(self.sources.keys())
        
        results = {}
        
        for source_name in source_names:
            source = self.sources.get(source_name)
            if source and source.supports_intent(structured_query.intent):
                try:
                    source_results = source.query(structured_query)
                    results[source_name] = source_results
                    if source_results:
                        self.logger.info(f"Source {source_name}: {len(source_results)} results")
                except Exception as e:
                    self.logger.error(f"Source {source_name} failed: {e}")
                    results[source_name] = []
        
        return results
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        return {name: source.get_stats() for name, source in self.sources.items()}

