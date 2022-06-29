import pandas as pd 
from pandas import json_normalize
import requests
import os
from json import JSONDecodeError
from tqdm import tqdm
import sqlite3
from sqlite3 import Error
from pathlib import Path
import argparse
import textwrap
from pathlib import Path
from rdkit.Chem import AllChem

p = Path(__file__).parents[1]
os.chdir(p)
print(p)

""" Argument parser """

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
        This script generates an SQL DB (structures_metadata.db) in the /output_data/sql_db/ with WD ID and NPClassfier taxonomy for annotated structures.
        '''))
parser.add_argument('-p', '--sample_dir_path', required=True,
                    help='The path to the directory where samples folders to process are located')
parser.add_argument('-sql', '--sql_name', default = 'structures_metadata.db',
                    help='The name of a previsouly generated SQL DB (that will be updated with new structures). \
                        If no SQL DB is available, will create new one /output_data/sql_db/')
parser.add_argument('-id', '--gnps_job_id', required = False, 
                    help='The GNPS job ID of the meta-MN corresponding to sample_dir_path')

args = parser.parse_args()
sample_dir_path = args.sample_dir_path
sql_path = os.path.join(os.getcwd() + '/output_data/sql_db/' + args.sql_name)
gnps_id = args.gnps_job_id

""" Functions """

def get_all_ik(url):
    query = '''
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?ik ?wd ?isomeric_smiles
WHERE{
    ?wd wdt:P235 ?ik .
    optional { ?wd wdt:P2017 ?isomeric_smiles } 
}
  '''
    r = requests.get(url, params={'format': 'json', 'query': query})
    try:
      data = r.json()
      results = pd.DataFrame.from_dict(data).results.bindings
      df = json_normalize(results)
      df.rename(columns={'wd.value':'wikidata_id', 'ik.value':'inchikey', 'isomeric_smiles.value': 'isomeric_smiles'}, inplace=True)
      return df[['wikidata_id', 'inchikey', 'isomeric_smiles']]
    except JSONDecodeError:
       return None


def update_sqldb(dataframe, sql_path):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(sql_path)
        dataframe.to_sql('structures_metadata', con=conn, if_exists='append')
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

def get_NPC(short_ik_smiles_query, db_ik, processed_ik, npc_api = "https://npclassifier.ucsd.edu/classify?smiles="):   
    for sik, smiles in tqdm(short_ik_smiles_query.items(), leave=False):
        if (sik not in processed_ik) & (sik not in db_ik):
            processed_ik[sik] = {}
            processed_ik[sik]['smiles'] = smiles
            url = npc_api + smiles
            seperator = "|"
            try:
                response = requests.get(url)
            except HTTPError:
                processed_ik[sik]['npc_pathway'] = 'unknown'
                processed_ik[sik]['npc_superclass'] = 'unknown'
                processed_ik[sik]['npc_class'] = 'unknown'
                continue                        
            try:
                data = response.json()
            except ValueError:  
                processed_ik[sik]['npc_pathway'] = 'unknown'
                processed_ik[sik]['npc_superclass'] = 'unknown'
                processed_ik[sik]['npc_class'] = 'unknown'
                continue
                
            if len(data['pathway_results']) > 0:
                joined = seperator.join(data['pathway_results'])
                processed_ik[sik]['npc_pathway'] = joined
            else:
                processed_ik[sik]['npc_pathway'] ='unknown'
                
            if len(data['superclass_results']) > 0:
                joined = seperator.join(data['superclass_results'])
                processed_ik[sik]['npc_superclass'] = joined
            else:
                processed_ik[sik]['npc_superclass'] = 'unknown'
                
            if len(data['class_results']) > 0:
                joined = seperator.join(data['class_results'])
                processed_ik[sik]['npc_class'] = joined
            else:
                processed_ik[sik]['npc_class'] = 'unknown'
    return  processed_ik
    
# These lines allows to make sure that we are placed at the repo directory level 
p = Path(__file__).parents[2]
os.chdir(p)

wd_url = 'https://query.wikidata.org/sparql'

path = os.path.normpath(sample_dir_path)
samples_dir = [directory for directory in os.listdir(path)]

# Check if sql DB of metadata already exist and load short IK if yes
if os.path.exists(sql_path):
    dat = sqlite3.connect(sql_path)
    query = dat.execute("SELECT * From structures_metadata")
    cols = [column[0] for column in query.description]
    df_metadata = pd.DataFrame.from_records(data = query.fetchall(), columns = cols)
    short_ik_in_db = list(set(list(df_metadata['short_inchikey'])))
    dat.close()
else:
    short_ik_in_db = []
    
# First load all unique short IK from ISDB annotation as long as their metadata (smiles 2D, NPC classes)
metadata_short_ik = {}
print('Processing ISDB results')
for directory in tqdm(samples_dir):
    isdb_path_pos = os.path.join(path, directory, 'pos', 'isdb', directory  + '_isdb_reweighted_flat_pos.tsv')
    isdb_path_neg = os.path.join(path, directory, 'neg', 'isdb', directory  + '_isdb_reweighted_flat_neg.tsv')
    isdb_annotations_pos = None
    isdb_annotations_neg = None
    try:
        isdb_annotations_pos = pd.read_csv(isdb_path_pos, sep='\t')\
            [['short_inchikey','structure_smiles_2D', 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class']]
    except FileNotFoundError:
        pass
    try:
        isdb_annotations_neg = pd.read_csv(isdb_path_neg, sep='\t')\
            [['short_inchikey','structure_smiles_2D', 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class']] 
    except FileNotFoundError:
        pass
        
    if (isdb_annotations_pos is not None) & (isdb_annotations_neg is not None):
        isdb_annotations = pd.concat([isdb_annotations_pos, isdb_annotations_neg])
        del(isdb_annotations_pos, isdb_annotations_neg)
    elif isdb_annotations_pos is not None:
        isdb_annotations = isdb_annotations_pos.copy()
        del(isdb_annotations_pos)
    elif isdb_annotations_neg is not None:
        isdb_annotations = isdb_annotations_neg.copy()
        del(isdb_annotations_neg)
    else:
        continue
    
    #print(f'Processing ISDB results for sample {directory}')
    
    isdb_annotations.drop_duplicates(subset=['short_inchikey'], inplace=True)
    short_ik = list(isdb_annotations['short_inchikey'])    
    for sik in short_ik:
        if (sik not in metadata_short_ik) & (sik not in short_ik_in_db):
            row = isdb_annotations[isdb_annotations['short_inchikey'] == sik]
            metadata_short_ik[sik] = {}
            metadata_short_ik[sik]['smiles'] = row['structure_smiles_2D'].values[0]
            metadata_short_ik[sik]['npc_pathway'] = row['structure_taxonomy_npclassifier_01pathway'].values[0]
            metadata_short_ik[sik]['npc_superclass'] = row['structure_taxonomy_npclassifier_02superclass'].values[0]
            metadata_short_ik[sik]['npc_class'] = row['structure_taxonomy_npclassifier_03class'].values[0]

# Add unique IK from GNPS annotations
print('Processing GNPS results')

gnps_file = os.listdir(os.path.join(path, '002_gnps', gnps_id, 'result_specnets_DB'))[0]
gnps_annotations_path = os.path.join(path, '002_gnps', gnps_id, 'result_specnets_DB', gnps_file)
short_ik_smiles_query = {}
try:
    gnps_annotations = pd.read_csv(gnps_annotations_path, sep='\t', usecols=['Smiles', 'InChIKey-Planar'])
    #print(f'GNPS job found with {len(gnps_annotations)} annotations')
    for _, row in gnps_annotations.iterrows():
        mol = AllChem.MolFromSmiles(row["Smiles"])
        if mol is not None:
            smiles =  AllChem.MolToSmiles(mol)
            short_ik_smiles_query[row['InChIKey-Planar']] = smiles
    metadata_short_ik = get_NPC(short_ik_smiles_query = short_ik_smiles_query, db_ik = short_ik_in_db, processed_ik = metadata_short_ik)
except FileNotFoundError:
    pass

# Add unique short IK from Sirius annotations + add NPC metadata
print('Processing Sirius results')

for directory in tqdm(samples_dir):
    sirius_path_pos = os.path.join(path, directory, 'pos',  directory + '_WORKSPACE_SIRIUS', 'compound_identifications.tsv')
    sirius_path_neg = os.path.join(path, directory, 'neg',  directory + '_WORKSPACE_SIRIUS', 'compound_identifications.tsv')
    sirius_annotations_pos = None
    sirius_annotations_neg = None
    try:
        sirius_annotations_pos = pd.read_csv(sirius_path_pos, sep='\t')\
            [['InChIkey2D','smiles']]
    except FileNotFoundError:
        pass
    try:
        sirius_annotations_neg = pd.read_csv(sirius_path_neg, sep='\t')\
            [['InChIkey2D','smiles']]
    except FileNotFoundError:
        pass    

    if (sirius_annotations_pos is not None) & (sirius_annotations_neg is not None):
        sirius_annotations = pd.concat([sirius_annotations_pos, sirius_annotations_neg])
        del(sirius_annotations_pos, sirius_annotations_neg)
    elif sirius_annotations_pos is not None:
        sirius_annotations = sirius_annotations_pos.copy()
        del(sirius_annotations_pos)
    elif sirius_annotations_neg is not None:
        sirius_annotations = sirius_annotations_neg.copy()
        del(sirius_annotations_neg)
    else:
        continue
    
    #print(f'Processing sirius results for sample {len(sirius_annotations)}')
    
    sirius_annotations.drop_duplicates(subset=['InChIkey2D'], inplace=True)        
    short_ik = list(sirius_annotations['InChIkey2D'])
    short_ik_smiles_query = pd.Series(sirius_annotations.smiles.values,index=sirius_annotations.InChIkey2D).to_dict()
    metadata_short_ik = get_NPC(short_ik_smiles_query = short_ik_smiles_query, db_ik = short_ik_in_db, processed_ik = metadata_short_ik)
     
df_ik_meta = pd.DataFrame.from_dict(metadata_short_ik, orient='index')\
    .reset_index().rename(columns={'index':'short_inchikey'}).fillna('unknown')

print('Getting WD id and formatting results')
 
if len(df_ik_meta) > 0:
    wd_all = get_all_ik(wd_url)
    wd_all['short_inchikey'] = wd_all['inchikey'].str[:14]
    wd_filtred = wd_all[wd_all['short_inchikey'].isin(list(metadata_short_ik.keys()))]
    
    df_total = wd_filtred.merge(df_ik_meta, on='short_inchikey', how='outer')
    df_total['isomeric_smiles'] = df_total['isomeric_smiles'].fillna(df_total['smiles'])
    df_total = df_total.fillna('no_wikidata_match')
                
    update_sqldb(df_total, sql_path)
