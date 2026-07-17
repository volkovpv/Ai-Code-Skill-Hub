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


def insecure(command: str, payload: bytes, doc: str, expr: str, url: str) -> None:
    result = eval(expr)
    subprocess.run(command, shell=True)
    obj = pickle.loads(payload)
    data = yaml.load(doc)
    path = tempfile.mktemp()
    stamp = datetime.utcnow()
    client.get(url, verify=False)
    handle(result, obj, data, path, stamp)


# type: ignore
broken = demo
