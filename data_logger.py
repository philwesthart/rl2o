#!/usr/bin/env python3

import logging
import time
import random

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

def main():
    setup_logging()
    logging.info("Data Logger Service Started")

    try:
        while True:
            value = random.randint(0, 100)
            logging.info(f"Sample data value: {value}")
            time.sleep(5)

    except Exception as e:
        logging.exception(f"Unhandled exception: {e}")
        raise

if __name__ == "__main__":
    main()