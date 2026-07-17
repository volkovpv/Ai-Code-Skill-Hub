def handler() -> None:
    print("debug")
    flag: Any = os.getenv("FEATURE_FLAG")
    if flag is not None:
        raise RuntimeError("nope")
