"""
BioNLI Response Formatter
=========================
Transforms raw data fetched from NCBI, UniProt, STRING, DisGeNET,
Reactome, and Ensembl into clear, well-structured answers that an
experimental biologist (or any curious person) can understand at a glance —
similar to how Claude or a knowledgeable scientist would explain things.

How to plug this in
-------------------
In qa_engine.py, replace the "Step 6: Combine answers intelligently" block
with these two lines:

    formatter = BioResponseFormatter()          # once, in __init__
    final_answer = self.formatter.format(       # in answer()
        answer_parts, gene, route['intent'].value, question
    )
"""

import re
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Low-level text helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_field(text: str, *names: str) -> str:
    """
    Pull the value that follows a labeled field such as:
        **Summary:** ...
        Summary: ...
    Tries every name in `names` (case-insensitive).
    Returns "" if nothing is found.
    """
    for name in names:
        pattern = rf'(?:\*\*)?{re.escape(name)}(?:\*\*)?:?\s*(.*?)(?=\n\n|\Z)'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            value = m.group(1).strip()
            # Strip any residual markdown bold/italic markers from the value
            value = re.sub(r'\*\*', '', value)
            value = re.sub(r'\*', '', value)
            value = re.sub(r'\s{2,}', ' ', value).strip()
            if value:
                return value
    return ""


def _bullet_list(items: List[str], limit: int = 10) -> str:
    return "\n".join(f"  • {item.strip()}" for item in items[:limit] if item.strip())


def _clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)        # strip HTML tags
    text = re.sub(r'\*\*', '', text)             # strip markdown bold **
    text = re.sub(r'\*', '', text)               # strip markdown italic * and stray asterisks
    text = re.sub(r'\(PubMed:\d+(?:,\s*PubMed:\d+)*\)', '', text)  # strip PubMed citations
    text = re.sub(r'\[provided by.*?\]', '', text, flags=re.IGNORECASE)  # strip RefSeq notes
    text = re.sub(r'\{ECO:\S+\}', '', text)      # strip UniProt evidence codes
    return re.sub(r'\s{2,}', ' ', text).strip()


def _trim_to_sentences(text: str, n: int = 4) -> str:
    """Keep the first n sentences of a block of text."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:n])


# ──────────────────────────────────────────────────────────────────────────────
# Section builders  — each returns a plain-text block or ""
# ──────────────────────────────────────────────────────────────────────────────

def _section_gene_overview(gene: str, ncbi_text: str) -> str:
    """
    Builds: 'What is this gene?' paragraph from NCBI data.
    """
    description = _extract_field(ncbi_text, "Description")
    summary     = _extract_field(ncbi_text, "Summary")
    location    = _extract_field(ncbi_text, "Location", "Chromosome")
    gene_id_m   = re.search(r'Gene ID[:\s]+(\d+)', ncbi_text, re.IGNORECASE)
    gene_id     = gene_id_m.group(1) if gene_id_m else ""

    # Normalise location: strip leading "Chromosome " word if present, then check
    location = re.sub(r'^chromosome\s+', '', location, flags=re.IGNORECASE).strip()
    location_ok = location and location.lower() not in ("not specified", "unknown", "", "none")

    if not description and not summary:
        return ""

    lines = []

    # Opening sentence
    lead = f"{gene}"
    if description:
        lead += f" ({description}) is a human gene"
    else:
        lead += " is a human gene"
    if location_ok:
        lead += f" located on chromosome {location}"
    lead += "."
    lines.append(lead)

    # Summary (first 3–4 sentences)
    if summary:
        lines.append(_trim_to_sentences(_clean_html(summary), n=4))

    # Source link
    if gene_id:
        lines.append(
            f"→ NCBI Gene entry: https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
        )

    return "\n".join(lines)


def _section_protein_function(gene: str, uniprot_text: str) -> str:
    """
    Builds: 'What does the protein do?' paragraph from UniProt data.
    """
    function = _extract_field(uniprot_text, "Function")

    # Parse protein name and UniProt ID
    name_m = re.search(r'\*\*(.*?)\*\*\s*\(UniProt:', uniprot_text)
    if not name_m:
        name_m = re.search(r'^(.+?)\s*\(UniProt:', uniprot_text, re.MULTILINE)
    protein_name = name_m.group(1).strip() if name_m else ""

    uid_m = re.search(r'UniProt[:\s]+([A-Z0-9]{5,10})', uniprot_text, re.IGNORECASE)
    uniprot_id = uid_m.group(1) if uid_m else ""

    if not function:
        return ""

    function = _clean_html(function)
    function = _trim_to_sentences(function, n=4)

    lines = []
    if protein_name:
        lines.append(
            f"The protein encoded by {gene} is called {protein_name}."
        )
    lines.append(function)
    if uniprot_id:
        lines.append(
            f"→ UniProt entry: https://www.uniprot.org/uniprot/{uniprot_id}"
        )

    return "\n".join(lines)


def _section_interactions(gene: str, string_text: str) -> str:
    items = re.findall(r'[•·\-]\s*([A-Z0-9][A-Z0-9_\-]{1,15})', string_text)
    if not items:
        return ""
    return (
        f"{gene} is known to physically interact with (or functionally associate with) "
        f"the following proteins inside the cell:\n"
        + _bullet_list(items, limit=10)
        + "\n→ Source: STRING · https://string-db.org"
    )


def _section_structure(gene: str, pdb_text: str) -> str:
    """Parse STRUCTURE_DATA_START block from PDBDataSource into readable text."""
    if not pdb_text or 'STRUCTURE_DATA_START' not in pdb_text:
        return ""

    def _val(key: str) -> str:
        m = re.search(rf'^{key}:\s*(.+)', pdb_text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    length     = _val('Sequence_Length')
    mass       = _val('Molecular_Mass')
    domains_raw = _val('Domains')
    exp_struct  = _val('Experimental_Structures')
    pdb_ids     = _val('PDB_IDs')
    af_page     = _val('AlphaFold_Page')
    uniprot_page = _val('UniProt_Page')

    lines = []
    if length or mass:
        parts = []
        if length: parts.append(length)
        if mass:   parts.append(f"molecular weight {mass}")
        lines.append("Size: " + " · ".join(parts))

    if domains_raw:
        domains = [d.strip() for d in domains_raw.split('|') if d.strip()]
        lines.append("\nFunctional domains and regions:")
        for d in domains:
            lines.append(f"  • {d}")

    if exp_struct:
        lines.append(f"\nExperimental 3D structures: {exp_struct}")
        if pdb_ids:
            lines.append(f"  Sample PDB IDs: {pdb_ids}")
            lines.append(f"  → Browse at: https://www.rcsb.org/search?query={gene}")

    if af_page:
        lines.append("\nAlphaFold predicted structure (free, high confidence):")
        lines.append(f"  → {af_page}")

    if uniprot_page:
        lines.append(f"\n→ Full structural data: {uniprot_page}#ptm_processing")

    lines.append("\n(Sources: UniProt · AlphaFold EBI · RCSB PDB)")
    return "\n".join(lines)


def _section_diseases(gene: str, disgenet_text: str) -> str:
    items = re.findall(r'[•·\-]\s*(.+)', disgenet_text)
    if not items:
        return ""
    return (
        f"Mutations or dysregulation of {gene} have been linked to:\n"
        + _bullet_list(items, limit=8)
        + "\n→ Source: DisGeNET · https://www.disgenet.org"
    )


def _section_pathways(gene: str, reactome_text: str) -> str:
    items = re.findall(r'[•·\-]\s*(.+)', reactome_text)
    if not items:
        return ""
    return (
        f"{gene} participates in the following biological pathways:\n"
        + _bullet_list(items, limit=8)
        + "\n→ Source: Reactome · https://reactome.org"
    )


def _section_homology(gene: str, ensembl_text: str) -> str:
    items = re.findall(r'[•·\-]\s*(.+)', ensembl_text)
    if not items:
        return ""
    return (
        f"The equivalent (orthologous) gene of {gene} in other organisms:\n"
        + _bullet_list(items, limit=6)
        + "\n→ Source: Ensembl · https://ensembl.org"
    )


def _section_go_terms(gene: str, go_text: str) -> str:
    m = re.search(r'Related GO Terms[:\s]*(.*)', go_text, re.IGNORECASE)
    if not m:
        return ""
    terms = [t.strip() for t in m.group(1).split(',') if t.strip()]
    if not terms:
        return ""
    return (
        f"Gene Ontology (GO) annotations for {gene}:\n"
        + _bullet_list(terms, limit=6)
        + "\n→ Source: Gene Ontology · https://geneontology.org"
    )


def _section_concept_definition(ols_text: str) -> str:
    definition = _extract_field(ols_text, "Definition")
    label_m = re.match(r'\*\*(.+?)\*\*', ols_text)
    label = label_m.group(1).strip() if label_m else ""
    if not definition:
        return _clean_html(ols_text[:500]) if ols_text else ""
    if label:
        return f"{label}: {_clean_html(definition)}"
    return _clean_html(definition)


# ──────────────────────────────────────────────────────────────────────────────
# Footer helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sources_footer(ncbi_text: str, uniprot_text: str) -> str:
    sources = []
    if ncbi_text:
        sources.append("NCBI Gene (https://www.ncbi.nlm.nih.gov/gene)")
    if uniprot_text:
        sources.append("UniProt Knowledgebase (https://www.uniprot.org)")
    if sources:
        return "📚 Data from: " + " | ".join(sources)
    return ""


def _timestamp_note() -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return (
        f"ℹ️  Retrieved on {today}. "
        "Always cross-check with the primary databases before experimental use."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main formatter class
# ──────────────────────────────────────────────────────────────────────────────

class BioResponseFormatter:
    """
    Drop-in formatter for BioNLI QA Engine.

    Instantiate once in BioQuestionAnsweringEngine.__init__:
        self.formatter = BioResponseFormatter()

    Call in BioQuestionAnsweringEngine.answer() instead of the big
    'Step 6' if/elif block:
        final_answer = self.formatter.format(
            answer_parts, gene, route['intent'].value, question
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def format(
        self,
        answer_parts: List[str],
        gene: Optional[str],
        intent: str,
        question: str,
    ) -> str:
        """
        Route to the correct layout based on intent and available data.
        Always returns a non-empty string.
        """
        if not answer_parts:
            return self._no_info_response(gene, question)

        # Classify each raw part by which database it came from.
        # Order matters: NCBI check must come before UniProt because NCBI
        # text also contains the word "Protein".
        ncbi_text     = next((p for p in answer_parts
                              if "Gene ID" in p or "*Source: NCBI" in p or "ncbi.nlm.nih.gov" in p), "")
        uniprot_text  = next((p for p in answer_parts
                              if "uniprot.org" in p.lower()
                              or "UniProt:" in p
                              or ("Function:" in p and "Gene ID" not in p)), "")
        pdb_text      = next((p for p in answer_parts
                              if "STRUCTURE_DATA_START" in p), "")
        string_text   = next((p for p in answer_parts
                              if "STRING" in p or "Interaction Partners" in p), "")
        disgenet_text = next((p for p in answer_parts
                              if "DisGeNET" in p or "Diseases associated" in p), "")
        reactome_text = next((p for p in answer_parts
                              if "Reactome" in p or "Pathway" in p), "")
        ensembl_text  = next((p for p in answer_parts
                              if "Ensembl" in p or "Ortholog" in p), "")
        go_text       = next((p for p in answer_parts
                              if "GO Terms" in p or "geneontology" in p.lower()), "")
        ols_text      = next((p for p in answer_parts
                              if "Gene Ontology" in p and "Definition" in p), "")

        i = intent.lower()

        # Structure / domains / PDB
        if "structure" in i:
            return self._format_structure(gene, pdb_text, uniprot_text)

        # Gene function / description (most common query type)
        if any(k in i for k in ("gene_function", "gene_description", "protein_function")):
            return self._format_gene_overview(
                gene, ncbi_text, uniprot_text, string_text,
                disgenet_text, reactome_text, go_text
            )

        # Protein-only questions
        if "protein" in i and uniprot_text and not ncbi_text:
            return self._format_protein_only(gene, uniprot_text)

        # Interactions
        if "interaction" in i:
            return self._format_interactions(gene, string_text)

        # Disease associations
        if "disease" in i:
            return self._format_diseases(gene, disgenet_text)

        # Pathways
        if "pathway" in i:
            return self._format_pathways(gene, reactome_text)

        # Homology / orthologs
        if "homolog" in i or "ortholog" in i:
            return self._format_homology(gene, ensembl_text)

        # Concept / GO definition
        if "concept" in i and ols_text:
            return self._format_concept(ols_text)

        # Fallback: render everything we have
        return self._format_generic(
            gene, ncbi_text, uniprot_text, string_text,
            disgenet_text, reactome_text, ensembl_text, go_text
        )

    # ------------------------------------------------------------------
    # Intent-specific layouts
    # ------------------------------------------------------------------

    def _format_structure(self, gene, pdb_text, uniprot_text) -> str:
        label = gene or "this protein"
        blocks = [f"Here is the structural biology information for **{label}**:\n"]

        s = _section_structure(gene, pdb_text)
        if s:
            blocks.append("─── PROTEIN STRUCTURE ───\n" + s)

        s = _section_protein_function(gene, uniprot_text)
        if s:
            blocks.append("─── WHAT THIS PROTEIN DOES ───\n" + s)

        blocks.append(
            "💡 Tip for experimentalists:\n"
            "  • Use the AlphaFold link above to visualise the 3D fold in your browser.\n"
            "  • Download the PDB file to open in PyMOL or ChimeraX.\n"
            "  • The RCSB PDB link shows all experimental crystal/cryo-EM structures."
        )
        blocks.append(_timestamp_note())
        return "\n\n".join(b for b in blocks if b.strip())


    def _format_gene_overview(
        self, gene, ncbi_text, uniprot_text, string_text,
        disgenet_text, reactome_text, go_text
    ) -> str:
        label = gene or "this gene"
        blocks = [f"Here is what the databases tell us about **{label}**:\n"]

        s = _section_gene_overview(gene, ncbi_text)
        if s:
            blocks.append("─── GENE OVERVIEW ───\n" + s)

        s = _section_protein_function(gene, uniprot_text)
        if s:
            blocks.append("─── WHAT THE PROTEIN DOES ───\n" + s)

        s = _section_diseases(gene, disgenet_text)
        if s:
            blocks.append("─── DISEASE ASSOCIATIONS ───\n" + s)

        s = _section_pathways(gene, reactome_text)
        if s:
            blocks.append("─── PATHWAYS INVOLVED ───\n" + s)

        s = _section_go_terms(gene, go_text)
        if s:
            blocks.append("─── GENE ONTOLOGY ANNOTATIONS ───\n" + s)

        s = _section_interactions(gene, string_text)
        if s:
            blocks.append("─── KEY PROTEIN INTERACTIONS ───\n" + s)

        footer = _sources_footer(ncbi_text, uniprot_text)
        if footer:
            blocks.append(footer)
        blocks.append(_timestamp_note())

        return "\n\n".join(b for b in blocks if b.strip())

    def _format_protein_only(self, gene, uniprot_text) -> str:
        label = gene or "this protein"
        blocks = [
            f"Here is what UniProt tells us about the protein encoded by **{label}**:\n",
            _section_protein_function(gene, uniprot_text) or uniprot_text,
            _sources_footer("", uniprot_text),
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_interactions(self, gene, string_text) -> str:
        label = gene or "this protein"
        blocks = [
            f"Here are the known protein interaction partners of **{label}** "
            f"from the STRING database:\n",
            _section_interactions(gene, string_text) or string_text,
            (
                "💡 Proteins that interact are usually part of the same "
                "pathway or molecular complex. Searching any partner name in "
                "UniProt will reveal its individual role."
            ),
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_diseases(self, gene, disgenet_text) -> str:
        label = gene or "this gene"
        blocks = [
            f"Here are the diseases and conditions associated with mutations "
            f"or dysregulation of **{label}**:\n",
            _section_diseases(gene, disgenet_text) or disgenet_text,
            (
                f"⚠️  Note: Being listed here does not mean every person with "
                f"a {label} mutation will develop these diseases. Penetrance, "
                "modifier genes, and environmental factors all play a role."
            ),
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_pathways(self, gene, reactome_text) -> str:
        label = gene or "this gene"
        blocks = [
            f"Here are the biological pathways that **{label}** participates in, "
            f"according to Reactome:\n",
            _section_pathways(gene, reactome_text) or reactome_text,
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_homology(self, gene, ensembl_text) -> str:
        label = gene or "this gene"
        blocks = [
            f"Here are the equivalent (orthologous) genes of **{label}** "
            f"in other species, from Ensembl:\n",
            _section_homology(gene, ensembl_text) or ensembl_text,
            (
                "🔬 Why does this matter? Studying the mouse or rat version of "
                "a human gene helps researchers understand its function and test "
                "potential treatments before human trials."
            ),
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_concept(self, ols_text) -> str:
        blocks = [
            "Here is a plain-English explanation from the Gene Ontology:\n",
            _section_concept_definition(ols_text) or ols_text,
            _timestamp_note(),
        ]
        return "\n\n".join(b for b in blocks if b.strip())

    def _format_generic(
        self, gene, ncbi_text, uniprot_text, string_text,
        disgenet_text, reactome_text, ensembl_text, go_text
    ) -> str:
        """
        Fallback: render every non-empty section in a consistent order.
        """
        label = gene or "the entity you asked about"
        blocks = [f"Here is what the databases tell us about **{label}**:\n"]

        for heading, text, builder in [
            ("GENE OVERVIEW (NCBI)",          ncbi_text,     lambda: _section_gene_overview(gene, ncbi_text)),
            ("PROTEIN FUNCTION (UniProt)",    uniprot_text,  lambda: _section_protein_function(gene, uniprot_text)),
            ("DISEASE ASSOCIATIONS",          disgenet_text, lambda: _section_diseases(gene, disgenet_text)),
            ("PATHWAYS (Reactome)",           reactome_text, lambda: _section_pathways(gene, reactome_text)),
            ("ORTHOLOGS (Ensembl)",           ensembl_text,  lambda: _section_homology(gene, ensembl_text)),
            ("INTERACTIONS (STRING)",         string_text,   lambda: _section_interactions(gene, string_text)),
            ("GENE ONTOLOGY",                 go_text,       lambda: _section_go_terms(gene, go_text)),
        ]:
            if text:
                body = builder()
                blocks.append(f"─── {heading} ───\n" + (body or text))

        footer = _sources_footer(ncbi_text, uniprot_text)
        if footer:
            blocks.append(footer)
        blocks.append(_timestamp_note())

        return "\n\n".join(b for b in blocks if b.strip())

    # ------------------------------------------------------------------
    # No-data fallback
    # ------------------------------------------------------------------

    def _no_info_response(self, gene: Optional[str], question: str) -> str:
        target = f"**{gene}**" if gene else "what you asked about"
        return (
            f"I searched NCBI, UniProt, and the other connected databases but "
            f"could not find enough information about {target} to give you a "
            f"reliable answer.\n\n"
            f"A few things to try:\n"
            f"  • Check that the gene symbol is the official HGNC name "
            f"(e.g., TP53, BRCA1, EGFR).\n"
            f"  • Rephrase your question — for example:\n"
            f"      – 'What is the function of TP53?'\n"
            f"      – 'What diseases are associated with BRCA1?'\n"
            f"      – 'What proteins interact with EGFR?'\n"
            f"  • Search directly at https://www.ncbi.nlm.nih.gov/gene or "
            f"https://www.uniprot.org\n\n"
            f"Your original question was: \"{question}\""
        )
