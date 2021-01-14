#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"


pip3 install gevent

cp ${DIR}/pythreadpool/gevent_thread_pool.py ${DIR}
cp ${DIR}/pythreadpool/native_thread_pool.py ${DIR}

python3 -m unittest ${DIR}/gevent_thread_pool_test.py
python3 -m unittest ${DIR}/native_thread_pool_test.py

rm ${DIR}/gevent_thread_pool_test.py
rm ${DIR}/native_thread_pool_test.py