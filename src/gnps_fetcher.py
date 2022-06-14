import zipfile
import os
import shlex
import subprocess
import argparse
import textwrap

# Loading the parameters from yaml file
from pathlib import Path

p = Path(__file__).parents[2]
os.chdir(p)

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
         This script will download a GNPS job
         --------------------------------
            results will be stored in data/in/<job_id>/
        '''))
parser.add_argument('--job_id', required=True,
                    help='the identifier of the GNPS job to download')
args = parser.parse_args()

pathout = os.path.normpath("./data/in/")
os.makedirs(pathout, exist_ok=True)
path_to_folder = os.path.expanduser(os.path.join('./data/in/' + args.job_id))
path_to_file = os.path.expanduser(os.path.join('./data/in/' + args.job_id +'.zip'))

# Downloading GNPS files

print('''
Fetching the GNPS job: '''
+ args.job_id
)

job_url_zip = "https://gnps.ucsd.edu/ProteoSAFe/DownloadResult?task="+args.job_id+"&view=download_cytoscape_data"
print(job_url_zip)

cmd = 'curl -d "" '+job_url_zip+' -o '+path_to_file+ ' --create-dirs'
subprocess.call(shlex.split(cmd))

with zipfile.ZipFile(path_to_file, 'r') as zip_ref:
    zip_ref.extractall(path_to_folder)

# We finally remove the zip file
os.remove(path_to_file)

print('''
Job successfully downloaded: results are in: '''
+ path_to_folder
)
