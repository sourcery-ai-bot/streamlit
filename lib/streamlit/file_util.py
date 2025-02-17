# Copyright 2018-2022 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import errno
import io
import os

import fnmatch

from streamlit import env_util
from streamlit import util
from streamlit.string_util import is_binary_string

# Configuration and credentials are stored inside the ~/.streamlit folder
CONFIG_FOLDER_NAME = ".streamlit"


def get_encoded_file_data(data, encoding="auto"):
    """Coerce bytes to a BytesIO or a StringIO.

    Parameters
    ----------
    data : bytes
    encoding : str

    Returns
    -------
    BytesIO or StringIO
        If the file's data is in a well-known textual format (or if the encoding
        parameter is set), return a StringIO. Otherwise, return BytesIO.

    """
    if encoding == "auto":
        encoding = None if is_binary_string(data) else "utf-8"
    if encoding:
        return io.StringIO(data.decode(encoding))

    return io.BytesIO(data)


@contextlib.contextmanager
def streamlit_read(path, binary=False):
    """Opens a context to read this file relative to the streamlit path.

    For example:

    with streamlit_read('foo.txt') as foo:
        ...

    opens the file `%s/foo.txt`

    path   - the path to write to (within the streamlit directory)
    binary - set to True for binary IO
    """ % CONFIG_FOLDER_NAME
    filename = get_streamlit_file_path(path)
    if os.stat(filename).st_size == 0:
        raise util.Error('Read zero byte file: "%s"' % filename)

    mode = "r"
    if binary:
        mode += "b"
    with open(os.path.join(CONFIG_FOLDER_NAME, path), mode) as handle:
        yield handle


@contextlib.contextmanager
def streamlit_write(path, binary=False):
    """
    Opens a file for writing within the streamlit path, and
    ensuring that the path exists. For example:

        with streamlit_write('foo/bar.txt') as bar:
            ...

    opens the file %s/foo/bar.txt for writing,
    creating any necessary directories along the way.

    path   - the path to write to (within the streamlit directory)
    binary - set to True for binary IO
    """ % CONFIG_FOLDER_NAME
    mode = "w"
    if binary:
        mode += "b"
    path = get_streamlit_file_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, mode) as handle:
            yield handle
    except OSError as e:
        msg = ["Unable to write file: %s" % os.path.abspath(path)]
        if e.errno == errno.EINVAL and env_util.IS_DARWIN:
            msg.append(
                "Python is limited to files below 2GB on OSX. "
                "See https://bugs.python.org/issue24658"
            )
        raise util.Error("\n".join(msg))


def get_static_dir():
    """Get the folder where static HTML/JS/CSS files live."""
    dirname = os.path.dirname(os.path.normpath(__file__))
    return os.path.normpath(os.path.join(dirname, "static"))


def get_assets_dir():
    """Get the folder where static assets live."""
    dirname = os.path.dirname(os.path.normpath(__file__))
    return os.path.normpath(os.path.join(dirname, "static/assets"))


def get_streamlit_file_path(*filepath) -> str:
    """Return the full path to a file in ~/.streamlit.

    This doesn't guarantee that the file (or its directory) exists.
    """
    # os.path.expanduser works on OSX, Linux and Windows
    home = os.path.expanduser("~")
    if home is None:
        raise RuntimeError("No home directory.")

    return os.path.join(home, CONFIG_FOLDER_NAME, *filepath)


def get_project_streamlit_file_path(*filepath):
    """Return the full path to a filepath in ${CWD}/.streamlit.

    This doesn't guarantee that the file (or its directory) exists.
    """
    return os.path.join(os.getcwd(), CONFIG_FOLDER_NAME, *filepath)


def file_is_in_folder_glob(filepath, folderpath_glob) -> bool:
    """Test whether a file is in some folder with globbing support.

    Parameters
    ----------
    filepath : str
        A file path.
    folderpath_glob: str
        A path to a folder that may include globbing.

    """
    # Make the glob always end with "/*" so we match files inside subfolders of
    # folderpath_glob.
    if not folderpath_glob.endswith("*"):
        folderpath_glob += "*" if folderpath_glob.endswith("/") else "/*"
    file_dir = f'{os.path.dirname(filepath)}/'
    return fnmatch.fnmatch(file_dir, folderpath_glob)


def file_in_pythonpath(filepath) -> bool:
    """Test whether a filepath is in the same folder of a path specified in the PYTHONPATH env variable.


    Parameters
    ----------
    filepath : str
        An absolute file path.

    Returns
    -------
    boolean
        True if contained in PYTHONPATH, False otherwise. False if PYTHONPATH is not defined or empty.

    """

    pythonpath = os.environ.get("PYTHONPATH", "")
    if len(pythonpath) == 0:
        return False

    absolute_paths = [os.path.abspath(path) for path in pythonpath.split(os.pathsep)]
    return any(
        file_is_in_folder_glob(os.path.normpath(filepath), path)
        for path in absolute_paths
    )
