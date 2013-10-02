#!/usr/bin/python
# Copyright (C) 2013 Red Hat, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import io
import re
import sys
import logging
logging.basicConfig(format='%(levelname)s:%(funcName)s:%(message)s',
                    level=logging.INFO)
import parse
import argparse


class Target(object):
    """
    Represents one line from the Python modules.
    """
    pattern = re.compile(r"^\s*@(step|when|then)\(u'(.*)'\)")
    result = 'targets'

    def __init__(self, text, filename, lineno):
        self.text = text
        self.parser = parse.compile(self.text)
        self.filename = filename
        self.lineno = int(lineno)

    def __unicode__(self):
        return "%s [@%s:%d]" % (self.text, self.filename, self.lineno)

    def __str__(self):
        return self.__unicode__().encode("utf-8")

    def ismatch(self, feature):
        """
        Checks whether the target line can be expanded to match
        the Feature.
        """
        out = self.parser.parse(feature)
        if out:
            logging.debug("out = %s", out)
        return out


class Feature(object):
    """
    Represents one line from the feature BDD files.
    """
    pattern = \
        re.compile(r'^\s+(\*|[Ww]hen|[Ss]tep|[Tt]hen|[Gg]iven)\s+(.*)\s*$')
    result = 'features'

    def __init__(self, text, filename, lineno):
        self.text = text

    def __unicode__(self):
        return self.text

    def __str__(self):
        return self.__unicode__().encode("utf-8")

    def match(self, targlist):
        """
        Returns the first Target matching the current Feature line.
        """
        for trg in targlist:
            if trg.ismatch(self.text):
                return trg

        return None


class SourceFile(object):
    def __init__(self, filename):
        self.name = filename

    def ishidden(self):
        """Is file hidden on the given OS.

        Later we can add some magic for non-Unix filesystems.
        """
        return self.name[0] == "."


class CodeFile(io.TextIOWrapper):
    def __init__(self, filename):
        filename = os.path.abspath(filename)
        io.TextIOWrapper.__init__(self,
                                  io.BufferedReader(
                                  io.FileIO(filename, "r")))

    def process_file(self, cdir):
        PATTERNS = {'.py': Target, '.feature': Feature}
        out = {
            'targets': [],
            'features': []
        }
        file_ext = os.path.splitext(self.name)[1]
        if file_ext in PATTERNS.keys():
            ftype = PATTERNS[file_ext]

            logging.debug("cdir = %s, file = %s", cdir, self.name)
            with io.open(self.name) as f:
                lineno = 0
                for line in f.readlines():
                    lineno += 1
                    matches = ftype.pattern.search(line)
                    if matches:
                        logging.debug("key = %s", ftype.result)
                        logging.debug("value = %s", matches.group(2))
                        obj = ftype(matches.group(2), self.name, lineno)
                        out[ftype.result].append(obj)

        len_results = len(out['targets']) + len(out['features'])
        if len_results:
            logging.debug("len out = %d", len_results)

        return out


def walker(startdir):
    feature_list = []
    target_list = []

    for root, dirs, files in os.walk(startdir):
        for directory in dirs:
            d = SourceFile(directory)
            if d.ishidden():
                dirs.remove(d.name)

        for f in files:
            in_f = CodeFile(os.path.join(root, f))

            new_out = in_f.process_file(root)
            feature_list.extend(new_out['features'])
            target_list.extend(new_out['targets'])

    return feature_list, target_list


def matcher(features, targets, out_dir):
    out = []
    for feat in features:
        trg = feat.match(targets)
        if trg:
            rel_filename = os.path.relpath(trg.filename, out_dir)
            logging.debug("feat = %s", feat)
            logging.debug("trg.filename = %s", rel_filename)
            logging.debug("trg.lineno = %s", trg.lineno)
            out.append((feat, rel_filename, trg.lineno,))

    return out


def get_step(feature, feat_list, target_list):
    for feat in feat_list:
        trg = feat.match(target_list)
        if trg:
            return trg.filename, trg.lineno


if __name__ == "__main__":
    desc = """
    Generate tags from Behave feature files and steps.
    """
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("-o", "--output", metavar="OUTPUT",
                        action="store", dest="output", default=None,
                        help="Name of the output file")
    options = parser.parse_args()

    logging.debug("options.output = %s", options.output)
    if options.output:
        outf = io.open(options.output, "w")
        outdir = os.path.dirname(outf.name)
    else:
        outf = sys.stdout
        outdir = os.curdir
    logging.debug("outf = %s", outf)

    raw = walker(os.curdir)
    res = matcher(raw[0], raw[1], outdir)
    for r in res:
        outf.write(unicode("%s\t%s\t%s\n" % r))
