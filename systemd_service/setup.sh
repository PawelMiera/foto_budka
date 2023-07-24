#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then echo "Please run as root." >&2; exit 1; fi

echo Coping files!


cp fotobudka.service /etc/systemd/system/

cp fotobudka.sh /usr/local/bin/

echo Setting permissions!

chmod a+x /usr/local/bin/fotobudka.sh

echo Reloading systemd deamon!

systemctl daemon-reload

echo Enabling services!

systemctl enable fotobudka.service
