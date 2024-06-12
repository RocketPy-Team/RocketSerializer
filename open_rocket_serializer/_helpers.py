import logging
import os
import shutil
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_ork_from_zip(zip_path: Path, extract_dir: Path) -> Path:
    """Extracts .ork file from a zip archive and returns its path.
    This is important because sometimes the .xml file is stuck inside the .ork
    file. The function extracts the .ork (.xml) file from the zip (.ork) file
    and returns its path as a Path object.

    Notes
    -----
    For illustration: if you try to open the .ork file with a text editor and
    you see a bunch of weird characters, it is probably a "zip" file. You can
    try to rename the file to .zip and open it with a zip extractor.

    Parameters
    ----------
    zip_path : Path
        The path to the .zip file.
    extract_dir : Path
        The path to the directory where the .ork file will be extracted.

    Returns
    -------
    Path
        The path to the extracted .ork file.
    """
    try:
        temp_zip_path = zip_path.with_suffix(".zip")
        shutil.copy(zip_path, temp_zip_path)
        with ZipFile(temp_zip_path) as zf:
            zf.extract("rocket.ork", path=extract_dir)
        logger.info(
            'Successfully extracted rocket.ork from "%s" to "%s"',
            zip_path.as_posix(),
            extract_dir.as_posix(),
        )
        return extract_dir / "rocket.ork"
    except BadZipFile:
        logger.warning(
            'The file "%s" seems to be a direct .ork file and not a compressed archive.',
            zip_path.as_posix(),
        )
        return zip_path
    except Exception as e:
        logger.error(
            'Error while extracting data from "%s": %s', zip_path.as_posix(), e
        )
        raise
    finally:
        if temp_zip_path.exists():
            os.remove(temp_zip_path)


def parse_ork_file(ork_path: Path):
    """Parses the .ork file and returns BeautifulSoup and a list of datapoints.

    Parameters
    ----------
    ork_path : Path
        The path to the .ork file.

    Returns
    -------
    BeautifulSoup
        The BeautifulSoup object.
    """
    try:
        with open(ork_path, encoding="utf-8") as file:
            bs = BeautifulSoup(file, features="xml")
            datapoints = bs.findAll("datapoint")
            logger.info(
                "Successfully parsed .ork file at '%s' with %d datapoints",
                ork_path.as_posix(),
                len(datapoints),
            )
            return bs, datapoints
    except UnicodeDecodeError as exc:
        error_msg = (
            "The .ork file is not in UTF-8."
            + "Please open the .ork file in a text editor and save it as UTF-8."
        )
        logger.error(error_msg)
        raise UnicodeDecodeError(error_msg) from exc
    except Exception as e:
        logger.error("Error while parsing the file '%s': %s", ork_path.as_posix(), e)
        raise e


def _dict_to_string(dictionary, indent=0):
    """Converts a dictionary to a string.

    Parameters
    ----------
    dictionary : dict
        Dictionary to be converted.
    indent : int, optional
        Indentation level, by default 0.

    Returns
    -------
    str
        String representation of the dictionary.

    Examples
    --------
    >>> from open_rocket_serializer._helpers import _dict_to_string
    >>> _dict_to_string({"a": 1, "b": {"c": 2}})
    " a: 1\n b: \n     c: 2\n"
    """
    string = ""
    for key, value in dictionary.items():
        string += " " * indent + str(key) + ": "
        if isinstance(value, dict):
            string += "\n" + _dict_to_string(value, indent + 4)
        else:
            string += str(value) + "\n"
    return string


# if __name__ == "__main__":
#     import doctest

#     doctest.testmod()
