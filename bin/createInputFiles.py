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

  Outputs: tab delimited files in coordload format, one for each collection
        1. MGI ID 
        2. Chr
        3. start coordinate
        4. end coordinate
        5. strand
	
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

# mirbase ID lookup {mgiID:markerKey, ...}
mirbaseDict = {}

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
    global fpMirbaseAssoc, mirbaseDict

    fpMirbaseAssoc = open(mirbaseAssocFile, 'w')

    # write the header:
    fpMirbaseAssoc.write('MGI%smiRBase%s' % (TAB, CRT))

    db.useOneConnection(1)

    # contain non-preferred IDs
    results = db.sql('''select a.accID, a._Object_key
	from ACC_Accession a
	where a._MGIType_key = 2
	and a._LogicalDB_key = 83
	and preferred = 1''', 'auto')
    for r in results:
	mgiID = r['accID']
	markerKey = r['_Object_key']

	# one mirbase ID per mgi ID
        mirbaseDict[mgiID] = markerKey

    db.useOneConnection(0)

# US 35 - create assocload file for mirbase id/marker associations
def processMirbase(mgiID, mbID):

    # if the marker has mirbase ID in the database, but there is no
    # mbID in the input, just delete it
    print 'processMirbase: %s %s' % (mgiID, mbID)
    if mbID == '':
	print 'no mbID'
	if mirbaseDict.has_key(mgiID):
	    print 'mirbaseDict has mgiID'
	    markerKey = mirbaseDict[mgiID]
	    results = db.sql('''select _Accession_key as aKey
		    from ACC_Accession
		    where _MGIType_key = 2
		    and _LogicalDB_key = 83''', 'auto')
	    # For each mirbase ID assoc with the marker delete it
	    # We are really only expecting one
	    print 'query results: %s' % results
	    for r in results:
		aKey = r['aKey']
		print 'deleting accKey %s from marker %s' % (aKey, mgiID)
		# delete from ACC_AccessionReference first
		db.sql('''delete from ACC_AccessionReference
		    where _Accession_key = %s''' % aKey, None)
		db.sql('''delete from ACC_Accession
		    where _Accession_key = %s''' % aKey, None)
	else:
	    print 'mirbaseDict does not have mgiID'
    else:
	print 'is mbID writing to assocload file'
	# write out to assocload input file
	fpMirbaseAssoc.write('%s%s%s%s' % (mgiID, TAB, mbID, CRT))
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
	print 'r: %s' % r
	# create list of columns
	columnList = r.split(TAB)
	if len(columnList) < 7:
	    sys.exit ('error in input line: %s' % r)

        # US 35 - get mgiID column
        mgiID = columnList[0].strip()
	mbID = columnList[7].strip()
	print 'calling processMirbase and sending %s and %s' % (mgiID, mbID)
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
