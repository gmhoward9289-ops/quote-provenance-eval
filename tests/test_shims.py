def test_package_and_shims_export_the_same_locate():
    import anchor
    import trust_but_anchor
    from trust_but_anchor import locate
    assert locate is trust_but_anchor.locate
    assert locate is anchor.locate
