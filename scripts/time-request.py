#!/usr/bin/env python

import time

import requests

if __name__ == "__main__":
    url = "http://localhost:8000/oapif/collections/poles/items"

    start = time.perf_counter()
    response = requests.get(url)
    request_time = time.perf_counter() - start

    print(f"time: {request_time}")
