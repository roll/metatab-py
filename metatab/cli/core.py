import sys
from genericpath import exists
from os.path import join
from uuid import uuid4

import six

from metatab import _meta, MetatabDoc
from metatab.util import make_metatab_file
from rowgenerators import Url


def prt(*args, **kwargs):
    print(*args, **kwargs)


def warn(*args, **kwargs):
    print('WARN:', *args, file=sys.stderr, **kwargs)


def err(*args, **kwargs):
    import sys
    print("ERROR:", *args, file=sys.stderr, **kwargs)
    sys.exit(1)


def load_plugins(parser):
    import metatab_plugins._plugins as mtp

    for p in mtp.metatab_plugins_list:
        p(parser)


def metatab_info(cache):
    from tabulate import tabulate
    from rowgenerators._meta import __version__ as rg_ver
    from rowpipe._meta import __version__ as rp_ver

    table = [
        ('Version',_meta.__version__),
        ('Row Generators', rg_ver),
        ('Row Pipes', rp_ver),
        ('Cache Dir', str(cache.getsyspath('/'))),
    ]

    prt(tabulate(table))


def new_metatab_file(mt_file, template):
    template = template if template else 'metatab'

    if not exists(mt_file):
        doc = make_metatab_file(template)

        doc['Root']['Identifier'] = str(uuid4())

        doc.write_csv(mt_file)


def find_files(base_path, types):
    from os import walk
    from os.path import join, splitext

    for root, dirs, files in walk(base_path):
        if '_metapack' in root:
            continue

        for f in files:
            if f.startswith('_'):
                continue

            b, ext = splitext(f)
            if ext[1:] in types:
                yield join(root, f)


def get_lib_module_dict(doc):
    """Load the 'lib' directory as a python module, so it can be used to provide functions
    for rowpipe transforms"""

    from os.path import dirname, abspath, join, isdir
    from importlib import import_module
    import sys

    u = Url(doc.ref)
    if u.proto == 'file':

        doc_dir = dirname(abspath(u.parts.path))

        # Add the dir with the metatab file to the system path
        sys.path.append(doc_dir)

        if not isdir(join(doc_dir, 'lib')):
            return {}

        try:
            m = import_module("lib")
            return {k: v for k, v in m.__dict__.items() if k in m.__all__}
        except ImportError as e:
            err("Failed to import python module form 'lib' directory: ", str(e))

    else:
        return {}


def dump_resources(doc):
    for r in doc.resources():
        prt(r.name, r.resolved_url)


def dump_resource(doc, name, lines=None):
    import unicodecsv as csv
    import sys
    from itertools import islice
    from tabulate import tabulate
    from rowpipe.exceptions import CasterExceptionError, TooManyCastingErrors

    r = doc.resource(name=name, env=get_lib_module_dict(doc))

    if not r:
        err("Did not get resource for name '{}'".format(name))

    # WARNING! This code will not generate errors if line is set ( as for the -H
    # option because the errors are tansfered from the row pipe to the resource after the
    # iterator is exhausted


    try:
        gen = islice(r, int(r.startline), lines)
    except (ValueError, AttributeError):
        gen = islice(r, 1, lines)

    def dump_errors(error_set):
        for col, errors in error_set.items():
            warn("Errors in casting column '{}' in resource '{}' ".format(col, r.name))
            for error in errors:
                warn("    ", error)


    try:
        if lines and lines <= 20:
            try:
                prt(tabulate(list(gen), list(r.headers())))
            except TooManyCastingErrors as e:
                dump_errors(e.errors)
                err(e)

        else:

            w = csv.writer(sys.stdout if six.PY2 else sys.stdout.buffer)

            if r.headers():
                w.writerow(r.headers())
            else:
                warn("No headers for resource '{}'; have schemas been generated? ".format(name))

            for row in gen:
                w.writerow(row)

    except CasterExceptionError as e:  # Really bad errors, not just casting problems.
        raise e
        err(e)
    except TooManyCastingErrors as e:
        dump_errors(e.errors)
        err(e)

    dump_errors(r.errors)



def dump_schema(doc, name):
    from tabulate import tabulate

    t = get_table(doc, name)

    rows = []
    header = 'name altname datatype description'.split()
    for c in t.children:
        cp = c.properties
        rows.append([cp.get(h) for h in header])

    prt(tabulate(rows, header))


def get_table(doc, name):
    t = doc.find_first('Root.Table', value=name)

    if not t:

        table_names = ["'" + t.value + "'" for t in doc.find('Root.Table')]

        if not table_names:
            table_names = ["<No Tables>"]

        err("Did not find schema for table name '{}' Tables are: {}"
            .format(name, " ".join(table_names)))

    return t


def make_excel_package(file, cache, env, skip_if_exists):
    from metatab.package import ExcelPackage

    p = ExcelPackage(file, callback=prt, cache=cache, env=env)

    if not p.exists() or not skip_if_exists:
        url = p.save()
        prt("Packaged saved to: {}".format(url))
        created = True
    elif p.exists():
        prt("Excel Package already exists")
        created = False
        url = p.save_path()

    return url, created


def make_zip_package(file, cache, env, skip_if_exists):

    from metatab.package import ZipPackage

    p = ZipPackage(file, callback=prt, cache=cache, env=env)
    if not p.exists() or not skip_if_exists:
        url = p.save()
        prt("Packaged saved to: {}".format(url))
        created = True
    elif p.exists():
        prt("ZIP Package already exists")
        created = False
        url = p.save_path()

    return url, created


def make_filesystem_package(file, cache, env, skip_if_exists):

    from metatab.package import FileSystemPackage
    p = FileSystemPackage(file, callback=prt, cache=cache, env=env)
    if not p.exists() or not skip_if_exists:
        url = p.save()
        prt("Packaged saved to: {}".format(url))
        created = True
    elif p.exists():
        prt("Filesystem Package already exists")
        created = False
        url = p.save_path()

    return url, created


def make_csv_package(file, cache, env, skip_if_exists):

    from metatab.package import CsvPackage

    p = CsvPackage(file, callback=prt, cache=cache, env=env)
    if not p.exists() or not skip_if_exists:
        url = p.save()
        prt("Packaged saved to: {}".format(url))
        created = True
    elif p.exists():
        prt("CSV Package already exists")
        created = False
        url = p.save_path()

    return url, created

def make_s3_package(file, url, cache,  env, skip_if_exists):
    from metatab.package import S3Package

    p = S3Package(file, callback=prt, cache=cache, env=env)
    if not p.exists(url) or not skip_if_exists:
        url = p.save(url)
        prt("Packaged saved to: {}".format(url))
        created = True
    elif p.exists(url):
        prt("S3 Package already exists")
        created = False
        url = p.access_url

    return url, created


def update_name(mt_file, fail_on_missing=False, report_unchanged=True):
    if isinstance(mt_file, MetatabDoc):
        doc = mt_file
    else:
        doc = MetatabDoc(mt_file)

    o_name = doc.find_first_value("Root.Name", section=['Identity', 'Root'])

    updates = doc.update_name()

    for u in updates:
        prt(u)

    prt("Name is: ", doc.find_first_value("Root.Name", section=['Identity', 'Root']))

    if o_name != doc.find_first_value("Root.Name", section=['Identity', 'Root']):
        doc.write_csv(mt_file)


class S3Bucket(object):
    def __init__(self, url):
        from rowgenerators import parse_url_to_dict
        import boto3

        self._s3 = boto3.resource('s3')

        p = parse_url_to_dict(url)

        if p['netloc']:  # The URL didn't have the '//'
            self._prefix = p['path']
            bucket_name = p['netloc']
        else:
            proto, netpath = url.split(':')
            bucket_name, self._prefix = netpath.split('/', 1)

        self._bucket_name = bucket_name
        self._bucket = self._s3.Bucket(bucket_name)


    def access_url(self, *paths):
        import boto3

        key = join(self._prefix, *paths).strip('/')

        s3 = boto3.client('s3')

        return '{}/{}/{}'.format(s3.meta.endpoint_url.replace('https', 'http'), self._bucket_name, key)

    def write(self, body, *paths):
        from botocore.exceptions import ClientError
        import mimetypes

        if isinstance(body, six.string_types):
            with open(body,'rb') as f:
                body = f.read()

        key = join(self._prefix, *paths).strip('/')

        try:
            o = self._bucket.Object(key)
            if o.content_length == len(body):
                prt("File '{}' already in bucket; skipping".format(key))
                return self.access_url(*paths)
            else:
                prt("File '{}' already in bucket, but length is different; re-wirtting".format(key))

        except ClientError as e:
            if int(e.response['Error']['Code']) != 404:
                raise

        ct = mimetypes.guess_type(key)[0]

        try:
            self._bucket.put_object(Key=key, Body=body, ACL='public-read',
                                           ContentType=ct if ct else 'binary/octet-stream')
        except Exception as e:
            self.err("Failed to write '{}': {}".format(key, e))

        return self.access_url(*paths)