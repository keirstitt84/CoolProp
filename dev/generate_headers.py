"""
In this module, we do some of the preparatory work that is needed to get
CoolProp ready to build.  This includes setting the correct versions in the 
headers, generating the fluid files, etc.
"""
from __future__ import division, print_function, unicode_literals
from datetime import datetime
import subprocess
import os
import sys
import json
import hashlib
import struct
import glob

json_options = {'indent' : 2, 'sort_keys' : True}

def get_hash(data):
    try:
        return hashlib.sha224(data).hexdigest()
    except TypeError:
        return hashlib.sha224(data.encode('ascii')).hexdigest()

# unicode
repo_root_path = os.path.normpath(os.path.join(os.path.abspath(__file__), '..', '..'))

# Load up the hashes of the data that will be written to each file
hashes_fname = os.path.join(repo_root_path,'dev','hashes.json')
if os.path.exists(hashes_fname):
    hashes = json.load(open(hashes_fname,'r'))
else:
    hashes = dict()

# 0: Input file path relative to dev folder
# 1: Output file path relative to include folder
# 2: Name of variable
values = [
    ('all_fluids.json','all_fluids_JSON.h','all_fluids_JSON'),
    ('all_incompressibles.json','all_incompressibles_JSON.h','all_incompressibles_JSON'),
    ('mixtures/mixture_excess_term.json', 'mixture_excess_term_JSON.h', 'mixture_excess_term_JSON'),
    ('mixtures/mixture_reducing_parameters.json', 'mixture_reducing_parameters_JSON.h', 'mixture_reducing_parameters_JSON')
]

def TO_CPP(root_dir, hashes):
    def to_chunks(l, n):
        if n<1:
            n=1
        return [l[i:i+n] for i in range(0, len(l), n)]
    
    # Normalise path name
    root_dir = os.path.normpath(root_dir)
    
    # First we package up the JSON files
    combine_json(root_dir)
    
    for infile,outfile,variable in values:
        
        json = open(os.path.join(root_dir,'dev',infile),'r').read().encode('ascii')

        # convert each character to hex and add a terminating NULL character to end the 
        # string, join into a comma separated string
        
        try:
            h = ["0x{:02x}".format(ord(b)) for b in json] + ['0x00']
        except TypeError:
            h = ["0x{:02x}".format(int(b)) for b in json] + ['0x00']
        
        # Break up the file into lines of 16 hex characters
        chunks = to_chunks(h, 16)
        
        # Put the lines back together again
        # The chunks are joined together with commas, and then EOL are used to join the rest
        hex_string = ',\n'.join([', '.join(chunk) for chunk in chunks])
            
        # Check if hash is up to date based on using variable as key
        if variable not in hashes or (variable in hashes and hashes[variable] != get_hash(hex_string.encode('ascii'))):
        
            # Generate the output string
            output  = '// File generated by the script dev/JSON_to_CPP.py on '+ str(datetime.now()) + '\n\n'
            output += '// JSON file encoded in binary form\n'
            output += 'const unsigned char '+variable+'_binary[] = {\n' + hex_string + '\n};'+'\n\n'
            output += '// Combined into a single std::string \n'
            output += 'std::string {v:s}({v:s}_binary, {v:s}_binary + sizeof({v:s}_binary)/sizeof({v:s}_binary[0]));'.format(v = variable)
            
            # Write it to file
            f = open(os.path.join(root_dir,'include',outfile), 'w')
            f.write(output)
            f.close()
            
            # Store the hash of the data that was written to file (not including the header)
            hashes[variable] = get_hash(hex_string.encode('ascii'))
            
            print(os.path.join(root_dir,'include',outfile)+ ' written to file')
        else:
            print(outfile + ' is up to date')
            
def version_to_file(root_dir):
    
    # Parse the CMakeLists.txt file to generate the version
    """
    Should have lines like
    "
    set (CoolProp_VERSION_MAJOR 5)
    set (CoolProp_VERSION_MINOR 0)
    set (CoolProp_VERSION_PATCH 0)
    "
    """
    
    lines = open(os.path.join(root_dir,'CMakeLists.txt'),'r').readlines()
    # Find the necessary lines
    MAJOR_line = [line for line in lines if ('VERSION_MAJOR' in line and 'MINOR' not in line)]
    MINOR_line = [line for line in lines if ('VERSION_MINOR' in line and 'MAJOR' not in line)]
    PATCH_line = [line for line in lines if ('VERSION_PATCH' in line and 'MINOR' not in line)]
    # String processing
    MAJOR = MAJOR_line[0].strip().split('VERSION_MAJOR')[1].split(')')[0].strip()
    MINOR = MINOR_line[0].strip().split('VERSION_MINOR')[1].split(')')[0].strip()
    PATCH = PATCH_line[0].strip().split('VERSION_PATCH')[1].split(')')[0].strip()
    # Generate the strings
    version = '.'.join([MAJOR,MINOR,PATCH])
     
    # Get the hash of the version
    if 'version' not in hashes or ('version' in hashes and hashes['version'] != get_hash(version.encode('ascii'))):
        hashes['version'] = get_hash(version)
        
        # Format the string to be written
        string_for_file = b'//Generated by the generate_headers.py script on {t:s}\n\nstatic char version [] ="{v:s}";'.format(t = str(datetime.now()),v = version)
        
        # Include path relative to the root
        include_dir = os.path.join(root_dir, b'include')
        
        # The name of the file to be written into
        file_name = os.path.join(include_dir, b'cpversion.h')
        
        # Write to file
        f = open(file_name,'w')
        f.write(string_for_file)
        f.close()
        
        print(b'version written to file: ' + file_name)
        
    else:
        print('cpversion.h is up to date')
        
    hidden_file_name = os.path.join(root_dir, '.version')
        
    # Write to file
    f = open(hidden_file_name,'w')
    f.write(version)
    f.close()
    
    print('version written to hidden file: ' + hidden_file_name + " for use in builders that don't use git repo")
    
def gitrev_to_file(root_dir):
    """
    If a git repo, use git to update the gitrevision.  If not a git repo, read 
    the gitrevision from the gitrevision.txt file.  Otherwise, fail.
    """
    
    try:
        try:
            subprocess.check_call('git --version', shell=True)
            print('git is accessible at the command line')
        except subprocess.CalledProcessError:
            print('git was not found')
            return
        p = subprocess.Popen('git rev-parse HEAD', 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE,
                             shell = True)
        stdout, stderr = p.communicate()

        # Include path relative to the root
        include_dir = os.path.join(root_dir,'include')
        
        if p.returncode != 0:
            print('tried to get git revision from git, but could not (building from zip file?)')
            gitrevision_path = os.path.join(root_dir, 'dev', 'gitrevision.txt')
            if os.path.exists(gitrevision_path):
                gitrev = open(gitrevision_path, 'r').read().strip()
            else:
                print('tried to get git revision from '+gitrevision_path+', but could not')
                gitrev = b'???'
        else:
            gitrev = stdout.strip() # bytes
            
            try:
                is_hash = gitrev.find(' ') == -1 # python 2.x
            except TypeError:
                is_hash = ' ' not in str(gitrev) # python 3.x
                                
            if not is_hash:
                raise ValueError('No hash returned from call to git, got '+rev+' instead')
        
        print('git revision is', str(gitrev))
        
        if 'gitrevision' not in hashes or ('gitrevision' in hashes and hashes['gitrevision'] != get_hash(gitrev)):
            print('*** Generating gitrevision.h ***')
            gitstring = '//Generated by the generate_headers.py script on {t:s}\n\nstd::string gitrevision = \"{rev:s}\";'.format(t = str(datetime.now()), rev = gitrev)
        
            f = open(os.path.join(include_dir,'gitrevision.h'),'w')
            f.write(gitstring)
            f.close()
            
            hashes['gitrevision'] = get_hash(gitrev)
            print(os.path.join(include_dir,'gitrevision.h') + ' written to file')
        else:
            print('gitrevision.h is up to date')
                
    except (subprocess.CalledProcessError,OSError):
        pass
        
def combine_json(root_dir):
    
    master = []
    
    for file in glob.glob(os.path.join(root_dir,'dev','fluids','*.json')):
        
        path, file_name = os.path.split(file)
        fluid_name = file_name.split('.')[0]
        
        try:
            # Load the fluid file
            fluid = json.load(open(file, 'r'))
        except ValueError:
            raise ValueError('unable to decode file %s' % file)
        
        master += [fluid]

    fp = open(os.path.join(root_dir,'dev','all_fluids_verbose.json'),'w')
    fp.write(json.dumps(master, **json_options))
    fp.close()
    
    fp = open(os.path.join(root_dir,'dev','all_fluids.json'),'w')
    fp.write(json.dumps(master))
    fp.close()
    
    master = []
    
    for file in glob.glob(os.path.join(root_dir,'dev','incompressible_liquids','json','*.json')):
        
        path, file_name = os.path.split(file)
        fluid_name = file_name.split('.')[0]
        
        try:
            # Load the fluid file
            fluid = json.load(open(file, 'r'))
        except ValueError:
            raise ValueError('unable to decode file %s' % file)
        
        master += [fluid]

    fp = open(os.path.join(root_dir,'dev','all_incompressibles_verbose.json'),'w')
    fp.write(json.dumps(master, **json_options))
    fp.close()
    
    fp = open(os.path.join(root_dir,'dev','all_incompressibles.json'),'w')
    fp.write(json.dumps(master))
    fp.close()        
    
def generate():
    
    import shutil
    shutil.copy2(os.path.join(repo_root_path, 'externals','Catch','single_include','catch.hpp'),os.path.join(repo_root_path,'include','catch.hpp'))

    version_to_file(root_dir = repo_root_path)
    gitrev_to_file(root_dir = repo_root_path)
    
    TO_CPP(root_dir = repo_root_path, hashes = hashes)

    # Write the hashes to a hashes JSON file
    if hashes:
        fp = open(hashes_fname,'w')
        fp.write(json.dumps(hashes))
        fp.close()
        
if __name__=='__main__':
	generate()

