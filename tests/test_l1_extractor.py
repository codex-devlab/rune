from rune.review.conflict_lexical import extract_triples


def test_always_use_typescript():
    triples = extract_triples("Always use TypeScript.")
    assert any(t[0] == "always" and t[1] == "use" and "typescript" in t[2] for t in triples)


def test_never_use_typescript():
    triples = extract_triples("Never use TypeScript.")
    assert any(t[0] == "never" and t[1] == "use" for t in triples)


def test_must_run_tests():
    triples = extract_triples("You must run tests before merging.")
    assert any(t[0] == "must" and t[1] == "run" for t in triples)


def test_must_not_run_tests():
    triples = extract_triples("Do not run tests in CI.")
    assert any(t[0] in ("do_not", "must_not") and t[1] == "run" for t in triples)
