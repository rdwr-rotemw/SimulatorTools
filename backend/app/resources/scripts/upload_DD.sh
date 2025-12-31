#!/bin/bash

fullfilename=$1
filename=${fullfilename##*/}
vision=localhost
user=radware
pw=radware
#set -x

## Login
result=`curl -ks -X POST "https://$vision/mgmt/system/user/login" \
     -H 'Content-Type: application/json; charset=utf-8' \
     -d $"{
\"username\": \"$user\",
\"password\": \"$pw\"
}" 2>&1`
if [ $? -ne 0 ]; then
    echo Error: unable to log in
    echo $result
    exit 1
fi
jsession=`echo $result | tr "," "\n"|grep -i jsession|tr -d '"' | cut -d: -f2`
#echo $jsession
sleep 1
curl -X POST --insecure -H "Content-Type: multipart/form-data" -H "Cookie: JSESSIONID=$jsession" -F "data=@$fullfilename" https://$vision/mgmt/system/config/dd/uploaddd?fileName=$filename
echo ""
