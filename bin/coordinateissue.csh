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

select _Collection_key, name from MAP_Coord_Collection order by _Collection_key
;

select mcc._Collection_key, count(m.symbol)
    from  MAP_Coord_Feature mcf, MAP_Coordinate mc, MRK_Marker m, MAP_Coord_Collection mcc
    where mcf._Map_key = mc._Map_key
    and mc._Collection_key = mcc._Collection_key
    and mcf._Object_key = m._Marker_key
    group by 1
;

select mcc._Collection_key, mcc.name, mcf._mgitype_key, a.name, mcc.creation_date, count(mcf._object_key)
    from  MAP_Coord_Feature mcf, MAP_Coordinate mc, MAP_Coord_Collection mcc, ACC_MGIType a
    where mcf._Map_key = mc._Map_key
    and mc._Collection_key = mcc._Collection_key
    and mcf._mgitype_key = a._mgitype_key
    group by 1,2,3,4,5
;

-- what is the difference between colleciton 131/MGI & 256/MGI Curation

EOSQL

date |tee -a $LOG

