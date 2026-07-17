# Intentional violations — exactly one per checker rule — used by the tests.
def demo(config: object) -> None:
    print("starting")
    url = os.environ.get("DATABASE_URL")
    value: Any = url
    try:
        handle(value)
    except:
        pass
    assert config is not None
    breakpoint()


# type: ignore
broken = demo
