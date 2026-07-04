"""
BioNLI QA Engine - Publication Quality
Smart router for ANY biological question
"""

import logging
import time
import hashlib
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from .structured_query import StructuredQuery, Entity, EntityType, Intent
from .semantic_parser import SemanticParser
from .ontology_integration import OntologyReasoner
from .hgnc_loader import HGNCGeneLoader
from .intent_router import IntentRouter, QuestionType
from .data_sources import (
    NCBIDataSource, EnsemblDataSource, STRINGDataSource,
    ReactomeDataSource, DisGeNETDataSource, OLSDataSource, UniProtDataSource
)
from .pdb_source import PDBDataSource
from .response_formatter import BioResponseFormatter
logger = logging.getLogger(__name__)


class BioQuestionAnsweringEngine:
    """Main QA Engine - Answers ANY biological question."""
    
    def __init__(self, email: str = "udaybioinfo@gmail.com", use_gpu: bool = True):
        logger.info("=" * 70)
        logger.info("🔬 BioNLI QA Engine Initializing (Publication Version)")
        logger.info("=" * 70)
        
        # Configure NCBI
        self.email = email
        
        # Initialize components
        logger.info("1. Loading Semantic Parser...")
        self.semantic_parser = SemanticParser(use_gpu=use_gpu)
        
        logger.info("2. Loading Intent Router...")
        self.intent_router = IntentRouter()
        
        logger.info("3. Loading Ontology Reasoner...")
        self.ontology_reasoner = OntologyReasoner()
        
        logger.info("4. Loading HGNC Gene List...")
        self.hgnc = HGNCGeneLoader()
        
        logger.info("5. Initializing Data Sources...")
        self.data_sources = {
            'ncbi': NCBIDataSource(email),
            'ensembl': EnsemblDataSource(),
            'string': STRINGDataSource(),
            'reactome': ReactomeDataSource(),
            'disgenet': DisGeNETDataSource(),
            'ols': OLSDataSource(),
            'uniprot': UniProtDataSource(),
            'pdb': PDBDataSource()
        }
        logger.info("6. Initializing Response Formatter...")
        self.formatter = BioResponseFormatter()
        
        self.query_cache = {}
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'intent_distribution': {}
        }
        
        logger.info("=" * 70)
        logger.info("✓ System Ready (No Fake Data)")
        logger.info(f"  - HGNC Genes: {self.hgnc.total_genes:,}")
        logger.info(f"  - GO Terms: {len(self.ontology_reasoner.ontologies.get('go', {})):,}")
        logger.info(f"  - Data Sources: {len(self.data_sources)}")
        logger.info("=" * 70)
    
    def answer(self, question: str, context: Dict = None) -> Dict:
        """
        Answer ANY biological question using smart routing.
        """
        start_time = time.time()
        self.stats['total_queries'] += 1
        
        logger.info(f"\n📝 Q: {question[:100]}...")
        
        # Check cache
        cache_key = hashlib.md5(question.encode()).hexdigest()
        if cache_key in self.query_cache:
            self.stats['cache_hits'] += 1
            logger.info(f"   ✓ Cache hit")
            return self.query_cache[cache_key]
        
        try:
            # Step 1: Parse with BioBERT
            structured_query = self.semantic_parser.parse(question)
            
            # Step 2: Route to appropriate data sources
            route = self.intent_router.route(question, structured_query.entities)
            
            # Update stats
            intent_name = route['intent'].value
            self.stats['intent_distribution'][intent_name] = self.stats['intent_distribution'].get(intent_name, 0) + 1
            
            logger.info(f"   ✓ Routed to: {route['intent'].value} (confidence: {route['intent_confidence']:.2f})")
            logger.info(f"   ✓ Data sources: {route['data_sources']}")
            
            # Step 3: Extract key entities
            gene = None
            concept = None
            for e in route['entities']:
                if e['type'] == 'GENE':
                    # Validate with HGNC
                    canonical = self.hgnc.get_canonical(e['text'])
                    gene = canonical if canonical else e['text'].upper()
                    logger.info(f"   ✓ Gene extracted: {e['text']} → {gene}")
                elif e['type'] == 'CONCEPT':
                    concept = e['text']
                    logger.info(f"   ✓ Concept extracted: {concept}")
            
            # Step 4: Query appropriate data sources (FIXED VALIDATION)
            answer_parts = []
            
            for source_name in route['data_sources']:
                source = self.data_sources.get(source_name)
                if source:
                    params = self._build_params(route['intent'], gene, concept, question)
                    logger.info(f"   🔍 Querying {source_name} with params: {params}")
                    
                    try:
                        result = source.query(params)
                    except Exception as e:
                        logger.error(f"   ✗ {source_name} query failed: {e}")
                        continue
                    
                    # FIXED: Better validation - check if result is a non-empty string with real content
                    if result is None:
                        logger.warning(f"   ⚠️ {source_name} returned None")
                        continue
                        
                    if not isinstance(result, str):
                        logger.warning(f"   ⚠️ {source_name} returned non-string: {type(result)}")
                        continue
                        
                    result_len = len(result)
                    logger.info(f"   📄 {source_name} result length: {result_len}")
                    
                    # Check if result has meaningful content (at least 50 chars for NCBI/UniProt)
                    if result_len < 20:
                        logger.warning(f"   ⚠️ {source_name} result too short: {result[:100] if result else 'Empty'}")
                        continue
                        
                    # Check for actual error messages (not just any "No" which might be part of a word)
                    result_lower = result.lower()

                    error_indicators = [
                        'no information found',
                        'error retrieving',
                        'api returned status',
                        'no protein information found',
                        'no definition found',
                        'no interaction data found',
                        'no ortholog found',
                        'no pathways found',
                        'no known disease associations found',
                        'no uniprot entry found',
                    ]
                    is_error = any(ind in result_lower for ind in error_indicators)

                    lines = [l.strip() for l in result.split('\n') if l.strip()]

                    if source_name == 'ncbi':
                        has_substantial_content = (
                            'gene id' in result_lower and
                            any(len(l) > 30 for l in lines)
                        )
                    elif source_name == 'uniprot':
                        has_substantial_content = (
                            ('uniprot.org' in result_lower or
                             'uniprotkb' in result_lower or
                             'uniprot:' in result_lower or
                             'swiss-prot' in result_lower or
                             'trembl' in result_lower) and
                            any(len(l) > 30 for l in lines)
                        )
                    elif source_name == 'pdb':
                        has_substantial_content = (
                            'structure_data_start' in result_lower and
                            'sequence_length' in result_lower
                        )
                    elif source_name == 'string':
                        has_substantial_content = (
                            ('interaction' in result_lower or 'string' in result_lower)
                            and len(lines) >= 3
                        )
                    elif source_name == 'reactome':
                        has_substantial_content = (
                            ('pathway' in result_lower or 'reactome' in result_lower)
                            and len(lines) >= 3
                        )
                    elif source_name == 'disgenet':
                        has_substantial_content = (
                            ('disease' in result_lower or 'opentargets' in result_lower
                             or 'disgenet' in result_lower)
                            and len(lines) >= 3
                        )
                    elif source_name == 'ensembl':
                        has_substantial_content = (
                            ('ortholog' in result_lower or 'ensembl' in result_lower
                             or 'homolog' in result_lower)
                            and len(lines) >= 2
                        )
                    else:
                        has_substantial_content = len(lines) >= 2

                    if is_error:
                        logger.warning(f"   ⚠️ {source_name} returned error: {result[:100]}")
                        continue

                    if not has_substantial_content:
                        logger.warning(f"   ⚠️ {source_name} insubstantial: {result[:100]}")
                        continue

                    # Result is valid
                    answer_parts.append(result)
                    logger.info(f"   ✅ Added result from {source_name}")
            
            logger.info(f"   📊 Total answer parts collected: {len(answer_parts)}")
            
            # Step 5: Add ontology expansion for gene queries
            if gene:
                logger.info(f"   🔍 Looking up ontology for gene: {gene}")
                concept_obj = self.ontology_reasoner.get_concept(gene.lower())
                if concept_obj and hasattr(concept_obj, 'synonyms') and concept_obj.synonyms:
                    # Filter out bare gene names (e.g. 'EGFR') — only keep real GO term descriptions
                    real_go_terms = [
                        t for t in concept_obj.synonyms[:8]
                        if len(t) > 6 and not t.isupper()
                    ]
                    if real_go_terms:
                        go_term_text = f"Related GO Terms: {', '.join(real_go_terms[:5])}"
                        answer_parts.append(go_term_text)
                        logger.info(f"   ✅ Added GO terms: {real_go_terms[:5]}")
                else:
                    logger.info(f"   ⚠️ No GO terms found for {gene}")
            
            # =========================================================
            # Step 6: Format answer clearly for the user
            # =========================================================
            final_answer = self.formatter.format(
                answer_parts, gene, route['intent'].value, question
            )
            logger.info(f"   ✅ Final answer length: {len(final_answer)} chars")
            
            response = {
                'question': question,
                'answer': final_answer,
                'confidence': route['intent_confidence'],
                'intent': route['intent'].value,
                'entities': route['entities'],
                'data_sources_used': route['data_sources'],
                'processing_time': time.time() - start_time,
                'status': 'success'
            }
            
            # Cache response
            self.query_cache[cache_key] = response
            
            logger.info(f"   ✓ Complete in {response['processing_time']:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"   ✗ Error: {e}", exc_info=True)
            return {
                'question': question,
                'answer': f"Error processing question: {str(e)}",
                'confidence': 0.0,
                'status': 'error',
                'processing_time': time.time() - start_time
            }
    
    def _build_params(self, intent: QuestionType, gene: str, concept: str, question: str) -> Dict:
        """Build parameters for data source query."""
        params = {}
        
        if intent == QuestionType.HOMOLOGY:
            # Extract species from question
            species = 'mouse'
            question_lower = question.lower()
            if 'rat' in question_lower:
                species = 'rat'
            elif 'zebrafish' in question_lower:
                species = 'zebrafish'
            elif 'fly' in question_lower:
                species = 'fly'
            elif 'worm' in question_lower:
                species = 'worm'
            params = {'gene': gene, 'species': species}
        
        elif intent == QuestionType.PATHWAY:
            if gene:
                params = {'gene': gene}
            else:
                question_lower = question.lower()
                pathway = None
                for kw in ['apoptosis', 'mapk', 'wnt', 'dna repair', 'cell cycle',
                           'pi3k', 'notch', 'hedgehog', 'tgf', 'jak-stat', 'nf-kb']:
                    if kw in question_lower:
                        pathway = kw
                        break
                params = {'pathway': pathway or question_lower}
        
        elif intent == QuestionType.INTERACTION:
            params = {'gene': gene}
        
        elif intent == QuestionType.DISEASE_ASSOCIATION:
            if gene:
                params = {'gene': gene}
            else:
                # Extract disease from question
                disease = concept or question.lower().split('associated with')[-1].strip()[:50]
                params = {'disease': disease}
        
        elif intent == QuestionType.CONCEPT_DEFINITION:
            params = {'concept': concept or question.replace('what is', '').replace('define', '').strip()}
        
        elif intent in [QuestionType.GENE_FUNCTION, QuestionType.GENE_DESCRIPTION, QuestionType.LOCATION]:
            params = {'gene': gene}
        
        elif intent == QuestionType.PROTEIN_FUNCTION:
            params = {'gene': gene}

        elif intent == QuestionType.STRUCTURE:
            params = {'gene': gene}

        return params
    
    def _get_helpful_response(self, question: str, route: Dict) -> str:
        """Generate helpful response when no specific answer found."""
        return f"""I couldn't find specific information for your question.

**Question detected as:** {route['intent'].value}

**Try asking about:**
• Gene functions: "What is the function of TP53?"
• Protein interactions: "What proteins interact with p53?"
• Pathways: "What genes are in the p53 pathway?"
• Homology: "Find mouse homologs of TP53"
• Diseases: "What diseases are associated with BRCA1?"
• Concepts: "What is apoptosis?"

**Supported genes include:** TP53, BRCA1, EGFR, KRAS, MYC, PTEN, RB1, VEGFA, INS, CFTR, APOE, APP, SNCA, HTT, DMD

**Example questions:**
1. "Describe the function of EGFR"
2. "What is the mouse homolog of TP53?"
3. "What proteins interact with BRCA1?"
4. "What diseases are associated with KRAS?"
5. "What is apoptosis?"
"""
    
    def get_stats(self) -> Dict:
        """Get system statistics."""
        source_stats = {}
        for name, source in self.data_sources.items():
            source_stats[name] = source.get_stats()
        
        return {
            **self.stats,
            'hgnc_genes': self.hgnc.total_genes,
            'hgnc_version': self.hgnc.version,
            'go_terms': len(self.ontology_reasoner.ontologies.get('go', {})),
            'source_stats': source_stats,
            'cache_hit_rate': (self.stats['cache_hits'] / max(self.stats['total_queries'], 1)) * 100
        }