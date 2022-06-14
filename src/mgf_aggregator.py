import pandas as pd
import os
from matchms.importing import load_from_mgf
from matchms.exporting import save_as_mgf
from tqdm import tqdm
import argparse
import textwrap
from pathlib import Path

p = Path(__file__).parents[2]
os.chdir(p)

""" Argument parser """
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
        This script generate an aggregated .mgf spectra file from unaligned individual .mgf files for further GNPS classical MN processing.
         --------------------------------
            Arguments:
            - Path to the directory where samples folders are located
            - Output name for the output
        '''))
parser.add_argument('--sample_dir_path', required=True,
                    help='The path to the directory where samples folders to process are located')
parser.add_argument('--output_name', required=True,
                    help='The the output name for the .mgf and the .csv file to generate')

args = parser.parse_args()
sample_dir_path = args.sample_dir_path
output_name = args.output_name

""" Process """ 

path = os.path.normpath(sample_dir_path)
samples_dir = [directory for directory in os.listdir(path)]
spectrums = []
i = 1
j = 1

n_iter = len(samples_dir)
for sample_directory in tqdm(samples_dir):
    mgf_file_path = os.path.join(path, sample_directory, sample_directory + '_features_ms2_pos.mgf')
    metadata_file_path = os.path.join(path, sample_directory, sample_directory + '_metadata.tsv')

    try:
        sample_spec = list(load_from_mgf(mgf_file_path))
        metadata = pd.read_csv(metadata_file_path, sep='\t')
    except FileNotFoundError:
        continue
    if metadata['sample_type'][0] == 'sample':
        for spectrum in sample_spec:
            original_feat_id = sample_directory + '_feature_' + spectrum.metadata['scans'] 
            spectrum.set('original_feature_id', original_feat_id)
            spectrum.set('feature_id', i)
            spectrum.set('scans', i)
            i += 1
        spectrums = spectrums + sample_spec

metadata_df = pd.DataFrame(s.metadata for s in spectrums)
metadata_df.to_csv(path + '/' + output_name + '_metadata.csv', index=False)

spec_path = os.path.normpath(path + '/' + output_name +'.mgf')
if os.path.isfile(spec_path):
    os.remove(spec_path)   
    save_as_mgf(spectrums, spec_path)
else:
    save_as_mgf(spectrums, spec_path)