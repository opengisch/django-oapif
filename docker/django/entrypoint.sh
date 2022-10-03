#!/bin/bash

set -e

## TODO: unsure it's good practice to do that here since
# failing transifex would prevent starting the container.
#if tx pull -a; then
#    echo "Command succeeded"
#    python manage.py compilemessages
#else
#    echo "Failed to pull Transifex translations !"
#    echo "Translations will not be available. Make sure you properly set the TX_TOKEN variable."
#fi

python manage.py collectstatic --no-input
python manage.py migrate --no-input

exec $@
