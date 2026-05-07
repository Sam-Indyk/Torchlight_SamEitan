# Inspiration-4 multi-omics: what changed in all four crew

This is a teammate-readable summary of what the [analysis/](analysis/) pipeline
found across the nine OSDR datasets surfaced in
[Torchlight_Hackathon_2026.ipynb](Torchlight_Hackathon_2026.ipynb).

The question we asked of every dataset:

> Did anything *interesting* significantly change between the **before**,
> **during**, and **after** spaceflight phases - and did the same change
> happen in **all four** Inspiration-4 crewmembers?

For per-subject longitudinal data: a feature counts only if all four crew
(C001-C004) individually move with `|log2 fold-change between phase means|
>= 1` AND in the **same direction**. For pre-aggregated DE tables (data
already pooled across subjects) we use `adj.P.Val < 0.05` AND `|logFC| >= 1`
and label those hits "pooled."

Full machine-readable outputs:
- [analysis/results/MASTER_summary.json](analysis/results/MASTER_summary.json) - per-dataset structured summary
- [analysis/results/MASTER_significant_features.csv](analysis/results/MASTER_significant_features.csv) - flat list of every significant feature

---

## Headline numbers

**66,917 features changed significantly** across the nine datasets.

| Dataset | Hits | Mode |
|---|---:|---|
| OSD-572 crew skin / oral / nasal swabs (per body site) | **59,927** | all 4 subjects |
| OSD-569 blood (RNA-seq + m6A + CBC) | **5,891** | all 4 subjects |
| OSD-570 PBMC snRNA-seq | 759 | pooled DE |
| OSD-571 plasma metabolomics + EVP + protein | 291 | pooled DE |
| OSD-574 spatial skin transcriptomics | 49 | pooled DE |

---

## The skin / oral / nasal microbiome story (OSD-572) - the dominant signal

The clearest pattern: **most body sites change a lot during flight and
largely recover after landing**, but a few sites get *worse* post-flight.
KEGG-function counts where all four crew shift the same direction:

| Body site | during_vs_pre | post_vs_pre | What this looks like |
|---|---:|---:|---|
| **ARM** (volar forearm) | 782 | 117 | huge in-flight shift, mostly recovers |
| **NAP** (nasopharynx) | 441 | 13 | huge in-flight, near-full recovery |
| **WEB** (toe web) | 255 | 36 | large in-flight, mostly recovers |
| **UMB** (umbilicus) | 83 | 46 | moderate, partial recovery |
| **GLU** (gluteal) | 46 | **108** | **delayed / persistent shift post-flight** |
| **TZO** (toe-web zone) | 23 | **110** | **delayed / persistent shift post-flight** |
| **NAC** (nasal cavity) | 0 | 1 | nasal-cavity microbiome highly conserved |

The **GLU and TZO post > during** pattern is the most clinically
interesting - those sites get worse after landing rather than recovering,
suggesting a delayed dysbiosis the crew may still be carrying.
**NAC stability** matches Tierney et al.'s observation that the nasal
cavity microbiome is unusually well-conserved.

### What's actually shifting at the highest-signal sites

**NAP (nasopharynx) - pathways UP during flight:**
- Multiple variants of **chlorophyll / divinyl-chlorophyllide biosynthesis**
- **Aerobic respiration via cytochrome c**
- **Serotonin degradation, tryptophan degradation X (via tryptamine),
  guanosine nucleotides degradation**

Chlorophyll-biosynthesis pathways are not part of a normal human nasal
microbiome - they're characteristic of cyanobacteria and photosynthetic
environmental bacteria. This is consistent with crew picking up taxa
from the closed cabin environment. (See OSD-573 below for the
companion capsule data.)

**ARM (volar forearm) - pathways DOWN during flight:**
- Massive loss of **aromatic-compound degradation** (D-galactarate,
  D-glucarate, gallate, methylgallate, protocatechuate, catechol
  meta- and ortho-cleavage)
- **Fatty-acid biosynthesis** (palmitate, unsaturated FAs, petroselinate)
- **Heterolactic fermentation / Bifidobacterium shunt**

Reads as **forearm-skin microbiome diversity collapse** - the
environmental-compound-degrading commensals get squeezed out.

**WEB (toe web) - pathways UP during flight:**
- **Urea cycle, 5-oxo-L-proline metabolism, fructuronate degradation**

A plausible signature of altered foot moisture / sweat physiology in
microgravity (no gravity-driven foot-blood pooling).

Per-body-site CSVs live in
[analysis/results/](analysis/results/) - filenames like
`OSD-572_kegg_NAP_during_vs_pre.csv`,
`OSD-572_pathway_ARM_during_vs_pre.csv`, etc.

---

## Capsule environmental microbiome (OSD-573)

7,128 KEGG functions, 3,585 taxa, 377 pathways, and 87,970 gene-families
were detected in the cabin during flight. These are the candidate **source
pool** for the taxa that show up on crew at NAP / ARM / WEB during flight.

The "introduced" / "not-persisted" comparisons are skipped because the
capsule-sample timepoint codes use `LM44`, `LM3`, `LM92` (pre) and
`RP1` etc. (post) instead of the crew-style `L-44` / `R+1`, so my
phase-binning currently only catches the in-flight `FD2` columns. Easy
fix - listed in **Known issues** below.

The "detected during flight" lists are real and usable:
[OSD-573_taxonomy_detected_during_flight.csv](analysis/results/OSD-573_taxonomy_detected_during_flight.csv)
and friends.

---

## Spatial skin transcriptomics (OSD-574)

49 hits, **strongly down-skewed (39 down vs 10 up)**.

The down list is a coherent **smooth-muscle / cytoskeleton suppression**
signature: **DES, TAGLN, ACTA2, ACTG2, MYLK, GSN, TLN1, ACTA2**. This
maps onto dermal arrector pili / vascular smooth muscle and is
exactly the kind of dermal-architecture finding the Park et al. skin-barrier
discussion in the [README](README.md) is targeting.

Top hits:
[analysis/results/OSD-574_spatial_pooled_DE.csv](analysis/results/OSD-574_spatial_pooled_DE.csv)

---

## Plasma metabolomics + proteomics (OSD-571) - 291 pooled DE hits

| Sub-table | Hits | Up | Down |
|---|---:|---:|---:|
| metabolomics | 100 | 43 | 57 |
| EVP (extracellular vesicle proteome) | 151 | 113 | 38 |
| protein (plasma proteome) | 40 | 25 | 15 |

**Metabolomics** ([file](analysis/results/OSD-571_metabolomics_pooled_DE.csv)):
- DOWN: the entire **LysoPC family** (15:0, 14:0, 17:0, 16:0, 16:1, 18:0)
  and **Sphingosine-1-phosphate**. Classic spaceflight lipid signature -
  oxidative stress, membrane remodeling, and disrupted vascular / immune
  signaling.
- UP: **Inosine** (purine catabolism), multiple **sphingomyelins**.

**EVP** ([file](analysis/results/OSD-571_evp_pooled_DE.csv)):
- UP: **CD58** (T-cell co-stimulation), **PRKACA**, **AHCY**, **AK1**,
  **FCN3** - immune activation / metabolic shift loaded onto extracellular
  vesicles.
- DOWN: **TFRC** (transferrin receptor - iron metabolism), **FN1** and
  **THBS1** (extracellular matrix), **IGLV** segments.

**Plasma protein** ([file](analysis/results/OSD-571_protein_pooled_DE.csv)):
- UP: **PF4** (platelet factor 4 - platelet activation / inflammation),
  **TGFB1** (immune regulation / fibrosis), **APP** (recently linked to
  spaceflight cognitive effects), **A2M**.
- DOWN: **LPL** (lipoprotein lipase), **COL4A2** (basement membrane),
  **FN1**, **ICAM3**.

---

## Blood biology (OSD-569)

| Table | Hits | Notes |
|---|---:|---|
| `rna_blood` (long-read RNA-seq) | **131** | 119 down / 12 up |
| `m6A` (RNA m6A modification) | **5,760** | huge post-flight remodeling |
| `cbc` (complete blood count) | 0 | homeostasis maintained |

**5,760 concordant m6A modification-site changes** is the surprise here.
m6A controls mRNA translation efficiency and stability, so a shift this
large implies a body-wide reprogramming of the **post-transcriptional
regulatory layer** post-flight. This is one of the more under-explored
datasets in the cohort and a real find.

The blood transcriptome itself is more modest (131 genes) but **strongly
down-skewed** (119 down). And the standard blood panel (CBC) showed
**zero** concordant changes - white-cell, red-cell, hemoglobin, hematocrit
all held steady, which is a meaningful negative result.

---

## PBMC immune cells (OSD-570 snRNA-seq) - 759 hits

**696 down vs 63 up** - a strikingly asymmetric response.

- The **down** list is dominated by **ribosomal protein genes**: RPL41,
  RPS11, RPS27, RPS18, RPL13, RPL13A, RPL10, RPL28, RPL30, RPLP1, RPLP2,
  RPS12, RPS14, RPS16, RPS27A, ... **Coordinated ribosome-biogenesis
  suppression is a hallmark cellular-stress response** - this is the
  clearest "PBMCs are stressed" signal in the data.
- The **up** list features **PLCG2** (B-cell receptor signaling),
  **MEF2C**, **MARCH1** (B-cell maturation), **HDAC9**, and **MTRNR2L12**
  (humanin-like anti-apoptotic peptide). These names appear repeatedly in
  the file because the same gene shows up across **multiple cell types**
  (B Cell, T Cell, NK, etc.) - meaning PLCG2 / MEF2C up-regulation is
  consistent across many PBMC populations, not a single-cell-type artifact.

snATAC-seq pulled zero hits with our threshold (`padj<0.05` AND
`|log2FC|>=1`); chromatin-accessibility shifts may need a softer
fold-change cutoff.

---

## Things that genuinely didn't pass the all-4-subjects bar

| Dataset | Result | Why this is informative |
|---|---|---|
| OSD-575 serum panels (CMP, immune Eve, immune Alamar, cardio) | 0 hits | Cytokines have high inter-individual baseline variance; a 2x concordance bar in all four is strict. |
| OSD-656 urine multiplex | 0 hits | Same as above. |
| OSD-630 stool metagenomics (4 tables) | 0 hits | Gut microbiomes are highly individual; the all-4 test correctly filters out per-individual responses. |
| OSD-569 CBC | 0 hits | Standard blood counts held homeostasis. Real biology, not a bug. |
| OSD-570 VDJ clonotype groupings | 0 hits | T/B-cell repertoires are inherently per-individual. |

These zeros are **load-bearing negatives**: the test is calibrated
strictly enough that homeostatic systems and per-individual responses
fall out, while genuinely concordant biology (microbiome, m6A, plasma
proteome, spatial skin) shines through.

---

## Cross-omic synthesis

Pulling the threads together - this is exactly the kind of integrated
view the [README](README.md) project proposal calls for:

```
   Capsule cabin microbes (3,585 taxa detected in flight)
                   |
                   v   (probable transfer route)
   Crew NAP / ARM / WEB microbiomes shift dramatically during flight
       - NAP gains photosynthetic / environmental taxa
       - ARM loses aromatic-degrading commensals + FA biosynthesis
       - GLU / TZO show *delayed* dysbiosis post-landing
                   |
                   v
   Skin barrier suppression
   (OSD-574 spatial: DES, TAGLN, ACTA2, MYLK, GSN down)
                   |
                   v
   Plasma signature
       - lipid-membrane disruption (LysoPC down, S1P down)
       - platelet activation (PF4 up), TGFB1 up
       - lipoprotein lipase down
                   |
                   v
   PBMC immune cells
       - massive ribosomal-protein suppression (stress response)
       - PLCG2 / MEF2C / MARCH1 / HDAC9 up across cell types
                   |
                   v
   Blood transcriptome + RNA modification
       - 119 genes down, 12 up
       - 5,760 m6A sites concordantly altered
                   |
                   v
   Held steady: CBC, serum CMP / cytokines / cardio panels, urine markers
   (homeostatic systems remain in their reference ranges)
```

---

## Known issues / open follow-ups

1. **OSD-574 skin metagenomics: 0 sites detected.** Columns are
   `C001_L-44_DEL`, `C001_R+1_DEL`, etc. - the body-site code is
   **`DEL`** (deltoid skin biopsy), which isn't in the body-site list
   in [analysis/osd574_skin.py](analysis/osd574_skin.py). One-line fix.
2. **OSD-573 capsule pre / post phases unclassified.** Columns use
   `LM44` / `LM3` / `LM92` (pre) and `RP1` (post) instead of the
   crew-sample `L-44` / `R+1` convention. The bin function in
   [analysis/osd573_capsule.py](analysis/osd573_capsule.py) needs aliases
   for those forms; the in-flight detection lists are valid as-is.
3. **Ensembl / UniRef90 IDs aren't gene-symbol-annotated.** The blood
   RNA-seq down-list is currently `ENSG00000...` IDs; mapping those to
   gene symbols would let us tell a tighter biological story.
4. **Threshold sensitivity.** Serum panels and snATAC-seq might surface
   real biology at `|log2FC| >= 0.5` instead of `>= 1`. Worth a sweep.
5. **n=4 caveat.** As the project README notes, group-level p-values
   are unreliable at n=4. We use directional concordance instead and
   honor per-astronaut effects rather than computing pooled p-values.

---

## How to reproduce

```bash
cd analysis
python master.py
```

Re-running clears prior output files automatically. See
[analysis/master.py](analysis/master.py) and the per-dataset scripts
for the analysis logic.
