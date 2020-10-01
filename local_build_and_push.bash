#!/bin/bash
git log -1
export TAG=$(git log -1 --pretty=format:"%h") && echo TAG=$TAG
docker build -t my-apache2:$TAG -t my-apache2:latest .
docker tag my-apache2:$TAG 141517001380.dkr.ecr.us-east-1.amazonaws.com/my-apache2:$TAG
docker tag my-apache2:$TAG 141517001380.dkr.ecr.us-east-1.amazonaws.com/my-apache2:latest
docker push 141517001380.dkr.ecr.us-east-1.amazonaws.com/my-apache2:$TAG
docker push 141517001380.dkr.ecr.us-east-1.amazonaws.com/my-apache2:latest
