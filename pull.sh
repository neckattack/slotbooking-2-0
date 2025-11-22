#!/bin/bash
git pull
./venv/bin/pip install -r ./requirements.txt
sudo /bin/systemctl restart slotbooking.service