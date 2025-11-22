#!/bin/bash
git pull
./venv/bin/pip install -r ./requirements.txt
/bin/systemctl restart slotbooking.service
