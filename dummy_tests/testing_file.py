import time

from prefect import flow, get_run_logger


@flow
def dummy_flow1():
    logger = get_run_logger()
    for i in range(3):
        time.sleep(5)
        logger.info('Flow1 test')
    pass

@flow
def dummy_flow2():
    logger = get_run_logger()
    for i in range(3):
        time.sleep(2)
        logger.info('Flow2 test')
    pass

