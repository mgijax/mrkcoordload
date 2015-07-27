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
#          MGD_DBUSER
#          MGD_DBPASSWORDFILE
#          TEMP_TABLE
#          INVALID_MARKER_RPT
#          SEC_MARKER_RPT
#	   INVALID_CHR_RPT
#          CHR_DISCREP_RPT
#	   INVALID_COORD_STRAND_RPT
#	   NON_MIRNA_MARKER_RPT
#	   MIRBASE_DELETE_RPT
#          MIRBASE_DUP_RPT
#	   MIRBASE_OTHER_MKR_RPT
#	   SOURCE_DISPLAY_RPT
#	   BUILD_RPT
#	   RPT_NAMES_RPT
#	   INPUT_FILE_LOAD
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
#	   8) miRBase ID (optional)
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
#      - QC report (${INVALID_CHR_RPT})
#
#      - QC report (${CHR_DISCREP_RPT})
#
#      - QC report (${INVALID_COORD_STRAND_RPT})
#
#      - QC report (${NON_MIRNA_MARKER_RPT})
#
#      - QC report (${MIRBASE_DELETE_RPT})
#
#      - QC report (${MIRBASE_DUP_RPT})
#
#      - QC report (${MIRBASE_OTHER_MKR_RPT})
#
#      - QC report (${SOURCE_DISPLAY_RPT})
#
#      - QC report (${BUILD_RPT})
#
#      - QC report (${RPT_NAMES_RPT})
#
#      - Load-ready input file (${INPUT_FILE_LOAD})
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
#      7) If this is a "live" run, create the load-ready coordinate file
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
user = os.environ['MGD_DBUSER']
passwordFileName = os.environ['MGD_DBPASSWORDFILE']

bcpCommand = os.environ['PG_DBUTILS'] + '/bin/bcpin.csh'

liveRun = os.environ['LIVE_RUN']

coordBCPFile = os.environ['INPUT_FILE_BCP']
coordTempTable = os.environ['TEMP_TABLE']
coordLoadFile = os.environ['INPUT_FILE_LOAD']

invMrkRptFile = os.environ['INVALID_MARKER_RPT']
secMrkRptFile = os.environ['SEC_MARKER_RPT']
invChrRptFile =  os.environ['INVALID_CHR_RPT']
chrDiscrepRptFile = os.environ['CHR_DISCREP_RPT']
invCoordStrandRptFile =  os.environ['INVALID_COORD_STRAND_RPT']
nonMirnaMrkRptFile =  os.environ['NON_MIRNA_MARKER_RPT']
mirbaseDeleteRptFile =  os.environ['MIRBASE_DELETE_RPT']
dupMirbaseIdRptFile =  os.environ['MIRBASE_DUP_RPT']
mirbaseOtherMrkRptFile = os.environ['MIRBASE_OTHER_MKR_RPT']
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

# MGI IDs that did not pass muster and will be removed
# from the load-ready file
badMGIIDs = {}

# mirbase IDs in the input mapped to a dictionary of MGI ID to
# it's input line
mb2mgiInInputDict = {} # {mbID:[{mgiID1:line}, {mgiID2:line}, ...], ...}

# mirbase IDs in the database mapped to a dictionary of MGI ID to 
# its result set
mb2mgiInDbDict = {} # {mbID:[mgiID1, mgiID2: ...], ...}

# MGI Ids in the input mapped to their miRBase associations
mgi2mbInDbDict = {} # {mgiID:[symbol, mbID1, mbID2, ...], ...}

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
    db.set_sqlPasswordFromFile(passwordFileName)

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
    global fpInvMrkRpt, fpSecMrkRpt, fpInvChrRpt, fpChrDiscrepRpt
    global fpInvCoordStrandRpt, fpNonMirnaMrkRpt, fpMirbaseDeleteRpt
    global fpDupMirbaseIdRpt, fpMirbaseOtherMrkRpt, fpSourceDisplayRpt
    global fpBuildRpt, fpRptNamesRpt

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
	fpInvChrRpt = open(invChrRptFile, 'a')
    except:
        print 'Cannot open report file: ' + invChrRptFile
        sys.exit(1)
    try:
        fpChrDiscrepRpt = open(chrDiscrepRptFile, 'a')
    except:
        print 'Cannot open report file: ' + chrDiscrepRptFile
        sys.exit(1)
    try:
        fpInvCoordStrandRpt = open(invCoordStrandRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + invCoordStrandRptFile
        sys.exit(1)
    try:
        fpNonMirnaMrkRpt = open(nonMirnaMrkRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + nonMirnaMrkRptFile
        sys.exit(1)
    try:
        fpMirbaseDeleteRpt = open(mirbaseDeleteRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + mirbaseDeleteRptFile
        sys.exit(1)
    try:
	fpDupMirbaseIdRpt = open(dupMirbaseIdRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + dupMirbaseIdRptFile
        sys.exit(1)
    try:
        fpMirbaseOtherMrkRpt = open(mirbaseOtherMrkRptFile, 'a')
    except:
        print 'Cannot  open report file: ' + mirbaseOtherMrkRptFile
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
    fpInvChrRpt.close()
    fpChrDiscrepRpt.close()
    fpInvCoordStrandRpt.close()
    fpNonMirnaMrkRpt.close()
    fpMirbaseDeleteRpt.close()
    fpDupMirbaseIdRpt.close()
    fpMirbaseOtherMrkRpt.close()
    fpSourceDisplayRpt.close()
    fpBuildRpt.close()
    return


#
# Purpose: Load the data from the input files into the temp tables.
#          This function also reports invalid start/end/strand as
#          we can't load characters into the integer columns.
# Returns: Nothing
# Assumes: All columns exist
# Effects: Nothing
# Throws: Nothing
#

def loadTempTables ():
    global build, mb2mgiInInputDict, header

    print 'Create a bcp file from the coordinate input file'
    sys.stdout.flush()

    #
    # Read each record from the coordinate input file, perform validation
    # checks and write them to a bcp file.
    #
    
    # set the global header value; remove any tabs, preserve newline
    header = '%s\n' % fpCoord.readline().strip() 

    tokens = header.split(';')
    for t in tokens:
	a = t.split('=')
	if a[0].strip().lower() == 'build':
	    build = a[1].strip()
    count = 1
    writeInvcoordStrandHeader()
    for line in fpCoord.readlines():
	#print 'line: %s' % line
        tokens = re.split(TAB, line[:-1])
        mgiID = tokens[0].strip()
        chromosome = tokens[1].strip()
        startCoordinate = tokens[2].strip()
        endCoordinate = tokens[3].strip()
        strand = tokens[4].strip()
        source = tokens[5].strip()
	display = tokens[6].strip()
	miRBaseID = tokens[7].strip()
	if miRBaseID != '':
	    for id in string.split(miRBaseID, ','):
		id = string.strip(id)
		if not mb2mgiInInputDict.has_key(id):
		    mb2mgiInInputDict[id] = []
		mb2mgiInInputDict[id].append(mgiID)
	sourceDisplay = '%s/%s' % (source, display)
	#print 'sourceDisplay: %s' % sourceDisplay
	if not sourceDisplay in sourceDisplayList:
	    sourceDisplayList.append(sourceDisplay)
        errors = createInvCoordStrandReport(mgiID, startCoordinate, endCoordinate, strand, source)
	if errors != 0:
	    continue

        fpCoordBCP.write(mgiID + TAB + chromosome + TAB +
                     startCoordinate + TAB + endCoordinate + TAB +
                      strand + TAB + source + TAB + display + TAB +
                      miRBaseID + TAB + build + NL)
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

    bcpCmd = '%s %s %s %s "/" %s "\\t" "\\n" mgd' % \
	(bcpCommand, db.get_sqlServer(), db.get_sqlDatabase(),coordTempTable,
	coordBCPFile)

    print 'bcp cmd = %s' % bcpCommand
    sys.stdout.flush()

    rc = os.system(bcpCmd)
    if rc <> 0:
        closeFiles()
        sys.exit(1)

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
# Purpose: Create the invalid marker report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvMarkerReport ():
    global errorCount, errorReportNames, badMGIIDs

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
                       'null as name, ' + \
                       'null as status ' + \
                'from ' + coordTempTable + ' tmp ' + \
                'where not exists (select 1 ' + \
                                  'from ACC_Accession a ' + \
                                  'where a.accID = tmp.mgiID) ' + \
                'union ' + \
                'select tmp.mgiID, ' + \
                       't.name, ' + \
                       'null as status ' + \
                'from ' + coordTempTable + ' tmp, ' + \
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
                'from ' + coordTempTable + ' tmp, ' + \
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
                'order by mgiID')

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

        #
        # If this is a live run of the load, maintain a list of MGI IDs that
        # are being rejected. The input lines with these MGI IDs will be
        # excluded from the new "load-ready" input file that gets created
        # at the end of this script.
        #
        if liveRun == "1":
            if not badMGIIDs.has_key(mgiID):
                badMGIIDs[mgiID] = ''

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
    global errorCount, errorReportNames, badMGIIDs

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
                'from ' + coordTempTable + ' tmp, ' + \
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
                'order by mgiID')

    results = db.sql(cmds,'auto')
    #
    # Write the records to the report.
    #
    for r in results[0]:
        mgiID = r['mgiID']

        fpSecMrkRpt.write('%-16s  %-50s  %-16s%s' %
            (mgiID, r['symbol'], r['accID'], NL))

        #
        # If this is a live run of the load, maintain a list of MGI IDs that
        # are being rejected. The input lines with these MGI IDs will be
        # excluded from the new "load-ready" input file that gets created
        # at the end of this script.
        #
        if liveRun == "1":
            if not badMGIIDs.has_key(mgiID):
                badMGIIDs[mgiID] = ''

    numErrors = len(results[0])
    fpSecMrkRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not secMrkRptFile in errorReportNames:
	    errorReportNames.append(secMrkRptFile + NL)
    return


#
# Purpose: Create the invalid chromosome report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvChrReport ():
    global errorCount, errorReportNames, invChrList, badMGIIDs

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
                from %s tc,
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
                order by mgiID''' % coordTempTable, 'auto')

    #
    # Write the records to the report.
    #
    for r in results:
        mgiID = r['mgiID']
        invChrList.append('"%s"' % r['chromosome'])
        fpInvChrRpt.write('%-20s  %-50s  %-10s%s' %
            (mgiID, r['symbol'], r['chromosome'], NL))

        #
        # If this is a live run of the load, maintain a list of MGI IDs that
        # are being rejected. The input lines with these MGI IDs will be
        # excluded from the new "load-ready" input file that gets created
        # at the end of this script.
        #
        if liveRun == "1":
            if not badMGIIDs.has_key(mgiID):
                badMGIIDs[mgiID] = ''

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
    global errorCount, errorReportNames, invChrList

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
    results = db.sql('''select tc.mgiID, 
                       tc.chromosome as fChr, 
                       m.symbol, 
                       m.chromosome as mChr
                from %s tc, 
                     ACC_Accession a, 
                     MRK_Marker m 
                where tc.chromosome not in (%s)
		and tc.mgiID = a.accID 
		and a._MGIType_key = 2 
                and a._LogicalDB_key = 1 
                and a.preferred = 1 
                and a._Object_key = m._Marker_key 
                and m.chromosome != tc.chromosome 
                order by mgiID''' % (coordTempTable, ic), 'auto')


    #
    # Write the records to the report.
    #
    for r in results:
        mgiID = r['mgiID']

        fpChrDiscrepRpt.write('%-20s  %-50s  %-10s  %-10s%s' %
            (mgiID, r['symbol'], r['mChr'], r['fChr'], NL))

    numErrors = len(results)
    fpChrDiscrepRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not chrDiscrepRptFile in errorReportNames:
            errorReportNames.append(chrDiscrepRptFile + NL)
    return


#
# Purpose: Create the invalid coordinate and strand report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createInvCoordStrandReport (mgiID, startCoordinate, endCoordinate, strand, source):
    global errorCount, errorReportNames, coordErrorCount, badMGIIDs

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

    if numErrors > 0:
        #
        # If this is a live run of the load, maintain a list of MGI IDs that
        # are being rejected. The input lines with these MGI IDs will be
        # excluded from the new "load-ready" input file that gets created
        # at the end of this script.
        #
        if liveRun == "1":
            if not badMGIIDs.has_key(mgiID):
                badMGIIDs[mgiID] = ''

	if not invCoordStrandRptFile + '\n' in errorReportNames:
	    errorReportNames.append(invCoordStrandRptFile + NL)
	
    errorCount += numErrors
    coordErrorCount += numErrors

    return numErrors


#
# Purpose: Create the non-miRNA marker report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createNonMirnaMarkerReport ():
    global errorCount, errorReportNames

    print 'Create the non-miRNA marker report'
    fpNonMirnaMrkRpt.write(string.center('Non-miRNA Marker Report',108) + NL)
    fpNonMirnaMrkRpt.write(string.center('(' + timestamp + ')',108) + 2*NL)
    fpNonMirnaMrkRpt.write('%-16s  %-50s  %-16s%s' %
                     ('MGI ID','Feature Type','miRBase ID',NL))
    fpNonMirnaMrkRpt.write(16*'-' + '  ' + 50*'-' + '  ' + 16*'-' + NL)

    cmds = []

    #
    # Find any MGI IDs from the coordinate file that are supposed to be
    # associated with a miRBase ID, but the marker does not have a
    # "miRNA gene" feature type.
    #
    # we use tc.mirbaseID like "%MI%" because mirbaseID is a text field
    #  and only like is allowed for a text field in the where clause 
    #
    cmds.append('select tc.mgiID, tc.mirbaseID, m.term ' + \
                'from ' + coordTempTable + ' tc, ' + \
                     'ACC_Accession a, ' + \
                     'MRK_MCV_Cache m ' + \
                'where tc.mirbaseID like "%MI%" and ' + \
                      'tc.mgiID = a.accID and ' + \
                      'a._MGIType_key = 2 and ' + \
                      'a._LogicalDB_key = 1 and ' + \
                      'a.preferred = 1 and ' + \
                      'a._Object_key = m._Marker_key and ' + \
                      'm.qualifier = "D" and ' + \
                      'm.term != "miRNA gene" ' + \
                'order by mgiID')

    results = db.sql(cmds,'auto')
    #
    # Write the records to the report.
    #
    for r in results[0]:
        mgiID = r['mgiID']
        mirbaseID = r['mirbaseID']
        featureType = r['term']

        fpNonMirnaMrkRpt.write('%-16s  %-50s  %-16s%s' %
            (mgiID, featureType, mirbaseID, NL))

    numErrors = len(results[0])
    fpNonMirnaMrkRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not nonMirnaMrkRptFile in errorReportNames:
	    errorReportNames.append(nonMirnaMrkRptFile + NL)
    return

#
# Purpose: Create the miRBase/marker association "to-be-deleted" report.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createMirbaseDeleteReport ():
    global errorCount, errorReportNames, mgi2mbInDbDict

    print 'Create the miRBase delete report'
    fpMirbaseDeleteRpt.write(string.center('miRBase/Marker Deletion Report',108) + NL)
    fpMirbaseDeleteRpt.write(string.center('(' + timestamp + ')',108) + 2*NL)
    fpMirbaseDeleteRpt.write('%-16s  %-16s  %-60s  %-60s%s' %
                     ('Input MGI ID','Input Symbol','miRBase/Marker Associations To Be Added', 'miRBase/Marker Associations To Be Deleted',NL))
    fpMirbaseDeleteRpt.write(16*'-' + '  ' + 16*'-' + '  ' + 60*'-' + '  ' + 60*'-' + NL)


    #
    # For each marker in the input report mirbase IDs being deleted 
    # from the database and mirbase IDs being added
    #
    db.useOneConnection(1)
    db.sql('''select a.accid as mgiID, m._Marker_key, m.symbol
	into temp mkrs
	from ACC_Accession a, MRK_Marker m
	where m._Organism_key = 1
	and m._Marker_Status_key in (1,3)
	and m._Marker_key = a._Object_key
	and a._MGIType_key = 2
	and a._LogicalDB_key = 1
	and a.prefixPart = 'MGI:' ''', None)

    db.sql('create index idx1 on mkrs(_Marker_key)', None)

    results = db.sql('''select m.*, a.accid as mbID
	from mkrs m 
	left outer join
	ACC_Accession a on
		m._marker_key=a._object_key
	where a._MGIType_key = 2
	and a._LogicalDB_key = 83''', 'auto')

    for r in results:
	mgiID = r['mgiID']
	symbol = r['symbol']
	mbID = r['mbID']
	if not mgi2mbInDbDict.has_key(mgiID):
	     mgi2mbInDbDict[mgiID] = [symbol]
	if mbID != None:
	    mgi2mbInDbDict[mgiID].append(mbID)
	
    results = db.sql('''select mgiID, mirbaseID
	from %s''' % coordTempTable, 'auto')
    #
    # Write the records to the report.
    #
    numErrors = 0
    for r in results:
        inputMgiID = r['mgiID']

	#
	# Get list of input mirbase IDs for this marker
	# comma delimited string in the input, create list, iterate
	# over IDs and remove any leading/trailing whitespace
	#
	mbID = r['mirbaseID']
	if mbID == None:
	    mbID = ''
        tempList = string.split(mbID, ',')
	inputMbID = []
	for id in tempList:
	    inputMbID.append(string.strip(id))
	#
	# Get list of database mirbase IDs for this marker
	#
	dbInfo = []
	if mgi2mbInDbDict.has_key(inputMgiID):
	    dbInfo = mgi2mbInDbDict[inputMgiID]
	else:
	    #print '%s not in database' % inputMgiID
	    continue
	symbol = dbInfo[0]
	dbMbID = []
	if len(dbInfo) > 1:
	    dbMbID = dbInfo[1:]
	#
	# the deleted mirbase ids are those in the database that are
	# not in the input
	#
	deletedMbID = set(dbMbID).difference(set(inputMbID))
	addedMbID = set(inputMbID).difference(set(dbMbID))
	#print 'deletedMbID: %s' % deletedMbID
	#print 'addedMbID: %s' % addedMbID
	if deletedMbID:
	    numErrors += 1
	    fpMirbaseDeleteRpt.write('%-16s  %-16s  %-60s  %-60s%s' % (inputMgiID, symbol, string.join(addedMbID, ', '), string.join(deletedMbID, ', '), NL))

    db.sql('drop table mkrs', None)
    db.useOneConnection(0)
    fpMirbaseDeleteRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
	if not mirbaseDeleteRptFile in errorReportNames:
	    errorReportNames.append(mirbaseDeleteRptFile + NL)
    return

#
# Purpose: Create report for duplicate miRBase IDs in the input
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createDupMirbaseIdReport():
    global errorCount, errorReportNames

    print 'Create the duplicate miRBase ID report'
    fpDupMirbaseIdRpt.write(string.center('Duplicate miRBase ID Report',108) + NL)
    fpDupMirbaseIdRpt.write(string.center('(' + timestamp + ')',108) + 2*NL)
    fpDupMirbaseIdRpt.write('%-16s  %-40s%s' %
                     ('Input miRBase ID', 'Associated MGI IDs', NL))
    fpDupMirbaseIdRpt.write(16*'-' + '  ' + 50*'-' + NL)

    numErrors = 0
    for mbId in mb2mgiInInputDict.keys():
	mgiIdList = mb2mgiInInputDict[mbId]
	if len(mgiIdList) > 1:
	    fpDupMirbaseIdRpt.write('%-16s  %-50s%s' % 
		(mbId, string.join(mgiIdList, ','), NL ) )
	    numErrors += 1
    fpDupMirbaseIdRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)

    errorCount += numErrors
    if numErrors > 0:
        if not dupMirbaseIdRptFile in errorReportNames:
            errorReportNames.append(dupMirbaseIdRptFile + NL)
    return

#
# Purpose: Create report for miRBase IDs in the input associated with
#	other markers in the database
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createMirbaseOtherMrkReport():
    global errorCount, errorReportNames

    print 'Create the miRBase ID associated with other marker report'
    db.useOneConnection(1)
    db.sql('''select a.accid as mgiID, mm._Marker_key
        into temp mkrs
        from ACC_Accession a, MRK_Marker mm, MRK_Location_Cache m
        where mm._Organism_key = 1
        and mm._Marker_key =  m._Marker_key
	and m._Marker_key = a._Object_key
        and a._MGIType_key = 2
        and a._LogicalDB_key = 1
        and a.prefixPart = 'MGI:' ''', None)

    db.sql('create index idx1 on mkrs(_Marker_key)', None)

    results = db.sql('''select m.*, a.accid as mbID
        from mkrs m 
	left outer join
	 ACC_Accession a on
		m._marker_key=a._object_key
        where a._MGIType_key = 2
        and a._LogicalDB_key = 83''', 'auto')

    for r in results:
	mbID = r['mbID']
	mgiID = r['mgiID']
	if not mb2mgiInDbDict.has_key(mbID):
	    mb2mgiInDbDict[mbID] = []
	mb2mgiInDbDict[mbID].append(mgiID)

    print 'Create the miRBase IDs associated with other markers report'
    db.sql('drop table mkrs', None)
    db.useOneConnection(0)

    fpMirbaseOtherMrkRpt.write(string.center('miRBase IDs in the Input Associated with Different Markers in MGI Report',108) + NL)
    fpMirbaseOtherMrkRpt.write(string.center('(' + timestamp + ')',108) + 2*NL)
    fpMirbaseOtherMrkRpt.write('%-16s  %-40s  %-40s%s' %
                     ('Input miRBase ID','Input MGI IDs', 'Database MGI IDs',NL))
    fpMirbaseOtherMrkRpt.write(16*'-' + '  ' + 40*'-' + '  ' + 40*'-' + NL)
 
    numErrors = 0
    for mbID in mb2mgiInInputDict.keys():
	#
	#  get input mgiIDs associated with mbID
	# 

        mgiIdInInputList = mb2mgiInInputDict[mbID]

	#
	# get db mgiIDs associated with mbID
	#

	if mb2mgiInDbDict.has_key(mbID):
	    mgiIdInDbList = mb2mgiInDbDict[mbID]
	else:
	    #print '%s not associate with marker in the database' % mbID
	    continue

	#
	# diff the sets - we're looking for any mgiIDs in the db not in the
	# input for  mbID
	#

	diffSet = set(mgiIdInDbList).difference(set(mgiIdInInputList))

	# DEBUG
	#print 'mbID: %s' % mbID
	#print 'mgiIdInDbList: %s' % mgiIdInDbList
	#print 'mgiIdInInputList: %s' % mgiIdInInputList
	#print 'diffSet: %s' % diffSet

	# report mgiIDs for mbID in the db that are not in the input
	if diffSet:
	    numErrors += 1
	    #
	    # get input info
	    #
	    inputData = []
	    dbData = []
	    for id in mgiIdInInputList:
		inputData.append(id)
	    #
	    # get db info
	    #
	    for id in diffSet:
		dbData.append(id)
	    
	    fpMirbaseOtherMrkRpt.write('%-16s  %-40s  %-40s%s' % (mbID, string.join(inputData, ', '), string.join(dbData, ', '), NL))

    errorCount += numErrors
    fpMirbaseOtherMrkRpt.write(NL + 'Number of Rows: ' + str(numErrors) + NL)
    if numErrors > 0:
        if not mirbaseOtherMrkRptFile in errorReportNames:
            errorReportNames.append(mirbaseOtherMrkRptFile + NL)
    return

#
# Purpose: Create report for input vs database source/display values.
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
    #print 'dbSourceList: %s' % dbSourceList
    #print 'sourceDisplayList: %s' % sourceDisplayList
    for s in sourceDisplayList:
	if s not in dbSourceList:
	    fpSourceDisplayRpt.write('%s%s' % (s, NL))
	    newSource += 1
    if newSource != 0:
	errorReportNames.append(sourceDisplayRptFile + NL)
	errorCount += 1
    else:
	fpSourceDisplayRpt.write('No new source/display in input' + NL)
    return


#
# Purpose: Create report for genome build values in the input and in the
#          database.
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
# Purpose: Create the "load-ready" coordinate file from input records that
#          were not rejected by QC checks.
# Returns: Nothing
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def createCoordLoadFile ():

    try:
        fpCoord = open(coordFile, 'r')
    except:
        print 'Cannot open input file: ' + coordFile
        sys.exit(1)

    try:
        fpLoadFile = open(coordLoadFile, 'w')
    except:
        print 'Cannot open output file: ' + coordLoadFile
        sys.exit(1)
    
    # remove header line - use global header with tabs removed
    junk = fpCoord.readline()
    fpLoadFile.write(header)
    for line in fpCoord.readlines():
        tokens = re.split(TAB, line[:-1])
        mgiID = tokens[0].strip()

        #
        # Only write the input record to the load file if the MGI ID was
        # not added to the dictionary of rejected MGI IDs.
        #
        if not badMGIIDs.has_key(mgiID):
            fpLoadFile.write(line)

    fpCoord.close()
    fpLoadFile.close()


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
createNonMirnaMarkerReport()
createMirbaseDeleteReport()
createDupMirbaseIdReport()
createMirbaseOtherMrkReport()
createSourceDisplayReport()
createBuildReport()
closeFiles()

if liveRun == "1":
    createCoordLoadFile()

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
