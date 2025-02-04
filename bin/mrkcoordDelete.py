#
# Program: mrkcoordDelete.py
#
# Inputs:
#
#	A tab-delimited file in the format:
#       field 1:  MGI:xxxx
#       field 2:  MGI Coordinate Id
#
# Outputs:
#
#       Diagnostics file of all input parameters and SQL commands
#       Error file
#
# History
#

import sys
import os
import db
import mgi_utils
import loadlib

#db.setTrace()

inputFileName = ''
mode = ''
isSanityCheck = 0
lineNum = 0
hasFatalError = 0
hasWarningError = 0

diagFileName = os.environ['LOG_DIAG']
errorFileName = os.environ['LOG_ERROR']
inputFile = os.environ['INPUTDIR']

diagFile = ''
errorFile = ''

deleteSQL = ''

# Purpose: prints error message and exits
# Returns: nothing
# Assumes: nothing
# Effects: exits with exit status
# Throws: nothing
def exit(
    status,          # numeric exit status (integer)
    message = None   # exit message (string)
    ):

    if message is not None:
        sys.stderr.write('\n' + str(message) + '\n')
 
    try:
        diagFile.write('\n\nEnd Date/Time: %s\n' % (mgi_utils.date()))

        if hasFatalError == 0:
                errorFile.write("\nSanity check : successful\n")
        else:
                errorFile.write("\nSanity check : failed")
                errorFile.write("\nErrors must be fixed before file is published.\n")

        errorFile.write('\n\nEnd Date/Time: %s\n' % (mgi_utils.date()))
        diagFile.close()
        errorFile.close()
        inputFile.close()
    except:
        pass

    db.useOneConnection(0)
    sys.exit(status)
 
# Purpose: process command line options
# Returns: nothing
# Assumes: nothing
# Effects: initializes global variables
#          exits if files cannot be opened
# Throws: nothing
def init():
    global inputFileName, mode, isSanityCheck
    global diagFileName, errorFileName, diagFile, errorFile, inputFile
 
    try:
        inputFileName = sys.argv[1]
        mode = sys.argv[2]
    except:
        exit(1, 'Could not open inputFileName=sys.argv[1] or mode=sys.argv[2]\n')

    if mode == "preview":
        isSanityCheck = 1

    # place diag/error file in current directory
    if isSanityCheck == 1:
        diagFileName = inputFileName + '.diagnostics'
        errorFileName = inputFileName + '.error'

    try:
        if isSanityCheck == 1:
            diagFile = open(diagFileName, 'w')
        else:
            diagFile = open(diagFileName, 'a')
    except:
        exit(1, 'Could not open file diagFile: %s\n' % diagFile)
                
    try:
        errorFile = open(errorFileName, 'w')
    except:
        exit(1, 'Could not open file errorFile: %s\n' % errorFile)
                
    try:
        inputFile = open(inputFileName, 'r', encoding="latin-1")
    except:
        exit(1, 'Could not open file inputFileName: %s\n' % inputFileName)
    
    # Log all SQL
    db.set_sqlLogFunction(db.sqlLogAll)

    diagFile.write('Start Date/Time: %s\n' % (mgi_utils.date()))
    diagFile.write('Server: %s\n' % (db.get_sqlServer()))
    diagFile.write('Database: %s\n' % (db.get_sqlDatabase()))

    errorFile.write('Start Date/Time: %s\n\n' % (mgi_utils.date()))

    return

# Purpose:  processes data
# Returns:  nothing
# Assumes:  nothing
# Effects:  verifies and processes each line in the input file
# Throws:   nothing
def processFile():

    global lineNum
    global deleteSQL
    global hasFatalError, hasWarningError

    # For each line in the input file

    for line in inputFile.readlines():

        lineNum = lineNum + 1

        if not line.startswith('MGI:'):
            continue

        # Split the line into tokens
        tokens = line.rstrip('\n').split('\t')

        try:
            mgiId = tokens[0]
            mapId = tokens[1]
            #print(tokens)
        except:
            exit(1, 'Invalid Line (%d): %s\n' % (lineNum, line))

        results = db.sql('''
            select mc._feature_key from acc_accession ma, acc_accession ca, map_coord_feature mc
            where ma.accid = '%s' 
            and ma._logicaldb_key = 1
            and ma._mgitype_key = 2
            and ma.preferred = 1
            and ca.accid = '%s'
            and ca._logicaldb_key not in (1,8,9,117,118)
            and ca._mgitype_key = 2
            and ma._object_key = mc._object_key
            and mc._mgitype_key = 2
            ''' % (mgiId, mapId), 'auto')

        if len(results) == 0:
            errorFile.write('Invalid Mapping Coordinate (row %d) %s %s\n' % (lineNum, mgiId, mapId))
            hasFatalError += 1

        # if no errors, process

        if isSanityCheck == 1:
            continue

        if hasFatalError > 0:
            continue

        key = results[0]['_feature_key']
        deleteSQL = deleteSQL + ''' delete from MAP_Coord_Feature where _feature_key = %s;\n ''' % (key)

    #	end of "for line in inputFile.readlines():"

    print(deleteSQL)
    #db.sql(deleteSQL, None)
    #db.commit()

    return

#
# Main
#

init()
processFile()
exit(0)

