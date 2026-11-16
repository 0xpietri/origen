"""The fetched files open with the libraries that will read them in phase 2."""

from skyfield.api import load_file

from origen import data

from .conftest import REAL_DATA, needs_data


@needs_data
def test_de440s_opens_with_skyfield_and_covers_its_range() -> None:
    eph = load_file(str(REAL_DATA / "ephemeris/de440s.bsp"))
    try:
        names = {name for names in eph.names().values() for name in names}
        for body in (
            "SUN",
            "MOON",
            "EARTH",
            "MERCURY",
            "VENUS",
            "MARS BARYCENTER",
            "JUPITER BARYCENTER",
            "SATURN BARYCENTER",
            "URANUS BARYCENTER",
            "NEPTUNE BARYCENTER",
            "PLUTO BARYCENTER",
        ):
            assert body in names, body
        seg = eph.spk.segments[0]
        assert seg.start_jd < 2397000  # before 1850-01-01
        assert seg.end_jd > 2506000  # after 2149-12-31
    finally:
        eph.close()


@needs_data
def test_star_files_look_like_their_catalogues() -> None:
    with (REAL_DATA / "stars/hip_main.dat").open() as f:
        first = f.readline()
    assert first.startswith("H|")
    names = (REAL_DATA / "stars/IAU-CSN.txt").read_text(encoding="utf-8")
    assert "Acrux" in names and "Canopus" in names
    assert data.STARS.endswith("20220404") and "Last updated 2022-04-04" in names
