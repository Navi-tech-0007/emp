#!/bin/bash -ex
yum -y install python3 mysql
pip3 install -r requirements.txt
amazon-linux-extras install epel
yum -y install stress
export PHOTOS_BUCKET=${SUB_PHOTOS_BUCKET}
export DATABASE_HOST=${SUB_DATABASE_HOST}
export DATABASE_USER=${SUB_DATABASE_USER}
export DATABASE_PASSWORD=${SUB_DATABASE_PASSWORD}
export DATABASE_DB_NAME=employees
cat database_create_tables.sql | \
mysql -h $$DATABASE_HOST -u $$DATABASE_USER -p$$DATABASE_PASSWORD
FLASK_APP=application.py /usr/local/bin/flask run --host=0.0.0.0 --port=80




#Instaling Git and cloning the repository
sudo dnf install -y git
git clone https://github.com/Navi-tech-0007/emp.git

#Installing mycli for db
sudo yum install -y python3-pip  # or dnf
sudo pip3 install mycli

#Creating new directory and moving to it
sudo mkdir /Projet/
sudo chown -R ec2-user:ec2-user /Projet/
mv emp /Projet/

#If want to acccess db from ec2 instance
mycli -h scheduledb.cdk4umg4mf9o.us-east-2.rds.amazonaws.com -u admin -p Qwerty77

#Installing requirements and dependencies
cd /Projet/emp
sudo yum -y install python3-pip
sudo pip install -r requirements.txt
sudo yum -y install stress
pip install python-dotenv

#running the application
export PHOTOS_BUCKET=emp-photo-375e3264
export AWS_DEFAULT_REGION=us-east-2
export DYNAMO_MODE=on
export FLASK_APP=application.py
sudo -E /usr/local/bin/flask run --host=0.0.0.0 --port=80
