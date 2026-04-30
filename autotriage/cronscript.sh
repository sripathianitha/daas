#!/bin/bash
sudo su cohesity;
source /home/cohesity/.bashrc;
source /home/cohesity/daasenv/bin/activate;
python /home/cohesity/daas/manage.py runcrons > /home/cohesity/cronjob.log 2>&1