#!/usr/local/bin/python

'''
  Program: createInputFiles.py 

  Purpose: Read input file and parse into multiple
           coordload files by collection

  Usage:
	createInputFiles.py

  Env Vars:

  Inputs: tab delimited file with the following columns:
	1. MGI ID 
	2. Chr
	3. start coordinate
	4. end coordinate
	5. strand
	6. collection name
	7. collection abbreviation

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
	2. miRBase ID

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

# curated marker coordinate file
## Change INPUT_FILE_DEFAULT to INPUT_FILE_LOAD
## when we start running QC checks from the load
inputFile = os.environ['INPUT_FILE_DEFAULT']

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
def processMirbase(mgiID, mbID):
    #
    # Delete association to all markers associated with 'mbId'
    #
    results = db.sql('''select a1._Accession_key as aKey, a2.accid as mgiID
	    from ACC_Accession a1, ACC_Accession a2
	    where a1._MGIType_key = 2
	    and a1._LogicalDB_key = 83
	    and a1.accid = '%s' 
	    and a1._Object_key = a2._Object_key
	    and a2._MGIType_key = 2
	    and a2._LogicalDB_key = 1
	    and a2.preferred = 1
	    and a2.prefixPart = 'MGI:' ''' % mbID, 'auto')
    for r in results:
	#print 'deleting mirbaseID %s association with %s' % (mbID, r['mgiID'])
	deleteAccession(r['aKey'])

    # write out to assocload input file
    fpMirbaseAssoc.write('%s%s%s%s' % (mgiID, TAB, mbID, CRT))

    return

def deleteAccession(aKey):
	# delete from ACC_AccessionReference first
	#print 'deleting aKey: %s' % aKey
	db.sql('''delete from ACC_AccessionReference
	    where _Accession_key = %s''' % aKey, None)
	db.sql('''delete from ACC_Accession
	    where _Accession_key = %s''' % aKey, None)
	return

# US 35 - input file now has 8 columns, the 8th being MiRBase ID, optional
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
	#print 'r: %s' % r
	# create list of columns
	columnList = r.split(TAB)
	if len(columnList) < 7:
	    sys.exit ('error in input line: %s' % r)

        # US 35 - get mgiID column
        mgiID = columnList[0].strip()
	mbID = columnList[7].strip()
	if mbID != '':
	    #print 'calling processMirbase and sending %s and %s' % (mgiID, mbID)
	    processMirbase(mgiID, mbID)

	# add the coordinates to dictionary by collectin and abbrev
        # for later processing
	collection = columnList[5].strip()
	abbrev = columnList[6].strip()

	key = '%s~%s' % (collection, abbrev)
	#print 'col/abbrev key: %s' % key

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
	#print 'fileName: %s' % fileName
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
