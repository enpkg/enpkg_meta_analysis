# meta_analysis
Analyses  to enrich the Experimental Natural Products Knowledge Graph.

⚙️ Workflow part of [enpkg_workflow](https://github.com/mandelbrot-project/enpkg_workflow). First data have to be organized using [data_organization](https://github.com/mandelbrot-project/data_organization), taxonomy resolved using [taxo_enhancer](https://github.com/mandelbrot-project/taxo_enhancer) and spectra annotated using [indifiles_annotation](https://github.com/mandelbrot-project/indifiles_annotation) and/or [sirius_canopus](https://github.com/mandelbrot-project/sirius_canopus). 

Available meta-analyses:
- Meta-MN (through GNPS): link spectra between spectra of unaligned samples.
- MEMO: compare the chemistry of large amount of samples.
- Structures metadata fetcher: retrieve the NPClassifier taxonomy and the Wikidata ID of annotated structures.
- ChEMBL: retrieve compounds with an activity against a given target for biodereplication.

## 0. Clone repository and install environment

1. Clone this repository.
2. Create environment: 
```console 
conda env create -f environment.yml
```
3. Activate environment:  
```console 
conda activate meta_analysis
```

## 1. Create a meta-Molecular Network using GNPS
The meta-MN will be used to link features with similar fragmentation spectra among the different samples. In terms of GNPS workflow, it correspond to a classical MN. In our case, it is not a "real" classical MN because we performed feature detection and thus our potential isomers are separated.  

### Worflow
First, we need to create a .mgf file that aggregated samples' individual .mgf files. To do so, run the following command:

```console
python .\src\mgf_aggregator.py -p path/to/your/data/directory/ -ion {pos or neg} -out {output_name}
```
This will create 3 files in **path/to/your/data/directory/001_aggregated_spectra/**:

| Filename | Description |
| :------- | :-----------|
{output_name}_params.csv | A summary of the input samples used to generate the corresponding aggregated .mgf file
{output_name}_metadata.csv | The spectra metadata and orginal ID for each spectrum
{output_name}.mgf | The aggregated spectra in a GNPS-ready format

Once we have the aggregated .mgf file, launch a GNPS classical MN on it (such as this [example](https://gnps.ucsd.edu/ProteoSAFe/status.jsp?task=822f2d6ea4a34d18b059689597b06cf4))
When the job is finished, download the result using the following command:

```console
python .\src\gnps_fetcher.py -p path/to/your/data/directory/ --job_id {gnps_job_id}
```
The GNPS output will be dowloaded in **path/to/your/data/directory/002_gnps/{gnps_job_id}/**

## 2. MEMO analysis
Using individual fragmentation spectra files, it is possible to generate for each sample a MS2-based fingerprint, or [MEMO](https://github.com/mandelbrot-project/memo) vector. This allows to rapidly compare large amount of chemo-diverse samples to identify potential similarities in composition among them. Here, the aligned MEMO matrix of all samples' fingerprints will be generated.
### Worflow
```console
python .\src\memo_unaligned_repo.py -p path/to/your/data/directory/ --ionization {pos, neg or both} --output {output_name}
```

This will create 2 files in **path/to/your/data/directory/003_memo_analysis/**:

More parameters inherent to the vectorization process are available, for help use:
| Filename | Description |
| :------- | :-----------|
{output_name}\_params.csv | Parameters used to generate the corresponding MEMO matrix
{output_name}.gz | The MEMO matrix (with gzip compression)

Fo help about the MEMO vectorization parameters, use:

```console
python .\src\memo_unaligned_repo.py --help
```

## 3. Fetching structures' metadata
To enrich our knowledge graph, we will fetch for dereplicated structures their Wikidata id and their [NPClassifier](https://pubs.acs.org/doi/10.1021/acs.jnatprod.1c00399) taxonomy. Because the NPClassifier API can be slow for large amount of structures, results are stored in a SQL database. You can use the same SQL DB in your different project to avoid processing multiple times the same structure. The first time you run the process, a new SQL DB will be created at the default location (**./output_data/sql_db/{sql_name.db}**).
### Worflow
To do so, use the following command:
```console
python .\src\chemo_info_fetcher.py -p path/to/your/data/directory/ --sql_name structures_metadata.db --gnps_job_id {gnps_job_id}
```
## 4. Fetching ChEMBL compounds with activity against a given target
To enrich our knowledge graph, it is possible to include compounds from ChEMBL with activity against a target of interest. This could be fone using the ChEMBL KG itself, but it is unfortunately not available. Besides fetching compounds from ChEMBL, it is also possible to filter them according to their [NP likeliness](https://pubs.acs.org/doi/10.1021/ci700286x) score to remove synthetic compounds. 

To search for your target id go to https://www.ebi.ac.uk/chembl/. Format is CHEMBLXXXX e.g. https://www.ebi.ac.uk/chembl/target_report_card/CHEMBL364/

### Worflow
To do so, use the following command:
```console
python .\src\download_chembl.py -id {chembl_target_id} -npl {minimal_NP_like_score}
```
The resulting table will be placed in **./output_data/chembl/{target_id}\_np_like_min_{min_NPlike_score}.csv**.
