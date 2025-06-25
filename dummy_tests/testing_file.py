# my_deployments.py
from prefect import flow, task, serve
import time
from matterlab_valves import ValcoSelectionValve
from autoammonia.utils.prefect import create_deployments


@task
def my_task0(x, y):
    print(f"Task0: {x} * {y} = {x * y}")
    return x * y

@task
def my_task1(x, y):
    print(f"Task1: {x} + {y} = {x + y}")
    return x + y

@flow(log_prints=True)
def main0():
    print("Starting Flow0")
    for i in range(3): # Reduced range for quicker testing
        result = my_task0(x=i, y=i+1)
        print(f'Flow0 iteration {i}: {result}')
        time.sleep(0.5)
    print("Flow0 Finished")

@flow(log_prints=True)
def main1():
    print("Starting Flow1")
    for i in range(3): # Reduced range for quicker testing
        result = my_task1(x=i, y=i+1)
        print(f'Flow1 iteration {i}: {result}')
        time.sleep(0.75)
    print("Flow1 Finished")

deployments = create_deployments([main0, main1])
if __name__ == "__main__":
    serve(*deployments) # Pass as separate args
    