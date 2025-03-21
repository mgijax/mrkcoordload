#!/bin/sh -f

case `uname -n` in
bhmgiapp01) ssh mgiadmin@bhmgidb03lp 'rm -rf ${DATALOADSOUTPUT}/snpcacheload/output/lastrun';;
bhmgidevapp01) ssh mgiadmin@bhmgidb05ld 'rm -rf ${DATALOADSOUTPUT}/snpcacheload/output/lastrun';;
*) ;;
esac

