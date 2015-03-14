#!/bin/sh
#
#  mrkcoordQC.sh
###########################################################################
#
#  Purpose:
#
#      This script is a wrapper around the process that creates sanity/QC
#      reports for a given marker coordinate load input file
#
#  Usage:
#
#      mrkcoordQC.sh  filename  [ "live" ]
#
#      where
#          filename = path to the input file
#          live = option to let the script know that this is a "live" run
#                 so the output files are created under the /data/loads
#                 directory instead of the current directory
#
#  Env Vars:
#
#      See the configuration file
#
#  Inputs:
#
#      - marker coordinate input file with the following tab-delimited fields:
#
#          1) Marker MGI ID
#          2) Chromosome
#          3) Start Coordinate
#          4) End Coordinate
#          5) Strand (+ or -)
#          6) Provider - the source of the data e.g. 'NCBI UniSTS'
#	   7) Provider Display - What is displayed in the WI e.g. 'UniSTS'
#          8) miRBase ID
#
#  Outputs:
#
#      - Sanity report for the input file.
#
#      - Log file (${MRKCOORDQC_LOGFILE})
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  Fatal error occurred
#
#  Assumes:  Nothing
#
#  Implementation:
#
#      This script will perform following steps:
#
#      ) Validate the arguments to the script.
#      ) Source the configuration files to establish the environment.
#      ) Verify that the input file exists.
#      ) Initialize the report files.
#      ) Clean up the input file by removing blank lines, Ctrl-M, etc.
#      ) Generate the sanity report.
#      ) Create temp tables for the input data.
#      ) Load the input files into temp tables.
#      ) Call mrkcoordQC.py to generate the QC reports.
#      ) Drop the temp tables.
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
#  07/19/2012  sc  Initial development
#
###########################################################################

CURRENTDIR=`pwd`
BINDIR=`dirname $0`

CONFIG=`cd ${BINDIR}/..; pwd`/mrkcoordload.config
USAGE='Usage: mrkcoordQC.sh  filename  [ "live" ]'

LIVE_RUN=0; export LIVE_RUN

#
# Make sure an input file was passed to the script. If the optional "live"
# argument is given, that means that the output files are located in the
# /data/loads/... directory, not in the current directory.
#
if [ $# -eq 1 ]
then
    INPUT_FILE=$1
elif [ $# -eq 2 -a "$2" = "live" ]
then
    INPUT_FILE=$1
    LIVE_RUN=1
else
    echo ${USAGE}; exit 1
fi

#
# Create a temporary file and make sure that it is removed when this script
# terminates.
#
TMP_FILE=/tmp/`basename $0`.$$
touch ${TMP_FILE}
trap "rm -f ${TMP_FILE}" 0 1 2 15

#
# Make sure the configuration file exists and source it.
#
if [ -f ${CONFIG} ]
then
    . ${CONFIG}
else
    echo "Missing configuration file: ${CONFIG}"
    exit 1
fi

#
# Make sure the input file exists (regular file or symbolic link).
#
if [ "`ls -L ${INPUT_FILE} 2>/dev/null`" = "" ]
then
    echo "Missing input file: ${INPUT_FILE}"
    exit 1
fi

#
# If this is not a "live" run, the output, log and report files should reside
# in the current directory, so override the default settings.
#
if [ ${LIVE_RUN} -eq 0 ]
then
    INPUT_FILE_QC=${CURRENTDIR}/`basename ${INPUT_FILE_QC}`
    INPUT_FILE_BCP=${CURRENTDIR}/`basename ${INPUT_FILE_BCP}`
    MRKCOORDQC_LOGFILE=${CURRENTDIR}/`basename ${MRKCOORDQC_LOGFILE}`
    SANITY_RPT=${CURRENTDIR}/`basename ${SANITY_RPT}`
    INVALID_MARKER_RPT=${CURRENTDIR}/`basename ${INVALID_MARKER_RPT}`
    SEC_MARKER_RPT=${CURRENTDIR}/`basename ${SEC_MARKER_RPT}`
    INVALID_CHR_RPT=${CURRENTDIR}/`basename ${INVALID_CHR_RPT}`
    CHR_DISCREP_RPT=${CURRENTDIR}/`basename ${CHR_DISCREP_RPT}`
    INVALID_COORD_STRAND_RPT=${CURRENTDIR}/`basename ${INVALID_COORD_STRAND_RPT}`
    NON_MIRNA_MARKER_RPT=${CURRENTDIR}/`basename ${NON_MIRNA_MARKER_RPT}`
    MIRBASE_DELETE_RPT=${CURRENTDIR}/`basename ${MIRBASE_DELETE_RPT}`
    MIRBASE_DUP_RPT=${CURRENTDIR}/`basename ${MIRBASE_DUP_RPT}`
    MIRBASE_OTHER_MKR_RPT=${CURRENTDIR}/`basename ${MIRBASE_OTHER_MKR_RPT}`
    SOURCE_DISPLAY_RPT=${CURRENTDIR}/`basename ${SOURCE_DISPLAY_RPT}`
    BUILD_RPT=${CURRENTDIR}/`basename ${BUILD_RPT}`
    RPT_NAMES_RPT=${CURRENTDIR}/`basename ${RPT_NAMES_RPT}`

fi

#
# Initialize the log file.
#
LOG=${MRKCOORDQC_LOGFILE}
rm -rf ${LOG}
touch ${LOG}

#
# Initialize the report files to make sure the current user can write to them.
#
RPT_LIST="${SANITY_RPT} ${INVALID_MARKER_RPT} ${SEC_MARKER_RPT} ${INVALID_CHR_RPT} ${CHR_DISCREP_RPT} ${INVALID_COORD_STRAND_RPT} ${NON_MIRNA_MARKER_RPT} ${MIRBASE_DELETE_RPT} ${MIRBASE_DUP_RPT} ${MIRBASE_OTHER_MKR_RPT} ${SOURCE_DISPLAY_RPT} ${BUILD_RPT} ${RPT_NAMES_RPT}"

for i in ${RPT_LIST}
do
    rm -f $i; >$i
done

#
# Convert the input file into a QC-ready version that can be used to
# run the sanity/QC reports against. This involves doing the following:
# 1) Extract columns 1 thru 8
# 2) Extract only lines that have alphanumerics (excludes blank lines)
# 3) Remove any Ctrl-M characters (dos2unix)
# 4) Extract only lines that do not begin with '#'
#
cat ${INPUT_FILE} | cut -d'	' -f1-8 | grep '[0-9A-Za-z]' | grep -v '^#' > ${INPUT_FILE_QC}
dos2unix ${INPUT_FILE_QC} ${INPUT_FILE_QC} 2>/dev/null

#
# FUNCTION: Write invalid header in an input file
#           to the sanity report.
#
checkHeader ()
{
    FILE=$1    # The input file to check
    REPORT=$2  # The sanity report to write to
    echo "Invalid Header" >> ${REPORT}
    echo "---------------" >> ${REPORT}
    header=`head -1 ${INPUT_FILE}`
    if [ "`head -1 ${INPUT_FILE} | grep -i '^build='`" = "" ]
    then
	echo ${header} >> ${REPORT}
	return 1
    else
	return 0
    fi
}

#
# FUNCTION: Check for duplicate lines in an input file and write the lines
#           to the sanity report.
#
checkDupLines ()
{
    FILE=$1    # The input file to check
    REPORT=$2  # The sanity report to write to

    echo "" >> ${REPORT}
    echo "" >> ${REPORT}
    echo "Duplicate Lines" >> ${REPORT}
    echo "---------------" >> ${REPORT}
    sort ${FILE} | uniq -d > ${TMP_FILE}
    cat ${TMP_FILE} >> ${REPORT}
    if [ `cat ${TMP_FILE} | wc -l` -eq 0 ]
    then
        return 0
    else
        return 1
    fi
}

#
# FUNCTION: Check for a duplicated field in an input file and write the field
#           value to the sanity report.
#
checkDupFields ()
{
    FILE=$1         # The input file to check
    REPORT=$2       # The sanity report to write to
    FIELD_NUM=$3    # The field number to check
    FIELD_NAME=$4   # The field name to show on the sanity report

    echo "" >> ${REPORT}
    echo "" >> ${REPORT}
    echo "Duplicate ${FIELD_NAME}" >> ${REPORT}
    echo "------------------------------" >> ${REPORT}
    cut -d'	' -f${FIELD_NUM} ${FILE} | sort | uniq -d > ${TMP_FILE}
    cat ${TMP_FILE} >> ${REPORT}
    if [ `cat ${TMP_FILE} | wc -l` -eq 0 ]
    then
        return 0
    else
        return 1
    fi
}

#
# FUNCTION: Check for lines with missing columns and data in input file and
#           write the line numbers to the sanity report.
#
checkColumns ()
{   
    FILE=$1         # The input file to check
    REPORT=$2       # The sanity report to write to
    NUM_COLUMNS=$3  # The number of columns expected in each input record

    echo "" >> ${REPORT}
    echo "" >> ${REPORT}
    echo "Lines With Missing Columns or Data" >> ${REPORT}
    echo "-----------------------------------" >> ${REPORT}
    ${MRKCOORDLOAD}/bin/checkColumns.py ${FILE} ${NUM_COLUMNS} > ${TMP_FILE}
    cat ${TMP_FILE} >> ${REPORT} 
    if [ `cat ${TMP_FILE} | wc -l` -eq 0 ]
    then
        return 0
    else
        return 1
    fi
}

#
# FUNCTION: Check the MGI ID column for data that does not start with 'MGI:'
#           and write the field value to the sanity report.
#
checkMGIIDS ()
{
    FILE=$1         # The input file to check
    REPORT=$2       # The sanity report to write to

    echo "" >> ${REPORT}
    echo "" >> ${REPORT}
    echo "Bad MGI ID" >> ${REPORT}
    echo "---------------" >> ${REPORT}
    # get the first column excluding the header which contains '='
    cat ${FILE} | grep -v '=' | grep -i -v '^MGI:' > ${TMP_FILE}
    cat ${TMP_FILE} >> ${REPORT}
    if [ `cat ${TMP_FILE} | wc -l` -eq 0 ]
    then
        return 0
    else
        return 1
    fi
}

#
# Run sanity checks on the gene model input file.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Run sanity checks on the input file" >> ${LOG}
FILE_ERROR=0

checkHeader ${INPUT_FILE_QC} ${SANITY_RPT}
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

checkDupLines ${INPUT_FILE_QC} ${SANITY_RPT}
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

checkDupFields ${INPUT_FILE_QC} ${SANITY_RPT} 1 "MGI IDs"
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

checkColumns ${INPUT_FILE_QC} ${SANITY_RPT} ${MRKCOORD_FILE_COLUMNS}
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

checkMGIIDS ${INPUT_FILE_QC} ${SANITY_RPT}
if [ $? -ne 0 ]
then
    FILE_ERROR=1
fi

if [ ${FILE_ERROR} -ne 0 ]
then
    echo "Sanity errors detected. See ${SANITY_RPT}" | tee -a ${LOG}
fi

#
# If the input file had sanity errors, remove the QC-ready files and
# skip the QC reports.
#
if [ ${FILE_ERROR} -ne 0 ]
then
    rm -f ${INPUT_FILE_QC}
    exit 1
fi

#
# Create temp tables for the input data.
#
# we use a text field for mirbaseID because this field can be > 255 and our sybaselib does not allow
# varchar or char > 255 even though sybase 12.5 does
#

echo "" >> ${LOG}
date >> ${LOG}
echo "Create temp tables for the input data" >> ${LOG}
cat - <<EOSQL | psql -h${PG_DBSERVER} -d${PG_DBNAME} -U mgd_dbo -e  >> ${LOG}

create table ${TEMP_TABLE} (
    mgiID varchar(80) not null,
    chromosome varchar(8) null,
    startCoordinate float null,
    endCoordinate float null,
    strand char(1) null,
    provider varchar(255) not null,
    display varchar(255) not null,
    mirbaseID text null,
    buildValue varchar(30) not null
);

create index idx_mgiID on ${TEMP_TABLE} (mgiID);

create index idx_chromosome on ${TEMP_TABLE} (chromosome);

grant all on ${TEMP_TABLE} to public;

EOSQL

#
# Generate the QC reports.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Generate the QC reports" >> ${LOG}
# TO DO uncomment this when we test the python script
{ ${LOAD_QC} ${INPUT_FILE_QC} 2>&1; echo $? > ${TMP_FILE}; } >> ${LOG}
#echo 0 < ${TMP_FILE}
if [ `cat ${TMP_FILE}` -eq 1 ]
then
    echo "An error occurred while generating the QC reports"
    echo "See log file (${LOG})"
    RC=1
elif [ `cat ${TMP_FILE}` -eq 2 ]
then
    #cat ${RPT_NAMES_RPT} | tee -a ${LOG}
    RC=0
elif [ `cat ${TMP_FILE}` -eq 3 ]
then
    #cat ${RPT_NAMES_RPT} | tee -a ${LOG}
    RC=1
else
    echo "QC reports successful, no errors" | tee -a ${LOG}
    RC=0
fi
cat ${RPT_NAMES_RPT} | tee -a ${LOG}

#
# Drop the temp tables.
#
echo "" >> ${LOG}
date >> ${LOG}
echo "Drop the temp tables" >> ${LOG}
cat - <<EOSQL | psql -h${PG_DBSERVER} -d${PG_DBNAME} -U mgd_dbo -e  >> ${LOG}

drop table ${TEMP_TABLE};

EOSQL

date >> ${LOG}

#
# Remove the bcp files.
#
rm -f ${INPUT_FILE_BCP} 

exit ${RC}
