#!/bin/sh

#
# This script is a wrapper around the process that generates the input
# files for the mrkcoordload
#
# Usage:
#
#     mrkcoordload.sh
#


cd `dirname $0`
LOG=`pwd`/createInputFiles.log
rm -rf ${LOG}

#
#  Verify the argument(s) to the shell script.
#
if [ $# -ne 0 ]
then
    echo ${Usage} | tee -a ${LOG}
    exit 1
fi

CONFIG_LOAD=../mrkcoordload.config

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
#if [ -f ${LASTRUN_FILE} ]
#then
#    if /usr/local/bin/test ${LASTRUN_FILE} -nt ${INPUT_FILE}
#    then
#
#        echo "Input file has not been updated - skipping load" | tee -a ${LOG_PROC}
#        # set STAT for shutdown
#        STAT=0
#        echo 'shutting down'
#        shutDown
#        exit 0
#    fi
#fi

# get the coordinate version
echo 'get coordinate version'
save=$IFS
IFS=';'
export IFS
echo "IFS: $IFS"
echo ${INPUT_FILE}
echo `cat ${INPUT_FILE} | line `
for l in `cat ${INPUT_FILE} | line`
do
    echo $l
    key=`echo $l | cut -d= -f1`
    echo $key
    value=`echo $l | cut -d= -f2`
    echo $value
    if [ $key = 'build' ] ; then
        COORD_VERSION=$value
        export COORD_VERSION
        echo "COORD_VERSION: $COORD_VERSION"
    elif [ $key = 'strain' ] ; then
        STRAIN=$value
        export STRAIN
        echo "STRAIN: $STRAIN"
    else
        echo 'unrecognized key'
    fi
done

IFS=$save
echo "IFS: $IFS"

#
# create input files
#
echo 'Running createInputFiles.py' >> ${LOG_DIAG}
${MRKCOORDLOAD}/bin/createInputFiles.py
STAT=$?
checkStatus ${STAT} "${MRKCOORDLOAD}/bin/createInputFiles.py"

#
# for each input file:
# add collection name to the environment
# run the coordload
#

for f in `cat /data/loads/mgi/mrkcoordload/input/coordinateFileList.txt` # | cut -d. -f2`
do
    echo $f
    # these env variable names expected by java coordload
    # replace '_' with ' ' e.g. NCBI_UniSTS -> NCBI UniSTS
    suffix=`echo $f | cut -d. -f2`
    echo $suffix
    COORD_COLLECTION_NAME=`echo $suffix | sed 's/\_/ /g'`
    export COORD_COLLECTION_NAME
    echo ${COORD_COLLECTION_NAME}

    INFILE_NAME=$f
    export INFILE_NAME
    echo ${INFILE_NAME}
    if [ ! -r ${INFILE_NAME} ]
    then
        # set STAT for endJobStream.py
        STAT=1
        checkStatus ${STAT} "Cannot read from input file: ${INFILE_NAME}"
    fi
    
    MAIL_LOADNAME="${COORD_COLLECTION_NAME}, ${MAIL_LOADNAME}"
    export MAIL_LOADNAME
    echo ${MAIL_LOADNAME}

    echo "Running ${COORD_COLLECTION_NAME} mrkcoordload" | tee -a ${LOG_DIAG} ${LOG_PROC}
    ${JAVA} ${JAVARUNTIMEOPTS} -classpath ${CLASSPATH} \
        -DCONFIG=${CONFIG_MASTER},${CONFIG_LOAD} \
	-DCOORD_COLLECTION_NAME="${COORD_COLLECTION_NAME}" \
	-DINFILE_NAME=${INFILE_NAME} \
	-DCOORD_VERSION="${COORD_VERSION}" \
        -DJOBKEY=${JOBKEY} ${DLA_START}

    STAT=$?
    checkStatus ${STAT} "${COORD_COLLECTION_NAME} mrkcoordload java load"
done

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

