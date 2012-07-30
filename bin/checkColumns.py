#!/usr/local/bin/python
#
#  checkColumns.py
###########################################################################
#
#  Purpose:
#
#       This script checks that there are the correct number of columns
#	in a file
#
#  Usage:
#
#      checkColumns.py  filename numColumns	
#
#      where:
#          filename = path to the input file
#
#  Env Vars:
#
#      The following environment variables are set by the configuration
#      files that are sourced by the wrapper script:
#
#  Inputs:
#
#  Outputs:
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  An exception occurred
#      2:  Discrepancy errors detected in the input files
#  Implementation:
#
#  Notes:  None
#
###########################################################################


import string
import sys

USAGE = 'Usage: checkColumns.py  inputFile numColumns'
TAB = '\t'

inputFile = None
fpInput = None
numColumns = None
errors = 0

#
# Purpose: Validate the arguments to the script.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def checkArgs ():
    global inputFile, numColumns

    if len(sys.argv) != 3:
        print USAGE
        sys.exit(1)

    inputFile = sys.argv[1]
    numColumns = int(sys.argv[2])
    return

#
# Purpose: Open the file for reading
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def openFile ():
    global fpInput

    try:
	fpInput = open(inputFile, 'r')
    except:
	print 'Cannot open input file: ' + inputFile
	sys.exit(1)
    return

#
# Purpose: check the file for proper number of columns
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def checkColumns ():
    #print 'starting checkColumns'
    global errors
    lineNum = 1
    header = fpInput.readline()
    for line in fpInput.readlines():
	colError = 0
	lineNum = lineNum + 1
   	columns = string.split(line, TAB)
	nc = len(columns) 
	#print 'expected columns: %s actualColumns: %s columns: %s' % (numColumns, nc, columns)
	if nc < numColumns:
	    errors = errors + 1
	    colError = colError + 1
	### start code for missing data in req columns
	# If errors then wrong number of columns exists; so continue to next
	if colError > 0:
	    print 'Missing Column(s): %s' % (columns)
	    continue
	# default
	bad = 1
	# transpose empty last column
	if columns[6] == '\n':
	    columns[6] = ''
        # strand is optional
        if columns[0] != '' and columns[1] != '' and columns[2] != '' and columns[3] != '' and columns[5] != '' and columns[6] != '':
            bad = 0
        # delete has only MGI ID, provider and display
        elif columns[0] != '' and columns[1] == '' and columns[2] == '' and columns[3] == '' and columns[4] == '' and columns[5] != '' and columns[6] != '' :
            bad = 0
        if bad == 1:
            print 'Missing Data in required column: %s' % (columns)
	### end code for missing data in req columns
    #print 'end checkColumns and errors is: %s' % errors
    return

#
# Purpose: Close the files.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def closeFile():
    global fpInput

    fpInput.close()
    return

checkArgs()
openFile()
checkColumns()
closeFile()
if errors > 0:
    sys.exit(1)
sys.exit(0)