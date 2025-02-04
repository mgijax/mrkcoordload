#!/bin/sh
#
# Purpose:
#	wrapper for mrkcoordDelete.py
#
# History
#

BINDIR=`dirname $0`
COMMON_CONFIG=`cd ${BINDIR}/..; pwd`/mrkcoordloaddelete.config
USAGE="Usage: mrkcoordDelete.sh"

#
# Make sure the common configuration file exists and source it.
#
if [ -f ${COMMON_CONFIG} ]
then
    . ${COMMON_CONFIG}
else
    echo "Missing configuration file: ${COMMON_CONFIG}"
    exit 1
fi

#
# Initialize the log file.
#
LOG=${LOGDIR}/mrkcoordDelete.sh.log
rm -rf ${LOG}
touch ${LOG}

#
# Source the DLA library functions.
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

#####################################
#
# Main
#
#####################################

#
# updateArchive including OUTPUTDIR, startLog, getConfigEnv
# sets "JOBKEY"
#
preload ${OUTPUTDIR}

#
# if INPUT_FILE_DEFAULT does not exist, then skip load
#
if [ ! -f ${INPUT_FILE_DEFAULT} ]
then
        echo "Input file ${INPUT_FILE_DEFAULT} does not exist - skipping load" | tee -a ${LOG_PROC}
        # set STAT for shutdown
        STAT=0
        echo 'shutting down'
        shutDown
        exit 0
fi

# NOTE: keep this commented out until production release
#
# There should be a "lastrun" file in the input directory that was updated
# the last time the load was run for this input file. If this file exists
# and is more recent than the input file, the load does not need to be run.
#
LASTRUN_FILE=${INPUTDIR}/lastrundelete
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

echo "Running marker coordiante delete load" | tee -a ${LOG_DIAG}
${PYTHON} ${MRKCOORDLOAD}/bin/mrkcoordDelete.py ${INPUT_FILE_DEFAULT} load | tee -a ${LOG_DIAG}
STAT=$?
checkStatus ${STAT} "mrkcoordDelete.py"

#
# Touch the "lastrun" file to note when the load was run.
#
touch ${LASTRUN_FILE}

#
# run postload cleanup and email logs
#
shutDown

