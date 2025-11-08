from typing import Dict, List, Any, Set, Optional
from collections import defaultdict
import re

class OntologyManager:
    """Manages biological ontologies and semantic reasoning"""
    
    def __init__(self):
        self.ontologies = self._initialize_ontologies()
        self.relationships = self._initialize_relationships()
        self.inference_rules = self._initialize_inference_rules()
    
    def _initialize_ontologies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize biological ontologies with key concepts"""
        return {
            'gene_ontology': {
                'biological_process': {
                    'cell_cycle': ['mitosis', 'meiosis', 'cell_division', 'DNA_replication'],
                    'apoptosis': ['programmed_cell_death', 'cell_suicide'],
                    'metabolism': ['catabolic_process', 'anabolic_process', 'biosynthesis'],
                    'signaling': ['signal_transduction', 'cell_communication', 'receptor_activity'],
                    'development': ['cell_differentiation', 'morphogenesis', 'growth'],
                    'immune_response': ['inflammatory_response', 'defense_response', 'cytokine_production']
                },
                'molecular_function': {
                    'binding': ['protein_binding', 'DNA_binding', 'RNA_binding', 'ion_binding'],
                    'catalytic_activity': ['kinase_activity', 'phosphatase_activity', 'hydrolase_activity'],
                    'transporter_activity': ['ion_transport', 'substrate_transport', 'membrane_transport'],
                    'receptor_activity': ['transmembrane_receptor', 'nuclear_receptor', 'cytokine_receptor']
                },
                'cellular_component': {
                    'nucleus': ['nuclear_membrane', 'nucleolus', 'chromatin'],
                    'cytoplasm': ['cytosol', 'organelles', 'cytoskeleton'],
                    'membrane': ['plasma_membrane', 'organelle_membrane', 'receptor_complex'],
                    'extracellular': ['extracellular_matrix', 'secreted_proteins']
                }
            },
            'disease_ontology': {
                'cancer': ['carcinoma', 'sarcoma', 'leukemia', 'lymphoma', 'tumor'],
                'metabolic_disorders': ['diabetes', 'obesity', 'hyperlipidemia'],
                'neurological': ['alzheimer', 'parkinson', 'huntington', 'autism'],
                'immune_disorders': ['autoimmune', 'immunodeficiency', 'allergy', 'asthma'],
                'genetic_disorders': ['cystic_fibrosis', 'sickle_cell', 'hemophilia', 'muscular_dystrophy']
            },
            'pathway_ontology': {
                'signaling_pathways': ['MAPK', 'PI3K', 'Wnt', 'Notch', 'Hedgehog', 'TGF_beta'],
                'metabolic_pathways': ['glycolysis', 'TCA_cycle', 'oxidative_phosphorylation', 'fatty_acid_synthesis'],
                'regulatory_pathways': ['cell_cycle_regulation', 'apoptosis_regulation', 'DNA_repair'],
                'disease_pathways': ['cancer_pathways', 'inflammatory_pathways', 'metabolic_disease_pathways']
            }
        }
    
    def _initialize_relationships(self) -> Dict[str, List[str]]:
        """Initialize semantic relationships between concepts"""
        return {
            'is_a': ['is a type of', 'is a', 'is an'],
            'part_of': ['part of', 'component of', 'contained in'],
            'regulates': ['regulates', 'controls', 'modulates'],
            'interacts_with': ['interacts with', 'binds to', 'associates with'],
            'causes': ['causes', 'leads to', 'results in'],
            'expressed_in': ['expressed in', 'found in', 'localized to'],
            'involved_in': ['involved in', 'participates in', 'plays role in']
        }
    
    def _initialize_inference_rules(self) -> Dict[str, Any]:
        """Initialize reasoning rules for biological concepts"""
        return {
            'cancer_genes': {
                'conditions': ['tumor_suppressor', 'oncogene', 'DNA_repair', 'cell_cycle_regulation'],
                'inference': 'likely_cancer_related',
                'confidence': 0.8
            },
            'immune_genes': {
                'conditions': ['cytokine', 'receptor', 'signaling', 'defense_response'],
                'inference': 'likely_immune_related', 
                'confidence': 0.7
            },
            'metabolic_genes': {
                'conditions': ['enzyme', 'catalytic', 'biosynthesis', 'degradation'],
                'inference': 'likely_metabolic_related',
                'confidence': 0.75
            },
            'signaling_genes': {
                'conditions': ['receptor', 'kinase', 'phosphatase', 'signal_transduction'],
                'inference': 'likely_signaling_related',
                'confidence': 0.8
            }
        }
    
    def map_concepts_to_ontology(self, concepts: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Map extracted concepts to formal ontology terms"""
        mapped_terms = defaultdict(list)
        
        for concept_type, terms in concepts.items():
            for term in terms:
                # Search through all ontologies for matching terms
                ontology_terms = self._find_ontology_terms(term)
                if ontology_terms:
                    for ontology, categories in ontology_terms.items():
                        for category, terms_in_category in categories.items():
                            mapped_terms[f"{ontology}.{category}"].extend(terms_in_category)
        
        return dict(mapped_terms)
    
    def _find_ontology_terms(self, term: str) -> Dict[str, Dict[str, List[str]]]:
        """Find ontology terms that match the input term"""
        matches = defaultdict(lambda: defaultdict(list))
        term_lower = term.lower()
        
        for ontology_name, ontology in self.ontologies.items():
            for category, terms_in_category in ontology.items():
                if isinstance(terms_in_category, dict):
                    # Handle nested categories
                    for subcategory, sub_terms in terms_in_category.items():
                        if self._term_matches(term_lower, subcategory) or any(self._term_matches(term_lower, t) for t in sub_terms):
                            matches[ontology_name][category].append(subcategory)
                else:
                    # Handle flat categories
                    if self._term_matches(term_lower, category) or any(self._term_matches(term_lower, t) for t in terms_in_category):
                        matches[ontology_name][category].extend(terms_in_category)
        
        return dict(matches)
    
    def _term_matches(self, search_term: str, ontology_term: str) -> bool:
        """Check if search term matches ontology term"""
        ontology_lower = ontology_term.lower()
        
        # Exact match
        if search_term == ontology_lower:
            return True
        
        # Partial match
        if search_term in ontology_lower or ontology_lower in search_term:
            return True
        
        # Word boundary match
        if re.search(r'\b' + re.escape(search_term) + r'\b', ontology_lower):
            return True
        
        return False
    
    def infer_biological_context(self, entities: Dict[str, List[Dict]], concepts: Dict[str, List[str]]) -> Dict[str, Any]:
        """Infer broader biological context from entities and concepts"""
        inferences = defaultdict(list)
        confidence_scores = {}
        
        # Analyze gene entities
        if 'gene' in entities:
            for gene_entity in entities['gene']:
                gene_name = gene_entity['text'].upper()
                gene_inferences = self._infer_gene_context(gene_name, concepts)
                for inference, confidence in gene_inferences.items():
                    inferences[inference].append(gene_name)
                    confidence_scores[inference] = confidence
        
        # Analyze concepts for broader context
        concept_inferences = self._infer_from_concepts(concepts)
        for inference, confidence in concept_inferences.items():
            inferences[inference].extend(concepts.get(inference, []))
            confidence_scores[inference] = max(confidence_scores.get(inference, 0), confidence)
        
        return {
            'inferred_contexts': dict(inferences),
            'confidence_scores': dict(confidence_scores),
            'recommended_queries': self._generate_recommended_queries(inferences, concepts)
        }
    
    def _infer_gene_context(self, gene_name: str, concepts: Dict[str, List[str]]) -> Dict[str, float]:
        """Infer context for specific genes"""
        inferences = {}
        
        # Known gene patterns (could be expanded with real database)
        gene_patterns = {
            'TP53': ['tumor_suppressor', 'cell_cycle', 'apoptosis', 'DNA_repair'],
            'BRCA1': ['DNA_repair', 'tumor_suppressor', 'cell_cycle'],
            'EGFR': ['receptor', 'signaling', 'oncogene', 'kinase'],
            'INS': ['hormone', 'metabolism', 'signaling'],
            'HEMOGLOBIN': ['oxygen_transport', 'metabolism', 'blood'],
            'VEGF': ['signaling', 'angiogenesis', 'growth_factor'],
            'CFTR': ['ion_channel', 'transport', 'membrane']
        }
        
        # Add inferences based on known gene functions
        if gene_name in gene_patterns:
            for context in gene_patterns[gene_name]:
                inferences[context] = 0.9
        
        # Add inferences based on concepts
        for concept_type, terms in concepts.items():
            if concept_type in ['cancer', 'tumor']:
                inferences['cancer_related'] = 0.8
            if concept_type in ['immune', 'defense']:
                inferences['immune_related'] = 0.7
            if concept_type in ['metabolism', 'biosynthesis']:
                inferences['metabolic_related'] = 0.75
        
        return inferences
    
    def _infer_from_concepts(self, concepts: Dict[str, List[str]]) -> Dict[str, float]:
        """Infer broader context from concepts using rules"""
        inferences = {}
        
        for rule_name, rule in self.inference_rules.items():
            conditions_met = 0
            total_conditions = len(rule['conditions'])
            
            for condition in rule['conditions']:
                # Check if condition appears in any concept terms
                for concept_terms in concepts.values():
                    if any(condition in term.lower() for term in concept_terms):
                        conditions_met += 1
                        break
            
            if conditions_met > 0:
                confidence = rule['confidence'] * (conditions_met / total_conditions)
                inferences[rule['inference']] = confidence
        
        return inferences
    
    def _generate_recommended_queries(self, inferences: Dict[str, List[str]], concepts: Dict[str, List[str]]) -> List[str]:
        """Generate recommended follow-up queries based on inferences"""
        recommendations = []
        
        if 'cancer_related' in inferences:
            recommendations.extend([
                "Find interacting proteins in cancer pathways",
                "Explore mutation sites in cancer databases",
                "Check clinical trials targeting this gene"
            ])
        
        if 'immune_related' in inferences:
            recommendations.extend([
                "Find immune cell expression patterns",
                "Explore cytokine interactions",
                "Check autoimmune disease associations"
            ])
        
        if 'signaling_related' in inferences:
            recommendations.extend([
                "Map to signaling pathways (MAPK, PI3K, etc.)",
                "Find upstream regulators and downstream targets",
                "Explore phosphorylation sites"
            ])
        
        if 'metabolic_related' in inferences:
            recommendations.extend([
                "Find metabolic pathway associations",
                "Explore enzyme commission numbers",
                "Check metabolite interactions"
            ])
        
        # Add general recommendations
        if not recommendations:
            recommendations = [
                "Find protein structure information",
                "Explore tissue-specific expression",
                "Check evolutionary conservation",
                "Find related publications"
            ]
        
        return recommendations[:5]  # Limit to top 5
    
    def expand_query_terms(self, query_terms: List[str]) -> List[str]:
        """Expand query terms with synonyms and related terms"""
        expanded_terms = set(query_terms)
        
        for term in query_terms:
            # Find related terms in ontologies
            related = self._find_related_terms(term)
            expanded_terms.update(related)
        
        return list(expanded_terms)
    
    def _find_related_terms(self, term: str) -> List[str]:
        """Find semantically related terms in ontologies"""
        related_terms = []
        term_lower = term.lower()
        
        # Look for term in ontologies and get sibling terms
        for ontology in self.ontologies.values():
            for category, items in ontology.items():
                if isinstance(items, dict):
                    for subcategory, terms_list in items.items():
                        if term_lower == subcategory.lower() or any(term_lower == t.lower() for t in terms_list):
                            # Add all terms in the same category
                            related_terms.extend(terms_list)
                            related_terms.append(subcategory)
                else:
                    if term_lower == category.lower() or any(term_lower == t.lower() for t in items):
                        related_terms.extend(items)
                        related_terms.append(category)
        
        return list(set(related_terms))
