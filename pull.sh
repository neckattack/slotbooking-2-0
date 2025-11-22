#!/bin/bash
git pull
./venv/bin/pip install -r ./requirements.txt
service slotbooking restart
