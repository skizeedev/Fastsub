#!/bin/bash

mkdir -p backups

cp instance/fastsub.db backups/fastsub-$(date +%F-%H%M).db

echo "Backup completed"
