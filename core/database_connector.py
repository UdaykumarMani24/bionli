import requests
import json
from typing import Dict, List, Any
import time

class RealDatabaseConnector:
    """Simplified database connector using reliable APIs only"""
    
    def __init__(self):
        self.api_endpoints = {
            'ncbi_gene': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            'ncbi_summary': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            'ensembl': 'https://rest.ensembl.org/'
        }
    
    def query_ncbi_gene(self, gene_name: str, organism: str = "human") -> List[Dict[str, Any]]:
        """Query NCBI Gene database - RELIABLE"""
        try:
            print(f"🔍 Querying NCBI for gene: {gene_name}")
            
            # Search for gene
            search_params = {
                'db': 'gene',
                'term': f"{gene_name}[Gene Name] AND {organism}[Organism]",
                'retmode': 'json',
                'retmax': 3
            }
            
            response = requests.get(self.api_endpoints['ncbi_gene'], params=search_params, timeout=10)
            data = response.json()
            
            gene_ids = data.get('esearchresult', {}).get('idlist', [])
            if not gene_ids:
                return [{
                    'gene_id': 'Not found in NCBI',
                    'name': gene_name,
                    'description': f'Gene {gene_name} not found in NCBI database',
                    'source': 'NCBI Gene',
                    'status': 'not_found'
                }]
            
            # Get gene summaries
            summary_params = {
                'db': 'gene',
                'id': ','.join(gene_ids),
                'retmode': 'json'
            }
            
            summary_response = requests.get(self.api_endpoints['ncbi_summary'], params=summary_params, timeout=10)
            summary_data = summary_response.json()
            
            results = []
            for gene_id in gene_ids:
                if gene_id in summary_data['result']:
                    gene_info = summary_data['result'][gene_id]
                    
                    # Create comprehensive result
                    result = {
                        'gene_id': gene_id,
                        'symbol': gene_info.get('name', ''),
                        'name': gene_info.get('description', ''),
                        'summary': gene_info.get('summary', 'No summary available'),
                        'organism': gene_info.get('organism', {}).get('scientificname', 'Homo sapiens'),
                        'chromosome': gene_info.get('chromosome', 'Unknown'),
                        'map_location': gene_info.get('maplocation', ''),
                        'function': self._extract_function(gene_info),
                        'source': 'NCBI Gene',
                        'status': 'success'
                    }
                    
                    # Clean up empty fields
                    result = {k: v for k, v in result.items() if v}
                    results.append(result)
            
            print(f"✅ Found {len(results)} results from NCBI")
            return results
            
        except Exception as e:
            print(f"❌ NCBI query error: {e}")
            return [{
                'error': f'NCBI service temporarily unavailable',
                'gene': gene_name,
                'source': 'NCBI Gene',
                'status': 'error',
                'suggestion': 'Try again in a moment'
            }]
    
    def query_ensembl(self, gene_name: str, species: str = "human") -> List[Dict[str, Any]]:
        """Query Ensembl REST API - RELIABLE"""
        try:
            print(f"🔍 Querying Ensembl for gene: {gene_name}")
            
            # Search for gene
            search_url = f"{self.api_endpoints['ensembl']}xrefs/symbol/{species}/{gene_name}"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return [{
                    'gene_id': 'Not found in Ensembl',
                    'symbol': gene_name,
                    'name': f'Gene {gene_name} not found in Ensembl',
                    'source': 'Ensembl',
                    'status': 'not_found'
                }]
            
            data = response.json()
            if not data:
                return []
            
            results = []
            for item in data[:2]:  # Limit to first 2 results
                gene_id = item.get('id')
                
                # Get detailed gene info
                gene_url = f"{self.api_endpoints['ensembl']}lookup/id/{gene_id}"
                gene_response = requests.get(gene_url, headers=headers, timeout=10)
                
                if gene_response.status_code == 200:
                    gene_data = gene_response.json()
                    
                    result = {
                        'gene_id': gene_id,
                        'symbol': gene_data.get('display_name', ''),
                        'name': gene_data.get('description', 'No description available'),
                        'biotype': gene_data.get('biotype', ''),
                        'chromosome': gene_data.get('seq_region_name', ''),
                        'start': gene_data.get('start', ''),
                        'end': gene_data.get('end', ''),
                        'strand': gene_data.get('strand', ''),
                        'source': 'Ensembl',
                        'status': 'success'
                    }
                    
                    # Clean up empty fields
                    result = {k: v for k, v in result.items() if v}
                    results.append(result)
            
            print(f"✅ Found {len(results)} results from Ensembl")
            return results
            
        except Exception as e:
            print(f"❌ Ensembl query error: {e}")
            return [{
                'error': f'Ensembl service temporarily unavailable',
                'gene': gene_name,
                'source': 'Ensembl',
                'status': 'error'
            }]
    
    def _extract_function(self, gene_info: Dict) -> str:
        """Extract functional information from gene data"""
        summary = gene_info.get('summary', '')
        if summary and len(summary) > 50:
            # Return first 200 characters of summary as function
            return summary[:200] + '...' if len(summary) > 200 else summary
        return "Functional information not available in summary"

    def query_homology(self, gene_name: str, target_species: str = "mouse") -> List[Dict[str, Any]]:
        """Query for gene homologs across species"""
        try:
            print(f"🔍 Searching for {target_species} homolog of {gene_name}")
            
            # Known homolog mappings for common genes
            homolog_database = {
                'TP53': {'mouse': 'Trp53', 'rat': 'Trp53', 'human': 'TP53'},
                'BRCA1': {'mouse': 'Brca1', 'rat': 'Brca1', 'human': 'BRCA1'},
                'BRCA2': {'mouse': 'Brca2', 'rat': 'Brca2', 'human': 'BRCA2'},
                'EGFR': {'mouse': 'Egfr', 'rat': 'Egfr', 'human': 'EGFR'},
                'MYC': {'mouse': 'Myc', 'rat': 'Myc', 'human': 'MYC'},
                'KRAS': {'mouse': 'Kras', 'rat': 'Kras', 'human': 'KRAS'},
                'AKT1': {'mouse': 'Akt1', 'rat': 'Akt1', 'human': 'AKT1'},
                'PTEN': {'mouse': 'Pten', 'rat': 'Pten', 'human': 'PTEN'},
                'VEGF': {'mouse': 'Vegfa', 'rat': 'Vegfa', 'human': 'VEGFA'},
                'INS': {'mouse': 'Ins1', 'rat': 'Ins', 'human': 'INS'},
                'HEMOGLOBIN': {'mouse': 'Hbb', 'rat': 'Hbb', 'human': 'HBB'}
            }
            
            # Check if we have known homolog
            if gene_name.upper() in homolog_database and target_species in homolog_database[gene_name.upper()]:
                homolog_name = homolog_database[gene_name.upper()][target_species]
                
                # Get information about both original and homolog
                original_results = self.query_ncbi_gene(gene_name, "human")
                homolog_results = self.query_ncbi_gene(homolog_name, target_species)
                
                results = []
                
                # Add original gene info
                for result in original_results:
                    if result.get('status') == 'success':
                        result['homology_note'] = f'Original human gene'
                        result['query_type'] = 'homology_reference'
                        results.append(result)
                
                # Add homolog info
                for result in homolog_results:
                    if result.get('status') == 'success':
                        result['homology_note'] = f'{target_species} homolog of {gene_name}'
                        result['original_gene'] = gene_name
                        result['homology_relationship'] = 'ortholog'
                        result['query_type'] = 'homology_result'
                        results.append(result)
                
                if results:
                    return results
            
            # If no known homolog, provide guidance
            return [{
                'query_type': 'homology_guidance',
                'original_gene': gene_name,
                'target_species': target_species,
                'message': f'Use specialized databases for detailed homology analysis',
                'recommended_tools': ['Ensembl Compare', 'NCBI Homologene', 'OrthoDB'],
                'direct_links': [
                    f'https://www.ncbi.nlm.nih.gov/homologene?term={gene_name}',
                    f'https://useast.ensembl.org/Homo_sapiens/Gene/Compara_Homolog?g={gene_name}'
                ],
                'common_homologs': [
                    'TP53 → Trp53 (mouse)',
                    'BRCA1 → Brca1 (mouse)', 
                    'EGFR → Egfr (mouse)',
                    'Use gene symbols in uppercase for best results'
                ],
                'source': 'Homology Database'
            }]
            
        except Exception as e:
            print(f"❌ Homology query error: {e}")
            return [{
                'error': f'Homology service error',
                'gene': gene_name,
                'target_species': target_species,
                'query_type': 'homology',
                'status': 'error'
            }]

    def handle_sequence_query(self, gene_name: str) -> List[Dict[str, Any]]:
        """Handle sequence queries"""
        try:
            print(f"🔍 Getting sequence information for: {gene_name}")
            
            # First get basic gene info
            gene_results = self.query_ncbi_gene(gene_name)
            
            results = []
            for result in gene_results:
                if result.get('status') == 'success':
                    # Add sequence-specific information
                    result['sequence_info'] = {
                        'available': 'Full sequences available via NCBI Nucleotide database',
                        'direct_link': f'https://www.ncbi.nlm.nih.gov/nucleotide/?term={gene_name}[gene]',
                        'types': ['Genomic DNA', 'mRNA', 'Protein sequence'],
                        'recommended_action': 'Use NCBI Nucleotide database for complete sequences'
                    }
                    result['query_type'] = 'sequence'
                results.append(result)
            
            if not any(r.get('status') == 'success' for r in results):
                # If gene not found, provide sequence guidance
                results.append({
                    'query_type': 'sequence_guidance',
                    'gene': gene_name,
                    'message': f'Sequence data for {gene_name}',
                    'sequence_sources': ['NCBI Nucleotide', 'Ensembl', 'UCSC Genome Browser'],
                    'direct_links': [
                        f'https://www.ncbi.nlm.nih.gov/nucleotide/?term={gene_name}',
                        f'https://useast.ensembl.org/Homo_sapiens/Gene/Summary?g={gene_name}'
                    ],
                    'common_sequences': [
                        'For insulin: https://www.ncbi.nlm.nih.gov/nucleotide/NM_000207',
                        'For TP53: https://www.ncbi.nlm.nih.gov/nucleotide/NM_000546',
                        'For BRCA1: https://www.ncbi.nlm.nih.gov/nucleotide/NM_007294'
                    ],
                    'source': 'Sequence Database'
                })
            
            return results
            
        except Exception as e:
            print(f"❌ Sequence query error: {e}")
            return [{
                'error': f'Sequence service error',
                'gene': gene_name,
                'query_type': 'sequence',
                'status': 'error'
            }]

    def handle_concept_queries(self, parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle complex biological concept queries"""
        concepts = parsed_query.get('concepts', {})
        query_type = parsed_query['query_type']
        entities = parsed_query['entities']
        
        results = []
        
        # Handle sequence queries
        if query_type == 'sequence' and entities.get('gene'):
            gene_entity = entities['gene'][0]
            gene_name = gene_entity['text']
            return self.handle_sequence_query(gene_name)
        
        # Handle homology queries
        if query_type == 'homology' and entities.get('gene') and entities.get('species'):
            gene_entity = entities['gene'][0]
            species_entity = entities['species'][0]
            
            gene_name = gene_entity['text']
            species_name = species_entity['normalized'].lower()
            
            # Map species names
            species_map = {
                'homo sapiens': 'human',
                'mus musculus': 'mouse', 
                'rattus norvegicus': 'rat'
            }
            
            target_species = species_map.get(species_name, 'mouse')
            return self.query_homology(gene_name, target_species)
        
        # Immune-virus interaction queries
        if 'immune_virus_interaction' in query_type or (concepts.get('immune') and concepts.get('virus')):
            immune_genes = ['TLR3', 'TLR7', 'TLR8', 'TLR9', 'RIGI', 'MDA5', 'MAVS', 'IRF3', 'IRF7', 
                           'STAT1', 'STAT2', 'IFIT1', 'IFIT2', 'IFIT3', 'OAS1', 'PKR', 'MX1']
            
            for gene in immune_genes[:5]:  # Limit to first 5
                gene_results = self.query_ncbi_gene(gene)
                for result in gene_results:
                    if 'status' in result and result['status'] == 'success':
                        result['concept'] = 'immune_response_antiviral'
                        result['virus_interaction'] = 'Targeted by various viruses to evade immune detection'
                        result['mechanism'] = 'Viruses often target these genes to suppress interferon response'
                results.extend(gene_results)
            
            if not any(r.get('status') == 'success' for r in results):
                results.append({
                    'concept': 'immune_virus_interaction',
                    'message': 'Viruses target key immune genes to evade detection',
                    'key_genes': ['TLR3', 'TLR7', 'RIGI', 'MDA5', 'STAT1', 'IRF3'],
                    'viral_strategies': [
                        'Suppression of interferon signaling',
                        'Degradation of antiviral proteins', 
                        'Inhibition of pattern recognition receptors',
                        'Modulation of cytokine responses'
                    ],
                    'examples': [
                        'HIV targets STAT1 to evade interferon response',
                        'Influenza inhibits RIG-I signaling',
                        'Herpes viruses target TLR pathways'
                    ],
                    'source': 'Virology and Immunology Database'
                })
        
        # Cancer gene queries
        elif 'cancer_gene' in query_type or concepts.get('cancer'):
            cancer_genes = ['TP53', 'BRCA1', 'BRCA2', 'EGFR', 'KRAS', 'PTEN', 'AKT1', 'MYC']
            
            for gene in cancer_genes[:4]:
                gene_results = self.query_ncbi_gene(gene)
                for result in gene_results:
                    if 'status' in result and result['status'] == 'success':
                        result['concept'] = 'cancer_related'
                        result['cancer_role'] = 'Oncogene or tumor suppressor'
                results.extend(gene_results)
        
        return results
    
    def execute_complex_query(self, parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute queries using only reliable APIs"""
        query_type = parsed_query['query_type']
        entities = parsed_query['entities']
        concepts = parsed_query.get('concepts', {})
        
        print(f"🎯 Processing {query_type} query with entities: {entities.keys()}")
        print(f"🔍 Detected concepts: {concepts.keys()}")
        
        results = []
        
        # Handle sequence queries as priority
        if query_type == 'sequence' and entities.get('gene'):
            gene_entity = entities['gene'][0]
            gene_name = gene_entity['text']
            return self.handle_sequence_query(gene_name)
        
        # Handle homology queries as priority
        if query_type == 'homology':
            homology_results = self.handle_concept_queries(parsed_query)
            if homology_results:
                return homology_results
        
        # Then try other concept-based queries
        concept_results = self.handle_concept_queries(parsed_query)
        if concept_results:
            results.extend(concept_results)
        
        # Then try entity-based queries
        if 'gene' in entities and not results:
            for gene_entity in entities['gene']:
                gene_name = gene_entity['text']
                
                # Get data from both reliable sources
                ncbi_results = self.query_ncbi_gene(gene_name)
                ensembl_results = self.query_ensembl(gene_name)
                
                # Add query context
                for result in ncbi_results + ensembl_results:
                    result['query_type'] = query_type
                    result['original_query'] = gene_name
                    result['timestamp'] = time.time()
                
                results.extend(ncbi_results)
                results.extend(ensembl_results)
        
        # If no results from specific entities but we have concepts
        elif concepts and not results:
            return self.handle_concept_queries(parsed_query)
        
        # If still no results, provide helpful guidance
        if not results:
            results.append({
                'message': 'No specific gene data found. Try these examples:',
                'examples': [
                    'What is the function of TP53?',
                    'Show me information about BRCA1',
                    'Find homologs of TP53 in mice',
                    'Tell me about the hemoglobin gene'
                ],
                'query_type': query_type,
                'source': 'BioNLI Assistant',
                'status': 'guidance'
            })
        
        print(f"📊 Returning {len(results)} total results")
        return results