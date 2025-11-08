from typing import Dict, List, Any

class BioServices:
    """Biological services with reliable mock data"""
    
    def get_biological_pathways(self, gene_name: str) -> List[Dict[str, Any]]:
        """Get biological pathways for a gene"""
        pathway_data = {
            'TP53': [
                {'name': 'p53 signaling pathway', 'source': 'KEGG', 'category': 'Cell cycle'},
                {'name': 'Apoptosis', 'source': 'Reactome', 'category': 'Cell death'},
                {'name': 'DNA damage response', 'source': 'WikiPathways', 'category': 'DNA repair'}
            ],
            'BRCA1': [
                {'name': 'DNA repair', 'source': 'KEGG', 'category': 'DNA damage response'},
                {'name': 'Cell cycle checkpoints', 'source': 'Reactome', 'category': 'Cell cycle'},
                {'name': 'Hereditary breast cancer', 'source': 'WikiPathways', 'category': 'Cancer'}
            ],
            'EGFR': [
                {'name': 'EGFR tyrosine kinase inhibitor resistance', 'source': 'KEGG', 'category': 'Cancer'},
                {'name': 'MAPK signaling pathway', 'source': 'Reactome', 'category': 'Signaling'},
                {'name': 'ErbB signaling pathway', 'source': 'WikiPathways', 'category': 'Signaling'}
            ],
            'HEMOGLOBIN': [
                {'name': 'Oxygen transport', 'source': 'Reactome', 'category': 'Metabolism'},
                {'name': 'Heme biosynthesis', 'source': 'KEGG', 'category': 'Biosynthesis'},
                {'name': 'Erythrocyte development', 'source': 'WikiPathways', 'category': 'Development'}
            ],
            'INSULIN': [
                {'name': 'Insulin signaling pathway', 'source': 'KEGG', 'category': 'Metabolism'},
                {'name': 'Glucose metabolism', 'source': 'Reactome', 'category': 'Metabolism'},
                {'name': 'Type II diabetes', 'source': 'WikiPathways', 'category': 'Disease'}
            ],
            'CFTR': [
                {'name': 'Chloride ion transport', 'source': 'Reactome', 'category': 'Transport'},
                {'name': 'Cystic fibrosis pathway', 'source': 'KEGG', 'category': 'Disease'},
                {'name': 'Ion channel regulation', 'source': 'WikiPathways', 'category': 'Signaling'}
            ],
            'VEGF': [
                {'name': 'VEGF signaling pathway', 'source': 'KEGG', 'category': 'Angiogenesis'},
                {'name': 'Blood vessel development', 'source': 'Reactome', 'category': 'Development'},
                {'name': 'Hypoxia response', 'source': 'WikiPathways', 'category': 'Stress response'}
            ]
        }
        
        # Return pathways for known genes, generic for others
        pathways = pathway_data.get(gene_name.upper(), [
            {'name': 'Common cellular pathways', 'source': 'Multiple databases', 'category': 'General'},
            {'name': 'Metabolic pathways', 'source': 'KEGG', 'category': 'Metabolism'},
            {'name': 'Signal transduction', 'source': 'Reactome', 'category': 'Signaling'}
        ])
        
        return [{
            'gene': gene_name,
            'pathways': pathways,
            'sources': ['KEGG', 'Reactome', 'WikiPathways'],
            'direct_links': [
                f'https://www.genome.jp/dbget-bin/www_bget?{gene_name}',
                f'https://reactome.org/content/query?q={gene_name}'
            ],
            'source': 'Pathway Database Integration'
        }]
    
    def run_blast_search(self, sequence: str) -> Dict[str, Any]:
        """Provide BLAST guidance"""
        return {
            'service': 'BLAST Homology Search',
            'status': 'guidance',
            'message': 'BLAST analysis available through NCBI',
            'recommendation': 'Use NCBI BLAST for sequence homology analysis',
            'direct_link': f'https://blast.ncbi.nlm.nih.gov/Blast.cgi?PROGRAM=blastn&PAGE_TYPE=BlastSearch&QUERY={sequence}',
            'note': 'For protein sequences, use blastp instead of blastn'
        }
    
    def get_gene_function_summary(self, gene_name: str) -> Dict[str, Any]:
        """Provide quick function summaries for common genes"""
        function_data = {
            'TP53': 'Tumor protein p53 - crucial tumor suppressor that regulates cell cycle and prevents cancer development',
            'BRCA1': 'Breast cancer type 1 susceptibility protein - involved in DNA repair and maintaining genomic stability',
            'EGFR': 'Epidermal growth factor receptor - cell surface receptor that regulates cell growth and division',
            'HEMOGLOBIN': 'Oxygen-carrying protein in red blood cells - transports oxygen from lungs to tissues',
            'INSULIN': 'Peptide hormone produced by pancreas - regulates glucose metabolism and blood sugar levels',
            'CFTR': 'Cystic fibrosis transmembrane conductance regulator - chloride channel important for fluid transport',
            'VEGF': 'Vascular endothelial growth factor - stimulates blood vessel formation (angiogenesis)'
        }
        
        summary = function_data.get(gene_name.upper(), 
            f'{gene_name} is a gene with various biological functions. Check specific databases for detailed information.')
        
        return {
            'gene': gene_name,
            'function_summary': summary,
            'source': 'BioNLI Knowledge Base'
        }