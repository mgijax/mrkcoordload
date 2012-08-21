#!/usr/local/bin/python
#
#  mrkcoordQC.py
###########################################################################
#
#  Purpose:
#
#      This script will generate a set of QC reports for 
#      marker coordinate load file
#
#  Usage:
#
#      mrkcoordQC.py <path to input file>
#
#  Env Vars:
#
#      The following environment variables are set by the configuration
#      files that are sourced by the wrapper script:
#
#          MGI_PUBLICUSER
#          MGI_PUBPASSWORDFILE
#          TEMP_TABLE
#          INVALID_MARKER_RPT
#          SEC_MARKER_RPT
#          CHR_DISCREP_RPT
#	   INVALID_CHR_RPT
#	   INVALID_COORD_STRAND_RPT
#	   RPT_NAMES_RPT
#
#      The following environment variable is set by the wrapper script:
#
#          LIVE_RUN
#
#  Inputs:
#
#      - Coordinate input file with the following tab-delimited fields:
#
#          1) MGI ID
#          2) Chromosome
#          3) Start Coordinate
#          4) End Coordinate
#          5) Strand (+ or -)
#          6) Provider
#	   7) Display
#
#  Outputs:
#
#      - BCP file (${FILE_BCP}) for loading the coordinate file
#        into a temp table
#
#      - QC report (${INVALID_MARKER_RPT})
#
#      - QC report (${SEC_MARKER_RPT})
#
#      - QC report (${CHR_DISCREP_RPT})
#
#      - QC report (${INVALID_CHR_RPT})
#
#      - QC report (${INVALID_COORD_STRAND_RPT})
#
#      - QC report (${RPT_NAMES_RPT})
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  An exception occurred
#      2:  Discrepancy errors detected in the input files
#
#  Assumes:
#
#      This script assumes that the wrapper script has already created the
#      tables in tempdb for loading the input records into. The table
#      name is defined by the environment variable ${TEMP_TABLE}.
#      The wrapper script will also take care of
#      dropping the table after this script terminates.
#
#  Implementation:
#
#      This script will perform following steps:
#
#      1) Validate the arguments to the script.
#      2) Perform initialization steps.
#      3) Open the input/output files.
#      4) Load the records from the input file into the temp table.
#      5) Generate the QC reports.
#      6) Close the input/output files.
#      7) If this is a "live" run, create the load-ready coordinate  file
#         from the coordinates that do not have any discrepancies.
#
#  Notes:  None
#
###########################################################################
#
#  Modification History:
#
#  Date        SE   Change Description
#  ----------  ---  -------------------------------------------------------
#
#  07/24/2012  sc   Initial development
#
###########################################################################

import sys
import os
import string
import re
import mgi_utils
import db

#
#  CONSTANTS
#
TAB = '\t'
NL = '\n'

USAGE = 'mrkcoordQC.py coordinate_file'


#
#  GLOBALS
#
user = os.environ['MGI_PUBLICUSER']
passwordFile = os.environ['MGI_PUBPASSWORDFILE']

liveRun = os.environ['LIVE_RUN']

coordBCPFile = os.environ['INPUT_FILE_BCP']
coordTempTable = os.environ['TEMP_TABLE']

invMrkRptFile = os.environ['INVALID_MARKER_RPT']
secMrkRptFile = os.environ['SEC_MARKER_RPT']
chrDiscrepRptFile = os.environ['CHR_DISCREP_RPT']
invChrRptFile =  os.environ['INVALID_CHR_RPT']
invCoordStrandRptFile =  os.environ['INVALID_COORD_STRAND_RPT']
sourceDisplayRptFile = os.environ['SOURCE_DISPLAY_RPT']
buildRptFile = os.environ['BUILD_RPT']

# names of reports that contain discrepancies
rptNamesFile = os.environ['RPT_NAMES_RPT']

# list of distinct source/display fields found in the input
sourceDisplayList = []

# genome build value from the input
build = ''

# invalid chromosome list - don't do chromosome discrepancy
# reporting on this list
invChrList = ["' '"]

timestamp = mgi_utils.date()

errorCount = 0
coordErrorCount = 0
errorReportNames = []


#
# Purpose: Validate the arguments to the script.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def checkArgs ():
    global coordFile

    if len(sys.argv) != 2:
        print USAGE
        sys.exit(1)

    coordFile = sys.argv[1]
    print 'coordFile %s' % coordFile
    return


#
# Purpose: Perform initialization steps.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def init ():
    print 'DB Server:' + db.get_sqlServer()
    print 'DB Name:  ' + db.get_sqlDatabase()
    sys.stdout.flush()

    db.set_sqlUser(user)
    db.set_sqlPasswordFromFile(passwordFile)

    return


#
# Purpose: Open the files.
# Returns: Nothing
# Assumes: Nothing
# Effects: Sets global variables.
# Throws: Nothing
#
def openFiles ():
    global fpCoord, fpCoordBCP
    global fpInvMrkRpt, fpSecMrkRpt, fpChrDiscrepRpt, fpInvChrRpt
    global fpInvCoordStrandRpt
    global fpSourceDisplayRpt, fpBuildRpt, fpRptNamesRpt

    #
    # Open the input files.
    #
    try:
        fpCoord = open(coordFile, 'r')
    except:
        print 'Cannot open input file: ' + coordFile
        sys.exit(1)

    #
    # Open the output files.
    #
    try:
        fpCoordBCP = open(coordBCPFile, 'w')
    except:
        print 'Cannot open output file: ' + coordBCPFile
        sys.exit(1)

    #
    # Open the report files.
    #
    try:
        fpInvMrkRpt = open(invMrkRptFile, 'a')
    except:
        print 'Cannot open report file: ' + invMrkRptFile
        sys.exit(1)
    try:
        fpSecMrkRpt = open(secMrkRptFile, 'a')
    except:
        print 'Cannot open report file: ' + secMrkRptFile
        sys.exit(1)
    try:
        fpChrDiscrepRpt = open(chrDiscrepRptFile, 'a')
    except:
        print 'Cannot open report file: ' + chrDiscrepRptFile
        sys.exit(1)
    try:
	fpInvChrRpt = open(invChrRptFile, 'a')
    except:
        print 'Cannot open report file: ' + invChrRptFile
        sys.exit(1)
    try:
        fpInvCoordStrandRpt = open(invCoordStrandRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + invCoordStrandRptFile
        sys.exit(1)
    try:
        fpSourceDisplayRpt = open(sourceDisplayRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + sourceDisplayRptFile
        sys.exit(1)
    try:
        fpBuildRpt = open(buildRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + buildRptFile
        sys.exit(1)
    try:
        fpRptNamesRpt = open(rptNamesFile, 'a')
    except:
        print 'Cannot open report file: ' + invMrkRptFile
        sys.exit(1)
    return


#
# Purpose: Close the files.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def closeFiles ():
    global fpCoord, fpInvMrkRpt, fpSecMrkRpt, fpChrDiscrepRpt, fpInvChrRpt
    global fpInvCoordStrandRpt, fpSourceDisplayRpt, fpBuildRpt

    fpCoord.close()
    fpInvMrkRpt.close()
    fpSecMrkRpt.close()
    fpChrDiscrepRpt.close()
    fpInvChrRpt.close()
    fpInvCoordStrandRpt.close()
    fpSourceDisplayRpt.close()
    fpBuildRpt.close()
    return


#
# Purpose: Load the data from the input files into the temp tables.
#	This function also reports invalid start/end/strand as
#	we can't load characters into the integer columns
# Returns: Nothing
# Assumes: All columns exist
# Effects: Nothing
# Throws: Nothing
#
def loadTempTables ():
    global build

    print 'Create a bcp file from the coordinate input file'
    sys.stdout.flush()

    #
    # Read each record from the coordinate input file, perform validation
    # checks and write them to a bcp file.
    #
    header = fpCoord.readline()
    tokens = header.split(';')
    for t in tokens:
	a = t.split('=')
	if a[0].strip().lower() == 'build':
	    build = a[1].strip()
    print 'build: %s' % build
    count = 1
    writeInvcoordStrandHeader()
    for line in fpCoord.readlines():
	print 'line: %s' % line
        tokens = re.split(TAB, line[:-1])
        mgiID = tokens[0].strip()
        chromosome = tokens[1].strip()
        startCoordinate = tokens[2].strip()
        endCoordinate = tokens[3].strip()
        strand = tokens[4].strip()
        source = tokens[5].strip()
	display = tokens[6].strip()
	sourceDisplay = '%s/%s' % (source, display)
	print 'sourceDisplay: %s' % sourceDisplay
	if not sourceDisplay in sourceDisplayList:
	    sourceDisplayList.append(sourceDisplay)
        errors = createInvCoordStrandReport(mgiID, startCoordinate, endCoordinate, strand, source)
	if errors != 0:
	    continue

        fpCoordBCP.write(mgiID + TAB + chromosome + TAB +
                      startCoordinate + TAB + endCoordinate + TAB +
                      strand + TAB + source + TAB + display + TAB + build + TAB + NL)
        count += 1
    writeInvcoordStrandFooter()
    #
    # Close the bcp file.
    #
    fpCoordBCP.close()

    #
    # Load the temp tables with the input data.
    #
    print 'Load the coordinate data into the temp table: ' + coordTempTable
    sys.stdout.flush()

    bcpCmd = 'cat %s | bcp tempdb..%s in %s -c -t"%s" -S%s -U%s' % (passwordFile, coordTempTable, coordBCPFile, TAB, db.get_sqlServer(), db.get_sqlUser())
    rc = os.system(bcpCmd)
    if rc <> 0:
        closeFiles()
        sys.exit(1)

    return


#
# Purpose: Create the invalid marker report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvMarkerReport ():
    global errorCount, errorReportNames

    print 'Create the invalid marker report'
    fpInvMrkRpt.write(string.center('Invalid Marker Report',110) + NL)
    fpInvMrkRpt.write(string.center('(' + timestamp + ')',110) + 2*NL)
    fpInvMrkRpt.write('%-12s  %-20s  %-20s  %-30s%s' %
                     ('MGI ID','Associated Object',
                      'Marker Status','Reason',NL))
    fpInvMrkRpt.write(12*'-' + '  ' +  20*'-' + '  ' + \
                      20*'-' + '  ' + 30*'-' + NL)

    cmds = []

    #
    # Find any MGI IDs from the coordinate file that:
    # 1) Do not exist in the database.
    # 2) Exist for a non-marker object. (Exclude annotation evidence)
    # 3) Exist for a marker, but the status is not "offical" or "interim".
    #
    cmds.append('select tmp.mgiID, ' + \
                       'null "name", ' + \
                       'null "status" ' + \
                'from tempdb..' + coordTempTable + ' tmp ' + \
                'where not exists (select 1 ' + \
                                  'from ACC_Accession a ' + \
                                  'where a.accID = tmp.mgiID) ' + \
                'union ' + \
                'select tmp.mgiID, ' + \
                       't.name, ' + \
                       'null "status" ' + \
                'from tempdb..' + coordTempTable + ' tmp, ' + \
                     'ACC_Accession a1, ' + \
                     'ACC_MGIType t ' + \
                'where a1.accID = tmp.mgiID and ' + \
                      'a1._LogicalDB_key = 1 and ' + \
                      'a1._MGIType_key not in (2, 25) and ' + \
                      'not exists (select 1 ' + \
                                  'from ACC_Accession a2 ' + \
                                  'where a2.accID = tmp.mgiID and ' + \
                                        'a2._LogicalDB_key = 1 and ' + \
                                        'a2._MGIType_key = 2) and ' + \
                      'a1._MGIType_key = t._MGIType_key ' + \
                'union ' + \
                'select tmp.mgiID, ' + \
                       't.name, ' + \
                       'ms.status ' + \
                'from tempdb..' + coordTempTable + ' tmp, ' + \
                     'ACC_Accession a, ' + \
                     'ACC_MGIType t, ' + \
                     'MRK_Marker m, ' + \
                     'MRK_Status ms ' + \
                'where a.accID = tmp.mgiID and ' + \
                      'a._LogicalDB_key = 1 and ' + \
                      'a._MGIType_key = 2 and ' + \
                      'a._MGIType_key = t._MGIType_key and ' + \
                      'a._Object_key = m._Marker_key and ' + \
                      'm._Marker_Status_key not in (1,3) and ' + \
                      'm._Marker_Status_key = ms._Marker_Status_key ' + \
                'order by tmp.mgiID')

    results = db.sql(cmds,'auto')

    #
    # Write the records to the report.
    #
    for r in results[0]:
        mgiID = r['mgiID']
        objectType = r['name']
        markerStatus = r['status']

        if objectType == None:
            objectType = ''
        if markerStatus == None:
            markerStatus = ''

        if objectType == '':
            reason = 'MGI ID does not exist'
        elif markerStatus == '':
            reason = 'MGI ID exists for non-marker'
        else:
            reason = 'Marker status is invalid'

        fpInvMrkRpt.write('%-12s  %-20s  %-20s  %-30s%s' %
            (mgiID,  objectType, markerStatus, reason, NL))

        # NOTE: Will need update to keep a dictionary of lines  from
	# which to create the new file minus those with skip errors
	# Below is comment and code from genemodelload version:
        # If the MGI ID and gene model ID are found in the association
        # dictionary, remove the gene model ID from the list so the
        # association doesn't get written to the load-ready association file.
        #
        if liveRun == "1":
            if coord.has_key(mgiID):
                list = coord[mgiID]
                if list.count(gmID) > 0:
                    list.remove(gmID)
                coord[mgiID] = list
    numErrors = len(results[0])
    fpInvMrkRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not invMrkRptFile in errorReportNames:
	    errorReportNames.append(invMrkRptFile + NL)
    return


#
# Purpose: Create the secondary marker report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createSecMarkerReport ():
    global coord, errorCount, errorReportNames

    print 'Create the secondary marker report'
    fpSecMrkRpt.write(string.center('Secondary Marker Report',108) + NL)
    fpSecMrkRpt.write(string.center('(' + timestamp + ')',108) + 2*NL)
    fpSecMrkRpt.write('%-16s  %-50s  %-16s%s' %
                     ('Secondary MGI ID',
                      'Marker Symbol','Primary MGI ID',NL))
    fpSecMrkRpt.write(16*'-' + '  ' + 50*'-' + '  ' + \
                      16*'-' + NL)

    cmds = []

    #
    # Find any MGI IDs from the coordinate file that are secondary IDs
    # for a marker.
    #
    cmds.append('select tmp.mgiID, ' + \
                       'm.symbol, ' + \
                       'a2.accID ' + \
                'from tempdb..' + coordTempTable + ' tmp, ' + \
                     'ACC_Accession a1, ' + \
                     'ACC_Accession a2, ' + \
                     'MRK_Marker m ' + \
                'where tmp.mgiID = a1.accID and ' + \
                      'a1._MGIType_key = 2 and ' + \
                      'a1._LogicalDB_key = 1 and ' + \
                      'a1.preferred = 0 and ' + \
                      'a1._Object_key = a2._Object_key and ' + \
                      'a2._MGIType_key = 2 and ' + \
                      'a2._LogicalDB_key = 1 and ' + \
                      'a2.preferred = 1 and ' + \
                      'a2._Object_key = m._Marker_key ' + \
                'order by tmp.mgiID')

    results = db.sql(cmds,'auto')
    #
    # Write the records to the report.
    #
    for r in results[0]:
        mgiID = r['mgiID']

        fpSecMrkRpt.write('%-16s  %-50s  %-16s%s' %
            (mgiID, r['symbol'], r['accID'], NL))

        #
        # NOTE: Will need update to keep a dictionary of lines  from
        # which to create the new file minus those with skip errors
        # Below is comment and code from genemodelload version:
        # If the MGI ID and gene model ID are found in the association
        # dictionary, remove the gene model ID from the list so the
        # association doesn't get written to the load-ready association file.
        #
        if liveRun == "1":
            if coord.has_key(mgiID):
                list = coord[mgiID]
                if list.count(gmID) > 0:
                    list.remove(gmID)
                coord[mgiID] = list
    numErrors = len(results[0])
    fpSecMrkRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not secMrkRptFile in errorReportNames:
	    errorReportNames.append(secMrkRptFile + NL)
    return

#
# Purpose: Create the invalid chromosome report
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#

def createInvChrReport ():
    global coord, errorCount, errorReportNames, invChrList

    print 'Create the invalid chromosome report'
    fpInvChrRpt.write(string.center('Invalid Chromosome Report',96) + NL
)
    fpInvChrRpt.write(string.center('(' + timestamp + ')',96) + 2*NL)
    fpInvChrRpt.write('%-20s  %-50s  %-10s%s' %
                         ('MGI ID', 'Marker Symbol', 'Invalid Chr', NL))
    fpInvChrRpt.write(20*'-' + '  ' + 50*'-' + '  ' +
                          10*'-' + '  ' + NL)

    cmds = []

    #
    # Find any cases where the feature chromosome is not a valid
    # mouse chromosome
    #
    results = db.sql('''select tc.mgiID,
                       tc.chromosome,
                       tc.mgiID,
                       m.symbol
                from tempdb..%s tc,
                     ACC_Accession a,
                     MRK_Marker m
                where tc.mgiID = a.accID
                and a._MGIType_key = 2
                and a._LogicalDB_key = 1
                and a.preferred = 1
                and a._Object_key = m._Marker_key
                and tc.chromosome not in (select mc.chromosome
		    from MRK_Chromosome mc
		    where mc._Organism_key = 1
		    and mc.chromosome != 'UN')
                order by tc.mgiID''' % coordTempTable, 'auto')

    #
    # Write the records to the report.
    #
    for r in results:
        mgiID = r['mgiID']
        invChrList.append('"%s"' % r['chromosome'])
        fpInvChrRpt.write('%-20s  %-50s  %-10s%s' %
            (mgiID, r['symbol'], r['chromosome'], NL))

        #
        # NOTE: Will need update to keep a dictionary of lines  from
        # which to create the new file minus those with skip errors
        # Below is comment and code from genemodelload version:
        # If the MGI ID and gene model ID are found in the association
        # dictionary, remove the gene model ID from the list so the
        # association doesn't get written to the load-ready association file.
        #
        if liveRun == "1":
            if coord.has_key(mgiID):
                list = coord[mgiID]
                if list.count(gmID) > 0:
                    list.remove(gmID)
                coord[mgiID] = list
    print 'Invalid Chromosomes: %s' % invChrList
    numErrors = len(results)
    fpInvChrRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
        if not invChrRptFile in errorReportNames:
            errorReportNames.append(invChrRptFile + NL)
    return

#
# Purpose: Create the chromosome discrepancy report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createChrDiscrepReport ():
    global coord, errorCount, errorReportNames, invChrList
    print 'Create the chromosome discrepancy report'
    fpChrDiscrepRpt.write(string.center('Chromosome Discrepancy Report',96) + NL)
    fpChrDiscrepRpt.write(string.center('(' + timestamp + ')',96) + 2*NL)
    fpChrDiscrepRpt.write('%-20s  %-50s  %-10s  %-10s%s' %
                         ('MGI ID', 'Marker Symbol', 'Marker Chr','Feature Chr',NL))
    fpChrDiscrepRpt.write(20*'-' + '  ' + 50*'-' + '  ' +
                          10*'-' + '  ' + 10*'-' + NL)

    cmds = []

    #
    # Find any cases where the marker in the coordinate file has
    # a different chromosome than the feature in the coordinate file
    #
    
    # exclude invalid chromosomes
    ic = string.join(invChrList, ',')
    print 'invalid chromosomes: %s' % ic
    results = db.sql('''select tc.mgiID, 
                       tc.chromosome as fChr, 
                       m.symbol, 
                       m.chromosome as mChr
                from tempdb..%s tc, 
                     ACC_Accession a, 
                     MRK_Marker m 
                where tc.chromosome not in (%s)
		and tc.mgiID = a.accID 
		and a._MGIType_key = 2 
                and a._LogicalDB_key = 1 
                and a.preferred = 1 
                and a._Object_key = m._Marker_key 
                and m.chromosome != tc.chromosome 
                order by tc.mgiID''' % (coordTempTable, ic), 'auto')


    #
    # Write the records to the report.
    #
    for r in results:
        mgiID = r['mgiID']

        fpChrDiscrepRpt.write('%-20s  %-50s  %-10s  %-10s%s' %
            (mgiID, r['symbol'], r['mChr'], r['fChr'], NL))

        #
        # NOTE: Will need update to keep a dictionary of lines  from
        # which to create the new file minus those with skip errors
        # Below is comment and code from genemodelload version:
        # If the MGI ID and gene model ID are found in the association
        # dictionary, remove the gene model ID from the list so the
        # association doesn't get written to the load-ready association file.
        #
        if liveRun == "1":
            if coord.has_key(mgiID):
                list = coord[mgiID]
                if list.count(gmID) > 0:
                    list.remove(gmID)
                coord[mgiID] = list

    numErrors = len(results)
    fpChrDiscrepRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not chrDiscrepRptFile in errorReportNames:
            errorReportNames.append(chrDiscrepRptFile + NL)
    return

def writeInvcoordStrandHeader():
    print 'Create the invalid coordinate and strand report'
    fpInvCoordStrandRpt.write(string.center('Invalid Coordinate and Strand Report',110) + NL)
    fpInvCoordStrandRpt.write(string.center('(' + timestamp + ')',110) + 2*NL)
    fpInvCoordStrandRpt.write('%-12s  %-20s  %-20s  %-10s  %-20s  %-30s%s' %
                     ('MGI ID','Start Coordinate','End Coordinate', 'Strand',
                      'Provider','Reason',NL))
    fpInvCoordStrandRpt.write(12*'-' + '  ' + 20*'-' + '  ' + 20*'-' + '  ' + \
                      10*'-' + '  ' + 20*'-' + '  ' + 30*'-' + NL)
    return

def writeInvcoordStrandFooter():
    fpInvCoordStrandRpt.write(NL + 'Number of Rows: ' + str(coordErrorCount) + NL)

    return
#
# Purpose: Create the invalid coordinate and strand report
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvCoordStrandReport (mgiID, startCoordinate, endCoordinate, strand, source):
    global errorCount, errorReportNames, coordErrorCount

    numErrors = 0    
    if len(re.findall('[^0-9]',startCoordinate)) > 0:
	numErrors += 1
	reason = 'Invalid start coordinate'
        fpInvCoordStrandRpt.write('%-12s  %-20s  %-20s  %-10s  %-20s  %-30s%s' %
            (mgiID, startCoordinate, endCoordinate, strand, source, reason, NL))

    if len(re.findall('[^0-9]',endCoordinate)) > 0:
	numErrors += 1
	reason = 'Invalid end coordinate'
	fpInvCoordStrandRpt.write('%-12s  %-20s  %-20s  %-10s  %-20s  %-30s%s' %
            (mgiID, startCoordinate, endCoordinate, strand, source, reason, NL))
    # if start and end are valid check that start < end
    if numErrors == 0:
	if startCoordinate != '' and endCoordinate != '' and (int(startCoordinate) > int(endCoordinate)):
	    numErrors += 1
	    reason = 'Start coordinate > end coordinate'
	    fpInvCoordStrandRpt.write('%-12s  %-20s  %-20s  %-10s  %-20s  %-30s%s' %
		(mgiID, startCoordinate, endCoordinate, strand, source, reason, NL))

    if strand != '-' and strand != '+' and strand != '':
	numErrors += 1
	reason = 'Invalid strand'
	fpInvCoordStrandRpt.write('%-12s  %-20s  %-20s  %-10s  %-20s  %-30s%s' %
            (mgiID, startCoordinate, endCoordinate, strand, source, reason, NL))
    print 'errorReportNames: %s' % errorReportNames
    if numErrors > 0:
	if not invCoordStrandRptFile + '\n' in errorReportNames:
	    print 'adding invCoordStrandRptFile to errorReportNames'
	    errorReportNames.append(invCoordStrandRptFile + NL)
	
    errorCount += numErrors
    coordErrorCount += numErrors

    return numErrors

#
# Purpose: Create report for input vs database source/display values
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#

def createSourceDisplayReport():
    global errorCount

    print 'Create the source display report'
    fpSourceDisplayRpt.write(string.center('Source/Display in Input, not in Database',110) + NL)
    fpSourceDisplayRpt.write(string.center('(' + timestamp + ')',110) + 2*NL)

    dbSourceList = []
    newSource = 0
    results = db.sql('''select distinct name, abbreviation
	from MAP_Coord_Collection''', 'auto')
    for r in results:
	dbSourceList.append('%s/%s' % (r['name'], r['abbreviation']))
    print 'dbSourceList: %s' % dbSourceList
    print 'sourceDisplayList: %s' % sourceDisplayList
    for s in sourceDisplayList:
	print 's: %s' % s
	if s not in dbSourceList:
	    print 'writing new source to report'
	    fpSourceDisplayRpt.write('%s%s' % (s, NL))
	    newSource += 1
    if newSource != 0:
	errorReportNames.append(sourceDisplayRptFile + NL)
	errorCount += 1
    else:
	fpSourceDisplayRpt.write('No new source/display in input' + NL)
    return

#
# Purpose: Create report for genome build values in the input 
#     and in the Database
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#

def createBuildReport():
    global errorCount

    print 'Create the build report'
    fpBuildRpt.write(string.center('Build Report',110) + NL)
    fpBuildRpt.write(string.center('(' + timestamp + ')',110) + 2*NL)

    #fpBuildRpt.write('Build Values in the Input' + NL)
    #fpBuildRpt.write(30*'-' + NL)
    #fpBuildRpt.write('%s%s%s' % (build, NL, NL))

    fpBuildRpt.write('Build Value Not in Database' + NL)
    fpBuildRpt.write(30*'-' + NL)
    results = db.sql('''select distinct version
		from MAP_Coordinate''', 'auto')
    dbBuildList = []
    for r in results:
	dbBuildList.append(r['version'])
    if build not in dbBuildList:
	fpBuildRpt.write(build + NL)
	errorReportNames.append(buildRptFile + NL)
	errorCount += 1
    return
#
# Main
#
checkArgs()
init()
openFiles()
loadTempTables() # also reports invalid coords and strand
createInvMarkerReport()
createSecMarkerReport()
createInvChrReport()
createChrDiscrepReport()
createSourceDisplayReport()
createBuildReport()
closeFiles()

if liveRun == "1":
    #createCoordLoadFile()
    print 'this is a live run'

# always display the source/display report name
#fpRptNamesRpt.write(sourceDisplayRptFile + NL)

if errorCount > 0:
    names = string.join(errorReportNames,'' )
    fpRptNamesRpt.write(names)
    fpRptNamesRpt.close()
    sys.exit(2)
else:
    fpRptNamesRpt.close()
    sys.exit(0)
