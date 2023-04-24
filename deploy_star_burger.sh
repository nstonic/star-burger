#!/bin/bash

set -e
echo "Executing 'git pull'"
git stash
git pull

echo "Installing requirements"
./venv/bin/pip install -r requirements.txt

echo "Preparing frontend"
npm ci
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"

echo "Preparing db"
./venv/bin/python3 manage.py migrate --noinput

echo "Collect static files"
./venv/bin/python3 manage.py collectstatic --noinput

echo "Restarting"
sudo systemctl reload nginx
sudo systemctl restart star-burger

echo "Reporting to Rollbar"
export $(xargs < ./.env)
REVISION=$(git rev-parse --short HEAD)

curl "https://api.rollbar.com/api/1/deploy/" \
     -F access_token=$ROLLBAR_ACCESS_TOKEN \
     -F environment="production" \
     -F revision=$REVISION \
     -F local_username="root"

echo
echo "Deployed successfully"
