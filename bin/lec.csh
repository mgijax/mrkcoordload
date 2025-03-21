#!/bin/csh -f

#
# Template
#


if ( ${?MGICONFIG} == 0 ) then
        setenv MGICONFIG /usr/local/mgi/live/mgiconfig
endif

source ${MGICONFIG}/master.config.csh

cd `dirname $0`

setenv LOG $0.log
rm -rf $LOG
touch $LOG
 
date | tee -a $LOG
 
cat - <<EOSQL | ${PG_DBUTILS}/bin/doisql.csh $0 | tee -a $LOG

    select mcf._feature_key, mcf._Object_key as markerKey, a.accid as mgiID, m.symbol, mcc.name, l.provider
    from MAP_Coord_Feature mcf, MAP_Coordinate mc, MAP_Coord_Collection mcc, ACC_Accession a, MRK_Marker m, MRK_Location_Cache l
    where mcf._Map_key = mc._Map_key
    and mc._Collection_key = mcc._Collection_key
    and mcc.name in ('MGI Curation')
    and mcf._Object_key = a._Object_key
    and a._MGIType_key = 2
    and a._LogicalDB_key = 1
    and a.preferred = 1
    and a.prefixPart = 'MGI:'
    and mcf._Object_key = m._marker_key
    and m._marker_key = l._marker_key
    order by symbol
;

EOSQL

date |tee -a $LOG

