#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then echo "Please run as root." >&2; exit 1; fi

echo Coping files!


cp fotobudka.service /etc/systemd/system/

echo Reloading systemd deamon!

systemctl daemon-reload

echo Enabling services!

systemctl enable fotobudka.service
