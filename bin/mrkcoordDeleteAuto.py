#
# Program: mrkcoordDeleteAuto.py
#
# use same SQL as the qcreports_db/MRK_C4AM_GeneModel.py
# select _feature_key for each Marker Feature Coorindate that exists for Collection 131,256,257:
#   131/MGI, 256/MGI Curation, 257/gff3blat
#
# and contains a Marker/Gene Model for:
#   223/VISTA Enhancer Element, 222/Ensembl Regulatory Feature, 60/Ensembl Gene Model, 59/NCBI Gene Model
#
# delete MAP_Coord_Feature based on _feature_key
#

import sys
import os
import db

db.setTrace()

results = db.sql('''
select mcf._feature_key, mcf._Object_key as markerKey, a.accid as mgiID, m.symbol, 
    mcc.name, gm.accid as gmID, gm._logicaldb_key, l.name
from MAP_Coord_Feature mcf, MAP_Coordinate mc, MAP_Coord_Collection mcc, ACC_Accession a, 
    MRK_Marker m, ACC_Accession gm, ACC_LogicalDB l
where mcf._Map_key = mc._Map_key
and mc._Collection_key in (131,256,257)
and mc._Collection_key = mcc._Collection_key
and mcf._Object_key = a._Object_key
and a._MGIType_key = 2
and a._LogicalDB_key = 1
and a.preferred = 1
and a.prefixPart = 'MGI:'
and mcf._Object_key = m._Marker_key
and a._Object_key = gm._Object_key
and gm._mgitype_key = 2
and gm._logicaldb_key in (223,222,60,59)
and gm._Logicaldb_key = l._logicaldb_key
''', 'auto')

deleteSQL = ''
for r in results:
        print(r)
        deleteSQL += ''' delete from MAP_Coord_Feature where _feature_key = %s;\n''' % (r['_feature_key'])

if deleteSQL != "":
    db.sql(deleteSQL, None)
    db.commit()


