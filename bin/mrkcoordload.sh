#!/bin/sh

#
# This script is a wrapper around the process that generates the input
# files for the mrkcoordload
#
# Usage:
#
#     mrkcoordload.sh
#

cd `dirname $0`/..
CONFIG_LOAD=`pwd`/mrkcoordload.config

cd `dirname $0`
LOG=`pwd`/createInputFiles.log
rm -rf ${LOG}

RUNTYPE=live

#
#  Verify the argument(s) to the shell script.
#
if [ $# -ne 0 ]
then
    echo ${Usage} | tee -a ${LOG}
    exit 1
fi

#
# verify & source the configuration file
#

if [ ! -r ${CONFIG_LOAD} ]
then
    echo "Cannot read configuration file: ${CONFIG_LOAD}"
    exit 1
fi

. ${CONFIG_LOAD}

#
#  Make sure the master configuration file is readable
#

if [ ! -r ${CONFIG_MASTER} ]
then
    echo "Cannot read configuration file: ${CONFIG_MASTER}"
    exit 1
fi

#
#  Source the DLA library functions.
#

if [ "${DLAJOBSTREAMFUNC}" != "" ]
then
    if [ -r ${DLAJOBSTREAMFUNC} ]
    then
        . ${DLAJOBSTREAMFUNC}
    else
        echo "Cannot source DLA functions script: ${DLAJOBSTREAMFUNC}" | tee -a ${LOG}
        exit 1
    fi
else
    echo "Environment variable DLAJOBSTREAMFUNC has not been defined." | tee -a ${LOG}
    exit 1
fi

#
# check that INFILE_NAME has been set
#
if [ "${INFILE_NAME}" = "" ]
then
    # set STAT for endJobStream.py
    STAT=1
    checkStatus ${STAT} "INFILE_NAME not defined"
fi

#
# we normally check if INFILE_NAME is readable here, but we can't because we
# need to create it first - we'll check it later
#

#####################################
#
# Main
#
#####################################

#
# createArchive including OUTPUTDIR, startLog, getConfigEnv
# sets "JOBKEY"
preload ${OUTPUTDIR}

#
# rm all files/dirs from OUTPUTDIR
#
cleanDir ${OUTPUTDIR}

#
# There should be a "lastrun" file in the input directory that was created
# the last time the load was run for this input file. If this file exists
# and is more recent than the input file, the load does not need to be run.
#
LASTRUN_FILE=${INPUTDIR}/lastrun
if [ -f ${LASTRUN_FILE} ]
then
    if test ${LASTRUN_FILE} -nt ${INPUT_FILE_DEFAULT}
    then

        echo "Input file has not been updated - skipping load" | tee -a ${LOG_PROC}
        # set STAT for shutdown
        STAT=0
        echo 'shutting down'
        shutDown
        exit 0
    fi
fi

#
# Generate the sanity/QC reports
#
echo "" >> ${LOG_DIAG}
date >> ${LOG_DIAG}
echo "Generate the sanity/QC reports" | tee -a ${LOG_DIAG}
${LOAD_QC_SH} ${INPUT_FILE_DEFAULT} ${RUNTYPE} 2>&1 >> ${LOG_DIAG}
STAT=$?
checkStatus ${STAT} "QC reports"
if [ ${STAT} -eq 1 ]
then
    shutDown
    exit 1
fi

# get the coordinate version
save=$IFS
IFS=';'
export IFS

## We will want to update INPUT_FILE_DEFAULT to INPUT_FILE_LOAD
## when we are ready to run the qC reports from the load
# Iterate thru tokens on first line delimited by IFS
for l in `cat ${INPUT_FILE_LOAD} | head -n +1`
do
    # get key in lower case
    key=`echo $l | cut -d= -f1 | tr 'A-Z' 'a-z'`
    # get value as is
    value=`echo $l | cut -d= -f2`
    value=`echo $value`
    if [ $key = 'build' ] ; then
        COORD_VERSION=$value
        export COORD_VERSION
    elif [ $key = 'strain' ] ; then
        STRAIN=$value
        export STRAIN
    fi
done

IFS=$save

#
# create input files
#
echo 'Running createInputFiles.py' >> ${LOG_DIAG}
${PYTHON} ${MRKCOORDLOAD}/bin/createInputFiles.py
STAT=$?
checkStatus ${STAT} "${MRKCOORDLOAD}/bin/createInputFiles.py"

#
# for each input file:
# add collection name to the environment
# run the coordload
#

for f in `cat ${COORD_FILES}`
do
    # these env variable names expected by java coordload
    # replace '_' with ' ' e.g. NCBI_UniSTS -> NCBI UniSTS
    suffix=`echo $f | cut -d. -f2`
    collection=`echo $suffix | cut -d~ -f1`
    abbrev=`echo $suffix | cut -d~ -f2`
    COORD_COLLECTION_NAME=`echo $collection | sed 's/\_/ /g'`
    export COORD_COLLECTION_NAME
    COORD_COLLECTION_ABBREV=`echo $abbrev | sed 's/\_/ /g'`
    export COORD_COLLECTION_ABBREV

    INFILE_NAME=$f
    export INFILE_NAME
    if [ ! -r ${INFILE_NAME} ]
    then
        # set STAT for endJobStream.py
        STAT=1
        checkStatus ${STAT} "Cannot read from input file: ${INFILE_NAME}"
    fi
    
    MAIL_LOADNAME="${COORD_COLLECTION_NAME}, ${MAIL_LOADNAME}"
    export MAIL_LOADNAME

     echo "" >> ${LOG_DIAG}
     echo "`date`" >> ${LOG_DIAG}
    echo "Running ${COORD_COLLECTION_NAME} mrkcoordload" | tee -a ${LOG_DIAG} ${LOG_PROC}
    ${JAVA} ${JAVARUNTIMEOPTS} -classpath ${CLASSPATH} \
        -DCONFIG=${CONFIG_MASTER},${CONFIG_LOAD} \
	-DCOORD_COLLECTION_NAME="${COORD_COLLECTION_NAME}" \
	-DCOORD_COLLECTION_ABBREV="${COORD_COLLECTION_ABBREV}" \
	-DINFILE_NAME=${INFILE_NAME} \
	-DCOORD_VERSION="${COORD_VERSION}" \
        -DJOBKEY=${JOBKEY} ${DLA_START}

    STAT=$?
    checkStatus ${STAT} "${COORD_COLLECTION_NAME} mrkcoordload java load"
done

# If there are mirbase associations load them
if [ `cat ${MIRBASE_ASSOC_FILE} | wc -l` -gt 1 ]
then
    echo "" >> ${LOG_DIAG}
    echo "`date`" >> ${LOG_DIAG}
    echo "Running association load" | tee -a ${LOG_DIAG} ${LOG_PROC}
    ${ASSOCLOADER_SH} ${CONFIG_LOAD} ${ASSOCLOADCONFIG} >> ${LOG_DIAG}
    STAT=$?
    checkStatus ${STAT} "${ASSOCLOADER_SH}"

fi

#
# Touch the "lastrun" file to note when the load was run.
#
if [ ${STAT} = 0 ]
then
    touch ${LASTRUN_FILE}
fi

#
# run postload cleanup and email logs
#
shutDown

