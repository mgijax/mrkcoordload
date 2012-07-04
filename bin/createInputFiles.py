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
inputFile = os.environ['INPUT_FILE']
print 'inputFile: %s' % inputFile

# root filepath for coordload files by collection
coordFileRoot = os.environ['INFILE_NAME']

# name of file containing all coordload input files
coordFileListFile = os.environ['COORD_FILES']

# mapping of collections to their rows of coordinates

# {collection  name: [list of coordload format rows], ...}
inputDict = {}

# the set of collections found in 'inputFile'
collectionList = []

def readInput():
    global inputDict, collectionList

    # open the input file
    try:
	fpInput = open(inputFile, 'r')
    except:
	print 'Cannot open input file: %s ' % inputFile
	sys.exit(1)
    junk = fpInput.readline()
    print 'junk: %s' % junk
    for r in fpInput.readlines():
	print 'r: %s' % r
	# create list of columns
	columnList = r.split(TAB)
	if len(columnList) < 5:
	    sys.exit ('error in input line: %s' % r)
	# get the collection name
	collection = columnList[5].strip()
	print 'collection: %s' % collection
	# remove the collection column from the list
	columnList = columnList[:-1]

	if not inputDict.has_key(collection):
	    inputDict[collection] = []
	inputDict[collection].append(columnList)

    # get the set of collections found in the input file
    collectionList = inputDict.keys()
def writeFiles():
    try:
	fp1 = open(coordFileListFile, 'w')
    except:
	print 'Cannot open output file: %s ' % coordFileListFile
	sys.exit(1)
    for c in collectionList:
	# e.g. mrkcoordload.MGI QTL
	suffix = c.replace(' ', '_')
	fileName = '%s.%s' % (coordFileRoot, suffix)
	print 'fileName: %s' % fileName
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
#
# Main
# 

#init()
readInput()
writeFiles()
sys.exit(0)
