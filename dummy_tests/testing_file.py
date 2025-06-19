from prefect import flow


@flow
def my_flow(x: int, y: int):
    return x + y

if __name__ == "__main__":
    my_flow(x=5, y=10)

if __name__ == "__main__":
    my_flow.serve(
        name="my_deployment",
        parameters={"x": 0, "y": 0},  # Default parameters
    )