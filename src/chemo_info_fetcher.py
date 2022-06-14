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

""" Argument parser """

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
        This script generates an SQL DB (structures_metadata.db) in the directory where samples folders are located with WD ID and NPClassfier taxonomy for annotated structures.
         --------------------------------
            Arguments:
            - Path to the directory where samples folders are located
        '''))
parser.add_argument('--sample_dir_path', required=True,
                    help='The path to the directory where samples folders to process are located')

args = parser.parse_args()
sample_dir_path = args.sample_dir_path

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


def update_sqldb(dataframe, db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        dataframe.to_sql('structures_metadata', con=conn, if_exists='append')
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()

# These lines allows to make sure that we are placed at the repo directory level 
p = Path(__file__).parents[2]
os.chdir(p)

wd_url = 'https://query.wikidata.org/sparql'
npc_api = "https://npclassifier.ucsd.edu/classify?smiles="

path = os.path.normpath(sample_dir_path)
samples_dir = [directory for directory in os.listdir(path)]

# Check if sql DB of metadata already exist and load short IK if yes
if os.path.exists(path+'/structures_metadata.db'):
    dat = sqlite3.connect(path+'/structures_metadata.db')
    query = dat.execute("SELECT * From structures_metadata")
    cols = [column[0] for column in query.description]
    df_metadata = pd.DataFrame.from_records(data = query.fetchall(), columns = cols)
    short_ik_in_db = list(set(list(df_metadata['short_inchikey'])))
    dat.close()
else:
    short_ik_in_db = []
    
# First load all unique short IK from ISDB annotation as long as their metadata (smiles 2D, NPC classes)
metadata_short_ik = {}
for directory in samples_dir:
    isdb_path = os.path.join(path, directory, directory  + '_isdb_matched_pos_repond_flat.tsv')
    try:
        isdb_annotations = pd.read_csv(isdb_path, sep='\t')\
            [['short_inchikey','structure_smiles_2D', 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class']]
        print(f'loading {directory} done')
    except FileNotFoundError:
        continue
      
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

# Add unique short IK from Sirius annotations + add NPC metadata
for directory in samples_dir:
    sirius_path = os.path.join(path, directory, directory + '_WORKSPACE_SIRIUS', 'compound_identifications.tsv')
    try:
        sirius_annotations = pd.read_csv(sirius_path, sep='\t')\
            [['InChIkey2D','smiles']]
        print(f'loading {directory} done')
        print(len(metadata_short_ik))
    except FileNotFoundError:
        continue                
    sirius_annotations.drop_duplicates(subset=['InChIkey2D'], inplace=True)        
    short_ik = list(sirius_annotations['InChIkey2D'])
    for sik in tqdm(short_ik):
        if (sik not in metadata_short_ik) & (sik not in short_ik_in_db):
            row = sirius_annotations[sirius_annotations['InChIkey2D'] == sik]
            metadata_short_ik[sik] = {}
            metadata_short_ik[sik]['smiles'] = row['smiles'].values[0]
            smiles = row['smiles'].values[0]
            url = npc_api + smiles
            seperator = "|"
            try:
                response = requests.get(url)
            except HTTPError:
                metadata_short_ik[sik]['npc_pathway'] = 'unknown'
                metadata_short_ik[sik]['npc_superclass'] = 'unknown'
                metadata_short_ik[sik]['npc_class'] = 'unknown'
                        
            try:
                data = response.json()
            except ValueError:  
                metadata_short_ik[sik]['npc_pathway'] = 'unknown'
                metadata_short_ik[sik]['npc_superclass'] = 'unknown'
                metadata_short_ik[sik]['npc_class'] = 'unknown'
                
            if len(data['pathway_results']) > 0:
                joined = seperator.join(data['pathway_results'])
                metadata_short_ik[sik]['npc_pathway'] = joined
            else:
                metadata_short_ik[sik]['npc_pathway'] ='unknown'
                
            if len(data['superclass_results']) > 0:
                joined = seperator.join(data['superclass_results'])
                metadata_short_ik[sik]['npc_superclass'] = joined
            else:
                metadata_short_ik[sik]['npc_superclass'] = 'unknown'
                
            if len(data['class_results']) > 0:
                joined = seperator.join(data['class_results'])
                metadata_short_ik[sik]['npc_class'] = joined
            else:
                metadata_short_ik[sik]['npc_class'] = 'unknown'

df_ik_meta = pd.DataFrame.from_dict(metadata_short_ik, orient='index')\
    .reset_index().rename(columns={'index':'short_inchikey'}).fillna('unknown')
    
if len(df_ik_meta) > 0:
    wd_all = get_all_ik(wd_url)
    wd_all['short_inchikey'] = wd_all['inchikey'].str[:14]
    wd_filtred = wd_all[wd_all['short_inchikey'].isin(list(metadata_short_ik.keys()))]
    
    df_total = wd_filtred.merge(df_ik_meta, on='short_inchikey', how='outer')
    df_total['isomeric_smiles'] = df_total['isomeric_smiles'].fillna(df_total['smiles'])
    df_total = df_total.fillna('no_wikidata_match')
                
    update_sqldb(df_total, path + '/structures_metadata.db')

