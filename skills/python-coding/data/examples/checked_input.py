def handler() -> None:
    print("debug")
    flag: Any = os.getenv("FEATURE_FLAG")
    started = datetime.utcnow()
    subprocess.run(["deploy", str(started)], shell=True)
    if flag is not None:
        raise RuntimeError("nope")
