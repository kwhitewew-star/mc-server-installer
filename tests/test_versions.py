from mcsi.core.versions import props_moved_to_gamerules, required_java, uses_snake_gamerules, version_key


def test_sorting_mixes_old_and_year_based_versions():
    vs = ["26.1", "1.21.11", "26.1-pre-1", "26.1.1", "26.1-snapshot-1", "26.1-rc-1", "1.20.1"]
    assert sorted(vs, key=version_key) == ["1.20.1", "1.21.11", "26.1-snapshot-1", "26.1-pre-1", "26.1-rc-1",
                                          "26.1", "26.1.1"]


def test_java_requirements():
    assert required_java("1.16.5") == 8
    assert required_java("1.20.1") == 17
    assert required_java("1.21.1") == 21
    assert required_java("26.1") == 25


def test_gamerule_naming():
    assert not uses_snake_gamerules("1.21.10") and uses_snake_gamerules("1.21.11")
    assert not props_moved_to_gamerules("1.21.8") and props_moved_to_gamerules("1.21.9")
