#!/bin/bash
# Dump the DB to stdout with maximum compression, and stream that to S3

timestamp=$(date +%s)
sudo -u postgres pg_dump --no-owner -v -Z 9 calypso | aws s3 cp - s3://andrz-research-bak/calypso/backup-${timestamp}.sql.gz
