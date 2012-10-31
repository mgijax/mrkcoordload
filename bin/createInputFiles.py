#!/usr/local/bin/python

'''
  Program: createInputFiles.py 

  Purpose: Read input file and parse into multiple
           coordload files by collection

  Usage:
	createInputFiles.py

  Env Vars:

  Inputs: tab delimited file with the 8 columns:
	1. MGI ID 
	2. Chr
	3. start coordinate
	4. end coordinate
	5. strand
	6. collection name
	7. collection abbreviation
	8. comma separated list of miRBase IDs
  Outputs: 
	Tab delimited files in coordload format, one for each collection
        1. MGI ID 
        2. Chr
        3. start coordinate
        4. end coordinate
        5. strand

	Optional tab delimited mirbase assocload file
	header:
	1. MGI
	2. miRBase
	data rows:
	1. MGI ID 
	2. comma separated list of miRBase IDs

  Assumes:
	QC process detects:
	1. invalid collections
	2. invalid MGI IDs

  Exit Codes:
    0:  Successful completion
    1:  An exception occurred

  Implementation:

  Notes:

  History:

  05/24/2012  sc   Initial development

'''

import sys
import os
import db
import string

# MGI python libraries
import mgi_utils

TAB = '\t'
CRT = '\n'

# load ready file - line rejects removed by QC process
inputFile = os.environ['INPUT_FILE_LOAD']

# US 35 - create assocload file for mirbase id/marker associations
mirbaseAssocFile = os.environ['MIRBASE_ASSOC_FILE']

# root filepath for coordload files by collection
coordFileRoot = os.environ['INFILE_NAME']

# name of file containing all coordload input files
coordFileListFile = os.environ['COORD_FILES']

# mapping of collections to their rows of coordinates

# {collectionName~collectionAbbrev: [list of coordload format rows], ...}
inputDict = {}

# the set of collections found in 'inputFile'
collectionList = []

# (MGI ID:_Marker_key
# US 35 - initialize lookup of markers with mirbase IDs
def init():
    global fpMirbaseAssoc

    fpMirbaseAssoc = open(mirbaseAssocFile, 'w')

    # write the header:
    fpMirbaseAssoc.write('MGI%smiRBase%s' % (TAB, CRT))
    user = os.environ['MGD_DBUSER']
    passwordFileName = os.environ['MGD_DBPASSWORDFILE']
    db.useOneConnection(1)
    db.set_sqlUser(user)
    db.set_sqlPasswordFromFile(passwordFileName)
    db.useOneConnection(0)
# US 35 - create assocload file for mirbase id/marker associations
#	  delete all marker associations to mbID
# US 175 - delete all mirbase IDs from  marker 'mgiID'
#	   write a line to the assocload file if 'mbiIDs' not empty
def processMirbase(mgiID, mbIDs):
    #
    # Delete association mirbase associations to mgiID - some won't exist
    # If mbIDs = '', could be a miRNA marker that we want to delete miRBase
    #    ids from
    #
    db.useOneConnection(1)
    db.sql('''select a1._Accession_key as aKey, a1._Object_key as _Marker_key, a1.accid as mbID
	into #mirbase
	from ACC_Accession a1
	where a1._MGIType_key = 2
	and a1._LogicalDB_key = 83''', None)
    db.sql('create index idx1 on #mirbase(_Marker_key)', None)
    results = db.sql('''select m.aKey, m.mbID
	from #mirbase m, ACC_Accession a
	where m._Marker_key = a._Object_key
	and a._MGIType_key = 2
	and a._LogicalDB_key = 1
	and a.accid = '%s' ''' % mgiID, 'auto')
    db.useOneConnection(0)
    for r in results:
	deleteAccession(r['aKey'])

    # write out to assocload input file
    if mbIDs != '':
	fpMirbaseAssoc.write('%s%s%s%s' % (mgiID, TAB, mbIDs, CRT))

    return

def deleteAccession(aKey):
	# delete from ACC_AccessionReference first
	db.sql('''delete from ACC_AccessionReference
	    where _Accession_key = %s''' % aKey, None)
	db.sql('''delete from ACC_Accession
	    where _Accession_key = %s''' % aKey, None)
	return

# US 35 - input file now has 8 columns, the 8th being MiRBase ID, optional
# US 175: column 8 now comma delimited list of miRBase IDs, optional
def readInput():
    global inputDict, collectionList

    # open the input file
    try:
	fpInput = open(inputFile, 'r')
    except:
	print 'Cannot open input file: %s ' % inputFile
	sys.exit(1)

    # discard the header line
    junk = fpInput.readline()
    for r in fpInput.readlines():
	# create list of columns
	columnList = r.split(TAB)
	if len(columnList) < 8:
	    sys.exit ('error in input line: %s' % r)

        # US 175 - mgID column no multivalued. New requirement: delete 
	# all 
        mgiID = columnList[0].strip()
	mbIDs = columnList[7].strip()
	processMirbase(mgiID, mbIDs)

	# add the coordinates to dictionary by collectin and abbrev
        # for later processing
	collection = columnList[5].strip()
	abbrev = columnList[6].strip()

	key = '%s~%s' % (collection, abbrev)

	# remove the collection and abbrev columns from the list
	columnList = columnList[:-2]

	if not inputDict.has_key(key):
	    inputDict[key] = []
	inputDict[key].append(columnList)

    # get the set of collections found in the input file
    collectionList = inputDict.keys()
def writeFiles():
    try:
	fp1 = open(coordFileListFile, 'w')
    except:
	print 'Cannot open output file: %s ' % coordFileListFile
	sys.exit(1)
    for c in collectionList:
	# e.g. c: MGI QTL~MGI
	suffix = c.replace(' ', '_')
	fileName = '%s.%s' % (coordFileRoot, suffix)
	try:
	    fp2 = open(fileName, 'w')
	except:
	    print 'Cannot open output file: %s ' % fileName
	    sys.exit(1)
	# save the filename to a file for access by the wrapper
	# which will iterate through them passing to coordload
	fp1.write(fileName + CRT)
	coordList = inputDict[c]
	for l in coordList:
	    fp2.write('\t'.join(l) + CRT)
	fp2.close()
    fp1.close()

def postprocess():
    global fpMirbaseAssoc

    fpMirbaseAssoc.close()
#
# Main
# 

init()
readInput()
writeFiles()
postprocess()
sys.exit(0)
