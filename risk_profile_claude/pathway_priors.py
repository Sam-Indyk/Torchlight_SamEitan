"""Hand-curated cascades linking spaceflight stressors to the molecular
observations in dashboard_data.json.

Each cascade is a hypothesized chain:

    [stressor]  →  [root cause node]  →  [intermediate signaling]  →
        [downstream observable molecules with expected direction]

The cascade_inference module scores each cascade against the actual
observations in the analysis pipeline. A cascade with many of its
terminal observations matched (in the right direction) is a candidate
upstream cause for the dashboard's downstream readings.

These are HYPOTHESIS-GENERATING. n = 4 cannot prove causation. The
panel that renders these is explicit about that.

References for each cascade are listed in the `evidence` field. They
are real, citeable papers (not AI-fabricated).
"""

from __future__ import annotations


# Each terminal observation entry:
#   feature           : substring matched against analysis/results/ feature names
#   direction         : "up" or "down"
#   weight            : importance in the score (1.0 = canonical, 0.5 = supporting)
#   source_csv_glob   : which analysis/results/ CSVs to look in (substring)

CASCADES: list[dict] = [
    {
        "id": "mechano_nfkb",
        "name": "Microgravity → mechanotransduction → NF-κB → cytokine cascade",
        "stressor": "microgravity",
        "root_cause": "YAP/TAZ mechanosensing disruption (loss of cytoskeletal "
                      "tension)",
        "mechanism": (
            "Microgravity removes the gravitational load that normally "
            "stretches the actin cytoskeleton. Without that mechanical "
            "tension, YAP/TAZ co-activators dissociate from the nucleus "
            "and Hippo-pathway brake on NF-κB is lifted. NF-κB then "
            "transcribes IL-6, TNF-α, and CRP-induction signals."
        ),
        "intermediate_nodes": [
            "actin cytoskeleton (decreased tension)",
            "RhoA/ROCK pathway (suppressed)",
            "YAP/TAZ (cytoplasmic retention)",
            "NF-κB (nuclear translocation)",
        ],
        "terminal_observations": [
            {"feature": "il_6",   "direction": "up", "weight": 1.0,
             "source_csv_substr": "OSD-575"},
            {"feature": "tnf",    "direction": "up", "weight": 1.0,
             "source_csv_substr": "OSD-575"},
            {"feature": "crp",    "direction": "up", "weight": 0.9,
             "source_csv_substr": "OSD-575"},
            {"feature": "tgfb",   "direction": "up", "weight": 0.6,
             "source_csv_substr": "OSD-571"},
            {"feature": "pf4",    "direction": "up", "weight": 0.5,
             "source_csv_substr": "OSD-571"},
        ],
        "evidence": (
            "Versari et al. 2013 (FASEB J): cytoskeletal disruption in "
            "microgravity → NF-κB activation in endothelial cells. "
            "Crawford-Young 2006 (Int J Dev Biol): comprehensive review "
            "of microgravity mechanotransduction effects."
        ),
        "confidence": "moderate",
    },

    {
        "id": "radiation_ros_mito",
        "name": "Cosmic radiation → ROS → mitochondrial dysfunction → metabolic shift",
        "stressor": "radiation",
        "root_cause": "Electron-transport-chain (ETC complex I/III) damage from "
                      "high-LET radiation",
        "mechanism": (
            "Galactic cosmic rays and trapped protons deposit energy on "
            "ETC complex I and III, increasing electron leak and "
            "superoxide production. ROS damages mtDNA and lipid "
            "membranes, suppressing TCA-cycle enzyme activity and "
            "fatty-acid β-oxidation. Acylcarnitines accumulate because "
            "carnitine-acyl transfer outpaces β-oxidation."
        ),
        "intermediate_nodes": [
            "ETC complex I/III (damaged)",
            "ROS (elevated)",
            "mtDNA (oxidative damage)",
            "TCA-cycle enzymes (suppressed)",
            "β-oxidation (reduced flux)",
        ],
        "terminal_observations": [
            {"feature": "succinate",     "direction": "up",   "weight": 0.8,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "fumarate",      "direction": "down", "weight": 0.7,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "acylcarnitine", "direction": "up",   "weight": 1.0,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "carnitine",     "direction": "up",   "weight": 0.6,
             "source_csv_substr": "OSD-571_metabolomics"},
        ],
        "evidence": (
            "da Silveira et al. 2020 (Cell): NASA Twins study found "
            "TCA-cycle and β-oxidation suppression after ISS exposure. "
            "Garrett-Bakelman et al. 2019 (Science): mitochondrial "
            "dysfunction signature in spaceflight cohorts. Cucinotta "
            "& Durante 2006 (Lancet Oncol) on radiation-induced ROS."
        ),
        "confidence": "moderate",
    },

    {
        "id": "membrane_oxidation",
        "name": "Oxidative stress → membrane lipid peroxidation → LysoPC suppression",
        "stressor": "radiation + microgravity (combined oxidative stress)",
        "root_cause": "Phospholipase A2 substrate depletion via membrane lipid "
                      "peroxidation",
        "mechanism": (
            "Healthy phospholipase A2 (PLA2) cleaves phosphatidylcholine "
            "into LysoPC + a free fatty acid. When ROS peroxidizes the "
            "PC sn-2 acyl chains first, the substrate is altered and PLA2 "
            "products are reduced. The LysoPC family (15:0, 16:0, 17:0, "
            "18:0) drops in plasma — the canonical spaceflight lipid "
            "signature reported in Tierney 2024."
        ),
        "intermediate_nodes": [
            "Membrane PC (oxidized)",
            "Lipid peroxide (elevated)",
            "PLA2 (substrate-depleted)",
        ],
        "terminal_observations": [
            {"feature": "lysopc",       "direction": "down", "weight": 1.0,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "sphingosine", "direction": "down", "weight": 0.7,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "s1p",         "direction": "down", "weight": 0.7,
             "source_csv_substr": "OSD-571_metabolomics"},
            {"feature": "sphingomyelin","direction": "up",  "weight": 0.6,
             "source_csv_substr": "OSD-571_metabolomics"},
        ],
        "evidence": (
            "Tierney et al. 2024 (Inspiration-4 multi-omics): LysoPC "
            "family suppression at R+1 across the cohort. da Silveira "
            "2020 (Cell): comparable lipid-membrane signature in twin "
            "study. Halliwell & Gutteridge (textbook) on ROS-driven "
            "membrane peroxidation chemistry."
        ),
        "confidence": "high",
    },

    {
        "id": "ribosome_stress",
        "name": "Cellular stress → ATF4/eIF2α → ribosome biogenesis suppression",
        "stressor": "microgravity (cellular stress response)",
        "root_cause": "Integrated stress response activation via PERK/eIF2α "
                      "phosphorylation",
        "mechanism": (
            "Cellular stress (microgravity-induced) phosphorylates "
            "eIF2α via PERK, GCN2, or HRI. eIF2α-P inhibits global "
            "translation initiation and selectively up-regulates ATF4. "
            "ATF4 represses ribosomal-protein gene transcription as a "
            "stress-conservation response. PBMCs in OSD-570 show "
            "exactly this signature: massive coordinated suppression of "
            "RPL/RPS gene family across multiple cell types."
        ),
        "intermediate_nodes": [
            "PERK / GCN2 (active)",
            "eIF2α-P (elevated)",
            "ATF4 (induced)",
            "RPL/RPS transcription (suppressed)",
        ],
        "terminal_observations": [
            {"feature": "rpl",  "direction": "down", "weight": 1.0,
             "source_csv_substr": "OSD-570_snrnaseq"},
            {"feature": "rps",  "direction": "down", "weight": 1.0,
             "source_csv_substr": "OSD-570_snrnaseq"},
            {"feature": "atf4", "direction": "up",   "weight": 0.7,
             "source_csv_substr": "OSD-570_snrnaseq"},
        ],
        "evidence": (
            "FINDINGS.md OSD-570 row: 696 down vs 63 up in PBMC "
            "snRNA-seq, dominated by ribosomal-protein gene suppression "
            "across cell types. Pakos-Zebrucka et al. 2016 (EMBO Rep) "
            "review of the integrated stress response."
        ),
        "confidence": "high",
    },

    {
        "id": "barrier_actin_loss",
        "name": "Microgravity → arrector pili / vascular smooth muscle → skin barrier",
        "stressor": "microgravity",
        "root_cause": "Loss of dermal smooth-muscle / vascular tone",
        "mechanism": (
            "Microgravity removes the mechanical loading on dermal "
            "arrector-pili and vascular smooth-muscle cells. Without "
            "load, smooth-muscle markers (DES, TAGLN, ACTA2, ACTG2, "
            "MYLK, GSN) coordinately drop. The skin's mechanical "
            "scaffolding weakens, contributing to the barrier-function "
            "phenotype Park 2024 reports."
        ),
        "intermediate_nodes": [
            "Mechanical loading (absent)",
            "Smooth-muscle cell program (suppressed)",
            "Cytoskeletal/dermal architecture (altered)",
        ],
        "terminal_observations": [
            {"feature": "des",   "direction": "down", "weight": 1.0,
             "source_csv_substr": "OSD-574_spatial"},
            {"feature": "tagln", "direction": "down", "weight": 1.0,
             "source_csv_substr": "OSD-574_spatial"},
            {"feature": "acta2", "direction": "down", "weight": 0.9,
             "source_csv_substr": "OSD-574_spatial"},
            {"feature": "actg2", "direction": "down", "weight": 0.7,
             "source_csv_substr": "OSD-574_spatial"},
            {"feature": "mylk",  "direction": "down", "weight": 0.7,
             "source_csv_substr": "OSD-574_spatial"},
            {"feature": "gsn",   "direction": "down", "weight": 0.6,
             "source_csv_substr": "OSD-574_spatial"},
        ],
        "evidence": (
            "Park et al. 2024 (Inspiration-4 skin): smooth-muscle / "
            "cytoskeleton suppression signature in deltoid biopsies. "
            "FINDINGS.md OSD-574: 39 down vs 10 up, coherent with this "
            "cascade. Mao et al. 2018 (NPJ Microgravity) on dermal "
            "mechanotransduction."
        ),
        "confidence": "high",
    },

    {
        "id": "platelet_endothelial",
        "name": "Endothelial shear stress change → platelet activation",
        "stressor": "microgravity (cardiovascular fluid shift)",
        "root_cause": "Endothelial mechanotransduction shift from gravity-driven "
                      "flow to redistributed venous return",
        "mechanism": (
            "Spaceflight shifts ~2 L of fluid from the lower body to the "
            "upper torso and head. The change in shear stress on "
            "endothelial cells alters their gene-expression program and "
            "promotes platelet activation. Activated platelets release "
            "PF4, which appears in plasma proteomics."
        ),
        "intermediate_nodes": [
            "Cephalad fluid shift",
            "Endothelial shear stress (altered)",
            "Endothelial activation",
            "Platelet activation (PF4 release)",
        ],
        "terminal_observations": [
            {"feature": "pf4",   "direction": "up",   "weight": 1.0,
             "source_csv_substr": "OSD-571_protein"},
            {"feature": "thbs",  "direction": "down", "weight": 0.5,
             "source_csv_substr": "OSD-571_evp"},
            {"feature": "fn1",   "direction": "down", "weight": 0.5,
             "source_csv_substr": "OSD-571_evp"},
        ],
        "evidence": (
            "FINDINGS.md OSD-571 protein row: PF4 up (platelet factor 4 / "
            "platelet activation) confirmed. Hughson et al. 2018 (NEJM) "
            "on cephalad fluid shifts. Stenger 2017 on cardiovascular "
            "deconditioning in microgravity."
        ),
        "confidence": "moderate",
    },

    {
        "id": "ddr_radiation",
        "name": "Cosmic radiation → DNA double-strand breaks → ATM/ATR activation",
        "stressor": "radiation",
        "root_cause": "High-LET radiation-induced DNA double-strand breaks",
        "mechanism": (
            "GCRs and SPE protons cause DNA strand breaks in actively "
            "dividing cells. ATM phosphorylates H2AX (γH2AX foci), "
            "recruiting BRCA1/2 and the homologous-recombination "
            "machinery. p53 is activated, inducing GADD45A and cell-"
            "cycle arrest. The whole cassette of canonical DDR genes "
            "(ATM, ATR, BRCA1/2, TP53, H2AFX, RAD51, GADD45A, XRCC) "
            "would be elevated post-flight."
        ),
        "intermediate_nodes": [
            "DNA double-strand breaks",
            "ATM / ATR (active)",
            "γH2AX (phosphorylated)",
            "p53 (stabilized)",
            "DDR transcriptional program (induced)",
        ],
        "terminal_observations": [
            {"feature": "atm",     "direction": "up", "weight": 1.0,
             "source_csv_substr": "OSD-569_rna"},
            {"feature": "tp53",    "direction": "up", "weight": 1.0,
             "source_csv_substr": "OSD-569_rna"},
            {"feature": "brca",    "direction": "up", "weight": 0.8,
             "source_csv_substr": "OSD-569_rna"},
            {"feature": "h2afx",   "direction": "up", "weight": 0.7,
             "source_csv_substr": "OSD-569_rna"},
            {"feature": "gadd45",  "direction": "up", "weight": 0.7,
             "source_csv_substr": "OSD-569_rna"},
        ],
        "evidence": (
            "Garrett-Bakelman et al. 2019 (Science): DDR signature in "
            "NASA Twins blood RNA-seq. Cucinotta & Durante 2006 on "
            "high-LET radiation biology. Pending Ensembl-to-symbol "
            "mapping in our pipeline (FINDINGS.md issue #3) before this "
            "cascade can be matched against real data."
        ),
        "confidence": "expected (currently unmatchable: see DDR axis)",
    },

    {
        "id": "m6a_remodel",
        "name": "Cellular stress → METTL3/METTL14 → m6A RNA methylation remodeling",
        "stressor": "microgravity + radiation (combined)",
        "root_cause": "m6A methyltransferase complex (METTL3/METTL14) activity "
                      "shift",
        "mechanism": (
            "Cellular stress alters METTL3/METTL14 activity, broadly "
            "remodeling N6-methyladenosine (m6A) marks across the "
            "transcriptome. m6A controls mRNA stability and translation, "
            "so a body-wide m6A shift implies coordinated post-"
            "transcriptional reprogramming. OSD-569 found 5,760 "
            "concordantly altered m6A sites at R+1 — one of the largest "
            "post-transcriptional shifts reported in any spaceflight "
            "study."
        ),
        "intermediate_nodes": [
            "Cellular stress (combined)",
            "METTL3 / METTL14 (activity shift)",
            "Transcriptome-wide m6A pattern (remodeled)",
            "mRNA stability + translation (rebalanced)",
        ],
        "terminal_observations": [
            # Match any transcript-level m6A site (ENST...) in the OSD-569 m6A
            # CSV. Direction = either since m6A remodeling can shift either way
            # at any given site; the cohort-level signal is the *number* of
            # concordantly-altered sites (5,760), not the sign.
            {"feature": "enst", "direction": "either", "weight": 1.0,
             "source_csv_substr": "OSD-569_m6A"},
        ],
        "evidence": (
            "FINDINGS.md OSD-569 row: 5,760 concordant m6A modification "
            "sites altered, one of the strongest signals in the entire "
            "dataset. Wang et al. 2014 (Cell) on the m6A epitranscriptome. "
            "Liu et al. 2020 (Mol Cell) on m6A as a stress-response "
            "regulator."
        ),
        "confidence": "high",
    },
]


def list_cascades() -> list[dict]:
    """Return the cascade table (read-only view)."""
    return [dict(c) for c in CASCADES]


def get(cascade_id: str) -> dict | None:
    for c in CASCADES:
        if c["id"] == cascade_id:
            return dict(c)
    return None
